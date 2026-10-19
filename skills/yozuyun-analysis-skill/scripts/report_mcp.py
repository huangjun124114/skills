#!/usr/bin/env python3
# Unified Streamable HTTP MCP client core for the yozuyun analysis skill.
# Python 3.8+, standard library only. Launched by report-mcp.ps1 (Windows) or
# report-mcp-macos.sh (macOS); both launchers are thin wrappers so the protocol,
# cache, and diagnosis logic stay single-sourced on this file.

import argparse
import hashlib
import http.client
import json
import os
import re
import ssl
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

REQUIRED_TOOLS = (
    'yzy_list_report_analyses',
    'yzy_describe_report_analysis',
    'yzy_analyze_report',
)
CLIENT_INFO = {'name': 'yozuyun-analysis-skill', 'version': '2.3.0'}
# Bounded same-session recovery for a gateway that intermittently answers
# "Session not found" (non-sticky session routing). Measured on the reference
# deployment: 3 attempts ~70%, 5 attempts 100%, so 8 leaves a safety margin.
# AVAILABILITY GUARD: these limits are deliberate safety margins and must NOT
# be tightened (even if the gateway is fixed and 404s disappear) unless the
# user explicitly requests and separately confirms a lower bound. Reducing
# them turns intermittent 404s into direct query failures.
SESSION_ATTEMPTS = 8
SESSION_RETRY_DELAY = 1.0
SESSION_RETRY_MAX_DELAY = 4.0
MAX_HTTP_REQUESTS_PER_RUN = 32
MAX_DISCOVERY_CANDIDATES = 6
CACHE_TTL_MINUTES = 30.0
REQUEST_TIMEOUT_SECONDS = 45
SUPPORTED_PROTOCOL_VERSIONS = ('2025-03-26', '2025-06-18', '2025-11-25')
RESERVED_REQUEST_HEADERS = {'accept', 'content-type', 'mcp-session-id', 'mcp-protocol-version'}
TASK_ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$')
CACHE_KEY_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$')
ENV_HEADER_PATTERN = re.compile(r'^\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}$|^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$')

_rpc_seq = 0
_request_count = 0


def canonical(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True)


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def utc_now():
    return datetime.now(timezone.utc)


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def next_rpc_id():
    global _rpc_seq
    _rpc_seq += 1
    return _rpc_seq


def new_payload(method, params=None, notification=False):
    payload = {'jsonrpc': '2.0', 'method': method}
    rpc_id = None
    if not notification:
        rpc_id = next_rpc_id()
        payload['id'] = rpc_id
    if params is not None:
        payload['params'] = params
    return payload, rpc_id


def get_property(obj, name):
    if isinstance(obj, dict):
        value = obj.get(name)
        return value
    return None


class TransportError(Exception):
    pass


class McpHttpError(Exception):
    pass


class McpHttp:
    """One-connection-per-request HTTP transport; never follows redirects, TLS verified by default."""

    def __init__(self, url, default_headers):
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https'):
            raise ValueError('Expected an HTTP(S) URL.')
        self.scheme = parts.scheme
        self.host = parts.hostname
        self.port = parts.port
        self.path = (parts.path or '/') + (('?' + parts.query) if parts.query else '')
        self.default_headers = {key: value for key, value in default_headers.items()
                                if key.lower() not in RESERVED_REQUEST_HEADERS}
        self.events = []
        self.request_count = getattr(self, 'request_count', 0)

    def spend_request(self, method):
        global _request_count
        _request_count += 1
        self.request_count = _request_count
        if _request_count > MAX_HTTP_REQUESTS_PER_RUN:
            raise McpHttpError(
                'Stopped after %d HTTP requests in this run at %s; the request budget for one '
                'invocation is exhausted. Report the transport failures instead of retrying further.'
                % (MAX_HTTP_REQUESTS_PER_RUN, method))

    def post(self, payload, session_id=None, protocol_version=None):
        body = canonical(payload)
        headers = dict(self.default_headers)
        headers['Accept'] = 'application/json, text/event-stream'
        headers['Content-Type'] = 'application/json'
        if session_id:
            headers['Mcp-Session-Id'] = session_id
        if protocol_version:
            headers['MCP-Protocol-Version'] = protocol_version
        if self.scheme == 'https':
            conn = http.client.HTTPSConnection(self.host, self.port, timeout=REQUEST_TIMEOUT_SECONDS,
                                               context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            try:
                conn.request('POST', self.path, body=body.encode('utf-8'), headers=headers)
                response = conn.getresponse()
                status = response.status
                response_headers = [(key.lower(), value) for key, value in response.getheaders()]
                data = response.read()
            except OSError as error:
                raise TransportError(
                    'MCP transport failed at %s; no HTTP status received. Check network, timeout or TLS. '
                    'Do not switch connections.' % payload.get('method')) from error
        finally:
            conn.close()
        return status, response_headers, data.decode('utf-8', errors='replace')


def header_value(headers, name):
    for key, value in headers:
        if key == name:
            return value
    return None


def parse_mcp_body(body, expected_id):
    """Plain JSON response, or SSE frames merged per event and matched by JSON-RPC id."""
    if not body or not body.strip():
        return None
    trimmed = body.strip()
    if trimmed.startswith('{') or trimmed.startswith('['):
        message = json.loads(trimmed)
        if expected_id is not None and message.get('id') != expected_id:
            raise ValueError('MCP response ID mismatch.')
        return message
    messages = []
    normalized = body.replace('\r\n', '\n')
    for frame in normalized.split('\n\n'):
        data_lines = [line[5:].lstrip(' ') for line in frame.split('\n') if line.startswith('data:')]
        if data_lines:
            try:
                messages.append(json.loads('\n'.join(data_lines)))
            except ValueError:
                pass
    for message in messages:
        if message.get('id') == expected_id:
            return message
    if expected_id is not None:
        raise ValueError('No matching MCP response ID in SSE events.')
    raise ValueError('The MCP response is neither JSON nor a parseable SSE data event.')


def read_body_diagnostics(body):
    """Triage facts only: whether the error body looks like an application stack, plus sanitized class names."""
    stack_classes = []
    if body:
        stack_classes = re.findall(r'"className":"([^"\r\n]{1,200})"', body)[:3]
    has_error_body = bool(body) and re.search(r'stackTrace|className|methodName', body) is not None
    return {
        'hasErrorBody': has_error_body,
        'applicationStackClasses': stack_classes,
    }


def invoke_mcp_request(http, payload, session_id, expected_id, protocol_version):
    """Bounded same-session recovery for explicit session-not-found responses.

    The gateway in front of the report service does not pin a session to one
    backend instance, so a request can land on a node that has never seen the
    session and answer 404 'Session not found' even though the session is still
    valid elsewhere. Re-sending the same payload with the same session converges
    within a few attempts, so same-session retry is the correct recovery here.
    """
    method = payload.get('method')
    retryable_method = method == 'tools/list' or (
        method == 'tools/call' and payload.get('params', {}).get('name') in REQUIRED_TOOLS)
    attempt = 1
    while True:
        http.spend_request(method)
        status, headers, body = http.post(payload, session_id=session_id, protocol_version=protocol_version)
        session_missing = status == 404 and bool(session_id) and bool(
            re.search(r'\bsession\s+not\s+found\b', body, re.IGNORECASE))
        if session_missing and method == 'notifications/initialized':
            event = {'method': method, 'httpStatus': status, 'attempt': attempt,
                     'action': 'warning-continue', 'reason': 'session-not-found'}
            http.events.append(event)
            print(canonical(event), file=sys.stderr)
            return None, session_id
        if not (session_missing and retryable_method and attempt < SESSION_ATTEMPTS):
            break
        delay = min(SESSION_RETRY_DELAY * attempt, SESSION_RETRY_MAX_DELAY)
        event = {'method': method, 'httpStatus': status, 'attempt': attempt,
                 'action': 'retry-same-session', 'reason': 'session-not-found',
                 'delaySeconds': round(delay, 2)}
        http.events.append(event)
        print(canonical(event), file=sys.stderr)
        time.sleep(delay)
        attempt += 1
    if status < 200 or status >= 300:
        session_attached = bool(session_id)
        raise McpHttpError(
            'MCP HTTP %d at %s; sessionAttached=%s; attempts=%d. Stop and report; do not switch connections.'
            % (status, payload.get('method'), str(session_attached).lower(), attempt))
    new_session = header_value(headers, 'mcp-session-id') or session_id
    try:
        message = parse_mcp_body(body, expected_id)
    except ValueError as error:
        raise McpHttpError('%s returned an unreadable response: %s' % (payload.get('method'), error))
    return message, new_session


def invoke_observed_request(http, payload, session_id, protocol_version):
    """Observed request used only by diagnose: records status/facts instead of failing on non-2xx."""
    status, headers, body = http.post(payload, session_id=session_id, protocol_version=protocol_version)
    new_session = header_value(headers, 'mcp-session-id') or session_id
    return {
        'httpStatus': status,
        'sessionId': new_session,
        'serverHeader': header_value(headers, 'server'),
        'body': body,
        'diagnostics': read_body_diagnostics(body),
    }


def assert_rpc_success(message, stage):
    if message is None:
        raise McpHttpError('%s returned no JSON-RPC response.' % stage)
    error_object = get_property(message, 'error')
    if error_object is not None:
        raise McpHttpError('%s returned a JSON-RPC error, code=%s.' % (stage, get_property(error_object, 'code')))
    if get_property(message, 'result') is None:
        raise McpHttpError('%s response has no result.' % stage)


def profile_enabled(profile):
    if not isinstance(profile, dict):
        raise ValueError('Each MCP connection entry must be an object.')
    for flag in ('disabled', 'enabled'):
        if flag in profile and not isinstance(profile[flag], bool):
            raise ValueError('Connection enable flags must be boolean.')
    return profile.get('disabled') is not True and profile.get('enabled') is not False


def expand_header_value(value):
    if not isinstance(value, str):
        value = str(value)
    match = ENV_HEADER_PATTERN.match(value)
    if match:
        name = match.group(1) or match.group(2)
        environment_value = os.environ.get(name)
        if environment_value is None or environment_value.strip() == '':
            raise ValueError("Environment variable '%s' referenced by an MCP header is not set." % name)
        return environment_value
    return value


def read_connection_profile(path, name):
    with open(path, 'r', encoding='utf-8') as handle:
        root = json.load(handle)
    container = root.get('mcpServers') if isinstance(root, dict) else None
    if container is None and isinstance(root, dict):
        container = root.get('servers')
    profile = root
    selected_name = name
    if container is not None:
        if not isinstance(container, dict):
            raise ValueError('The mcpServers/servers section must be an object.')
        enabled_profiles = {key: value for key, value in container.items() if profile_enabled(value)}
        if not selected_name or selected_name.strip() == '':
            if len(enabled_profiles) != 1:
                raise ValueError('The connection file contains multiple MCP servers. '
                                 'Select the active one with --connection-name.')
            selected_name = next(iter(enabled_profiles))
        if selected_name not in container:
            raise ValueError("MCP server '%s' does not exist in the active connection file." % selected_name)
        profile = container[selected_name]
    if not profile_enabled(profile):
        raise ValueError('The selected MCP connection is disabled. No request was sent.')
    if not selected_name or selected_name.strip() == '':
        selected_name = profile.get('name') or ''
    if not selected_name or selected_name.strip() == '':
        raise ValueError('A connection name is required for task binding and disclosure.')
    return selected_name, normalize_profile(selected_name, profile)


def normalize_profile(selected_name, profile):
    """Extract url, protocol and credentials from whatever shape the host config uses."""
    url = profile.get('url') or profile.get('endpoint') or profile.get('serverUrl')
    if not url or not isinstance(url, str) or url.strip() == '':
        raise ValueError('The active MCP connection has no url.')
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.netloc or (parts.username or parts.password):
        raise ValueError('Expected an HTTP(S) URL without embedded credentials.')

    declared = (profile.get('transport') or profile.get('type') or profile.get('protocol') or '').strip().lower()
    if declared in ('', 'streamable-http', 'streamablehttp', 'streamable', 'http'):
        transport = 'streamable-http'
    elif declared in ('sse', 'http+sse'):
        transport = 'sse'
    else:
        raise ValueError("Unsupported MCP transport '%s'. Supported: streamable-http, sse." % declared)

    headers = {}
    header_object = profile.get('headers')
    if header_object is not None:
        if not isinstance(header_object, dict):
            raise ValueError('The MCP connection headers must be an object.')
        for key, value in header_object.items():
            headers[key] = expand_header_value(value)

    # Credential may also live under apiKey/api_key, or in env as X_API_KEY / API_KEY.
    if not any(key.lower() in ('x-api-key', 'authorization') for key in headers):
        for candidate in ('apiKey', 'api_key', 'token'):
            value = profile.get(candidate)
            if isinstance(value, str) and value.strip():
                headers['X-API-Key'] = expand_header_value(value)
                break
        else:
            env_object = profile.get('env')
            if isinstance(env_object, dict):
                for key in ('X_API_KEY', 'API_KEY', 'MCP_API_KEY'):
                    value = env_object.get(key)
                    if isinstance(value, str) and value.strip():
                        headers['X-API-Key'] = expand_header_value(value)
                        break

    if transport == 'sse':
        raise ValueError(
            'The selected connection uses SSE. This helper speaks Streamable HTTP only; '
            'use the host native MCP tools for SSE connections.')

    fingerprint_parts = [selected_name, url, transport]
    for key in sorted(headers, key=lambda item: item.lower()):
        fingerprint_parts.append('%s:%s' % (key.lower(), headers[key]))
    fingerprint = sha256_text('\n'.join(fingerprint_parts))
    return url, headers, fingerprint


def config_search_paths(explicit_file):
    """Host MCP configuration locations, in priority order."""
    if explicit_file:
        return [explicit_file]
    paths = []
    override = os.environ.get('YOYUYUN_MCP_CONFIG') or os.environ.get('MCP_CONFIG_PATH')
    if override:
        paths.append(override)
    home = os.path.expanduser('~')
    appdata = os.environ.get('APPDATA') or ''
    candidates = [
        os.path.join(home, '.workbuddy', 'mcp.json'),
        os.path.join(home, '.codebuddy', 'mcp.json'),
        os.path.join(home, '.claude', 'mcp.json'),
        os.path.join(home, '.cursor', 'mcp.json'),
        os.path.join(home, '.config', 'mcp', 'mcp.json'),
    ]
    if appdata:
        candidates.insert(1, os.path.join(appdata, 'WorkBuddy', 'mcp.json'))
    candidates.extend([
        os.path.join(os.getcwd(), '.mcp.json'),
        os.path.join(os.getcwd(), '.workbuddy', 'mcp.json'),
    ])
    for candidate in candidates:
        if candidate and candidate not in paths:
            paths.append(candidate)
    return [path for path in paths if os.path.isfile(path)]


def collect_candidates(explicit_file, explicit_name):
    """All enabled HTTP(S) servers from the discovered config files."""
    files = config_search_paths(explicit_file)
    if not files:
        raise ValueError('No MCP configuration file was found. Point --connection-file at the file the '
                         'host uses, or set YOYUYUN_MCP_CONFIG.')
    candidates = []
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                root = json.load(handle)
        except (OSError, ValueError):
            continue
        container = root.get('mcpServers') if isinstance(root, dict) else None
        if container is None and isinstance(root, dict):
            container = root.get('servers')
        if not isinstance(container, dict):
            if isinstance(root, dict) and 'url' in root:
                container = {'(inline)': root}
            else:
                continue
        for name, profile in container.items():
            try:
                if not profile_enabled(profile):
                    continue
                if explicit_name and name != explicit_name:
                    continue
                url, headers, fingerprint = normalize_profile(name, profile)
            except ValueError:
                continue
            candidates.append({'file': path, 'name': name, 'url': url,
                               'headers': headers, 'fingerprint': fingerprint})
    return candidates


class Connection:
    def __init__(self, name, url, headers, fingerprint):
        self.name = name
        self.url = url
        self.headers = headers
        self.fingerprint = fingerprint


class Live:
    def __init__(self, http, session_id, tools, schema_hash, server_info, protocol_version):
        self.http = http
        self.session_id = session_id
        self.tools = tools
        self.schema_hash = schema_hash
        self.server_info = server_info
        self.protocol_version = protocol_version


def open_live(connection, tools_list_without_session, skip_initialized_notification):
    http = McpHttp(connection.url, connection.headers)
    initialize, initialize_id = new_payload('initialize', {
        'protocolVersion': '2025-06-18',
        'capabilities': {},
        'clientInfo': CLIENT_INFO,
    })
    message, session_id = invoke_mcp_request(http, initialize, None, initialize_id, None)
    assert_rpc_success(message, 'initialize')
    result = get_property(message, 'result')
    protocol_version = get_property(result, 'protocolVersion') or ''
    if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise McpHttpError('Unsupported negotiated Streamable HTTP protocol version.')
    server_info = get_property(result, 'serverInfo')

    if not skip_initialized_notification:
        notification, _ = new_payload('notifications/initialized', {}, notification=True)
        invoke_mcp_request(http, notification, session_id, None, protocol_version)

    discovery_session = None if tools_list_without_session else session_id
    list_request, list_id = new_payload('tools/list', {})
    # The tools/list response session header is deliberately discarded: the initialize session
    # stays the task session for every later request (matches the previous PS/sh behavior).
    message, _ = invoke_mcp_request(http, list_request, discovery_session, list_id, protocol_version)
    assert_rpc_success(message, 'tools/list')
    result = get_property(message, 'result')
    tools = list(result.get('tools') or [])
    if get_property(result, 'nextCursor'):
        raise McpHttpError('Unexpected pagination for the fixed three-tool MCP; stop rather than loop discovery.')

    names = sorted({tool.get('name') for tool in tools})
    missing = [tool for tool in REQUIRED_TOOLS if tool not in names]
    unexpected = [tool for tool in names if tool not in REQUIRED_TOOLS]
    if missing or unexpected or len(tools) != len(REQUIRED_TOOLS):
        raise McpHttpError('The active connection is not the expected three-tool report MCP. '
                       'missing=%s, unexpected=%s.' % (','.join(missing), ','.join(unexpected)))

    schema_hash = sha256_text(canonical(sorted(tools, key=lambda tool: tool.get('name') or '')))
    return Live(http, session_id, tools, schema_hash, server_info, protocol_version)


def assert_arguments_against_live_schema(tool, arguments):
    schema = get_property(tool, 'inputSchema')
    if schema is None:
        raise McpHttpError('The live tool definition has no inputSchema.')
    required = schema.get('required')
    if required:
        for name in required:
            if name not in arguments:
                raise McpHttpError("The live tool definition requires argument '%s'." % name)
    properties = schema.get('properties')
    if schema.get('additionalProperties') is False and properties is not None:
        for name in arguments:
            if name not in properties:
                raise McpHttpError("Argument '%s' is not present in the live inputSchema." % name)


def invoke_live_tool(live, name, arguments):
    matches = [tool for tool in live.tools if tool.get('name') == name]
    if len(matches) != 1:
        raise McpHttpError("The live tools/list does not contain exactly one '%s' tool." % name)
    assert_arguments_against_live_schema(matches[0], arguments)
    call, call_id = new_payload('tools/call', {'name': name, 'arguments': arguments})
    message, _ = invoke_mcp_request(live.http, call, live.session_id, call_id, live.protocol_version)
    assert_rpc_success(message, 'tools/call:%s' % name)
    return get_property(message, 'result')


def get_business_envelope(tool_result):
    structured = get_property(tool_result, 'structuredContent')
    if structured is not None:
        return structured
    content = get_property(tool_result, 'content') or []
    for item in content:
        if item.get('type') == 'text':
            try:
                return json.loads(item.get('text') or '')
            except ValueError:
                continue
    return None


def task_cache_directory(cache_root, task_id):
    return os.path.join(cache_root, sha256_text(task_id)[:24])


def write_atomic(path, text):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', dir=directory)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='') as stream:
            stream.write(text)
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def save_task_cache(cache_root, task_id, key, tool, arguments, tool_result, live, connection, fetched_at):
    data = {
        'toolName': tool,
        'argumentsHash': sha256_text(canonical(arguments)),
        'result': tool_result,
    }
    data_json = canonical(data)
    directory = task_cache_directory(cache_root, task_id)
    data_path = os.path.join(directory, '%s.data.json' % key)
    manifest_path = os.path.join(directory, '%s.manifest.json' % key)
    write_atomic(data_path, data_json)
    persisted_at = utc_now()
    manifest = {
        'cacheVersion': 1,
        'taskId': task_id,
        'cacheKey': key,
        'toolName': tool,
        'fetchedAtUtc': fetched_at.isoformat(),
        'persistedAtUtc': persisted_at.isoformat(),
        'persistedAtEpoch': int(persisted_at.timestamp()),
        'expiresAtUtc': (persisted_at + timedelta(minutes=CACHE_TTL_MINUTES)).isoformat(),
        'connectionFingerprint': connection.fingerprint,
        'liveToolSchemaHash': live.schema_hash,
        'dataSha256': sha256_text(data_json),
    }
    write_atomic(manifest_path, canonical(manifest))
    return manifest


def read_task_cache(cache_root, task_id, key, live, connection, allow_expired, options):
    directory = task_cache_directory(cache_root, task_id)
    data_path = os.path.join(directory, '%s.data.json' % key)
    manifest_path = os.path.join(directory, '%s.manifest.json' % key)
    if not os.path.isfile(data_path) or not os.path.isfile(manifest_path):
        raise McpHttpError("Cache '%s' does not exist for the current task." % key)
    with open(manifest_path, 'r', encoding='utf-8') as handle:
        manifest = json.load(handle)
    if manifest.get('taskId') != task_id:
        raise McpHttpError('Cache task ID mismatch. Cross-task cache use is forbidden.')
    if manifest.get('connectionFingerprint') != connection.fingerprint:
        raise McpHttpError('The cache belongs to another MCP connection and cannot be used.')
    if manifest.get('liveToolSchemaHash') != live.schema_hash:
        raise McpHttpError('The live MCP tool definitions changed. Refresh the data instead of using this cache.')
    persisted_at = datetime.fromisoformat(manifest.get('persistedAtUtc'))
    age_minutes = (utc_now() - persisted_at).total_seconds() / 60.0
    expired = age_minutes > CACHE_TTL_MINUTES
    if expired and not allow_expired:
        raise McpHttpError('The cache is older than 30 minutes (age %.2f minutes). Refresh the data.' % age_minutes)
    with open(data_path, 'r', encoding='utf-8') as handle:
        data_json = handle.read()
    if sha256_text(data_json) != manifest.get('dataSha256'):
        raise McpHttpError('Cache integrity validation failed.')
    return {
        'connectionName': connection.name,
        'toolsListWithoutSession': options.tools_list_without_session,
        'skipInitializedNotification': options.skip_initialized_notification,
        'cache': {
            'used': True,
            'stale': expired,
            'taskId': task_id,
            'cacheKey': key,
            'fetchedAtUtc': manifest.get('fetchedAtUtc'),
            'persistedAtUtc': manifest.get('persistedAtUtc'),
            'expiresAtUtc': manifest.get('expiresAtUtc'),
            'ageMinutes': round(age_minutes, 2),
            'ttlMinutes': CACHE_TTL_MINUTES,
        },
        'response': json.loads(data_json),
        'transportWarnings': live.http.events,
    }


def read_task_binding(cache_root, task_id):
    binding_path = os.path.join(task_cache_directory(cache_root, task_id), 'connection-binding.json')
    if not os.path.isfile(binding_path):
        return None
    try:
        with open(binding_path, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_task_binding(cache_root, task_id, connection, options):
    directory = task_cache_directory(cache_root, task_id)
    os.makedirs(directory, exist_ok=True)
    binding_path = os.path.join(directory, 'connection-binding.json')
    binding_value = canonical({
        'taskId': task_id,
        'connectionName': connection.name,
        'fingerprint': connection.fingerprint,
        'toolsListWithoutSession': options.tools_list_without_session,
        'skipInitializedNotification': options.skip_initialized_notification,
    })
    if os.path.exists(binding_path):
        with open(binding_path, 'r', encoding='utf-8') as handle:
            existing = handle.read()
        if existing != binding_value:
            raise McpHttpError('Task connection or compatibility mode changed. Stop; do not switch connections.')
    else:
        write_atomic(binding_path, binding_value)


def run_diagnose(connection):
    """Three fixed samples, at most nine HTTP requests, without request retries."""
    http = McpHttp(connection.url, connection.headers)
    samples = []
    distribution = {}
    server_info = None
    for sample_number in range(1, 4):
        steps = {}
        session_id = None
        protocol_version = None
        for method in ('initialize', 'notifications/initialized', 'tools/list'):
            params = {'protocolVersion': '2025-06-18', 'capabilities': {},
                      'clientInfo': CLIENT_INFO} if method == 'initialize' else {}
            payload, rpc_id = new_payload(method, params, method == 'notifications/initialized')
            started = utc_now().isoformat()
            observed = invoke_observed_request(http, payload, session_id, protocol_version)
            status = observed['httpStatus']
            steps[method] = {
                'httpStatus': status, 'startedAtUtc': started,
                'completedAtUtc': utc_now().isoformat(),
                'sessionIdFingerprint': sha256_text(session_id)[:16] if session_id else None,
                'sessionNotFound': bool(status == 404 and re.search(
                    r'\bsession\s+not\s+found\b', observed['body'], re.IGNORECASE)),
                'protocolVersion': protocol_version,
            }
            counts = distribution.setdefault(method, {})
            counts[str(status)] = counts.get(str(status), 0) + 1
            if method == 'initialize' and 200 <= status < 300:
                message = parse_mcp_body(observed['body'], rpc_id)
                assert_rpc_success(message, method)
                protocol_version = message['result'].get('protocolVersion')
                if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
                    raise McpHttpError('Unsupported negotiated Streamable HTTP protocol version.')
                session_id = observed['sessionId']
                server_info = message['result'].get('serverInfo')
                steps[method]['sessionIdFingerprint'] = sha256_text(session_id)[:16] if session_id else None
                steps[method]['protocolVersion'] = protocol_version
            elif method == 'tools/list' and 200 <= status < 300:
                message = parse_mcp_body(observed['body'], rpc_id)
                assert_rpc_success(message, method)
            elif not 200 <= status < 300 and not (status == 404 and session_id):
                samples.append({'sample': sample_number, 'steps': steps})
                return {'samples': samples, 'distribution': distribution}, 'stopped-on-error', server_info
        samples.append({'sample': sample_number, 'steps': steps})
        if sample_number < 3:
            time.sleep(SESSION_RETRY_DELAY)
    mixed = any(any(200 <= int(s) < 300 for s in counts) and
                any(not 200 <= int(s) < 300 for s in counts)
                for counts in distribution.values())
    outcome = 'intermittent-observed' if mixed else 'sample-complete'
    return {'samples': samples, 'distribution': distribution}, outcome, server_info


DIAGNOSE_INTERPRETATIONS = {    'intermittent-observed': 'Mixed success and failure observed. Correlate session fingerprints and '
                            'timestamps with gateway and instance logs; this does not establish the root cause.',
    'sample-complete': 'Three samples completed. Identical outcomes in a small sample do not prove '
                       'permanent health or a notification-only defect. Inspect per-method status counts.',
    'stopped-on-error': 'Sampling stopped on an error outside the session-404 diagnostic allowance. '
                        'Report the observed status; do not switch connections.',
}


def emit(value):
    sys.stdout.write(canonical(value) + '\n')


def summarize_envelope(tool_name, arguments, tool_result):
    """Compact business summary of a tool result for stdout.

    Full results (columns, rows, live tool schemas) can exceed terminal line
    limits, and wrapped/truncated stdout has caused field misreads (e.g.
    reportCode). Stdout therefore carries this summary only; the complete
    output is written to a file and referenced by fullOutputPath.
    """
    envelope = get_business_envelope(tool_result)
    if not isinstance(envelope, dict):
        return {'parse': 'none'}
    meta = envelope.get('meta') or {}
    application = meta.get('application') or {}
    data = envelope.get('data')
    summary = {
        'status': envelope.get('status'),
        'applicationDisplayName': application.get('displayName'),
    }
    if envelope.get('error'):
        summary['error'] = envelope.get('error')
    if tool_name == 'yzy_list_report_analyses':
        reports = data if isinstance(data, list) else []
        summary['catalogState'] = meta.get('catalogState')
        summary['reportCount'] = len(reports)
        summary['reports'] = [
            {'reportCode': item.get('reportCode'), 'name': item.get('name'),
             'sampleQuestions': (item.get('sampleQuestions') or [])[:2]}
            for item in reports if isinstance(item, dict)
        ]
    elif tool_name == 'yzy_describe_report_analysis':
        summary['reportCode'] = (arguments or {}).get('reportCode') if isinstance(arguments, dict) else None
        if isinstance(data, dict):
            summary['reportCode'] = summary['reportCode'] or data.get('code')
            summary['name'] = data.get('name')
            summary['logicalTable'] = data.get('logicalTable')
            summary['analysisDefinitionVersion'] = data.get('analysisDefinitionVersion')
            summary['columnCount'] = len(data.get('columns') or [])
            summary['parameterNames'] = [item.get('name') for item in (data.get('parameters') or [])]
            summary['metricCount'] = len(data.get('metrics') or [])
    elif tool_name == 'yzy_analyze_report':
        if isinstance(data, dict):
            summary['returnedRows'] = data.get('returnedRows')
            summary['resultLimited'] = data.get('resultLimited')
            summary['columns'] = [item.get('label') or item.get('name')
                                  for item in (data.get('columns') or [])]
            rows = data.get('rows') or []
            if len(rows) <= 50:
                summary['rows'] = rows
            else:
                summary['rowsPreview'] = rows[:20]
                summary['rowsTotal'] = len(rows)
            summary['effectiveArguments'] = data.get('effectiveArguments')
    if envelope.get('warnings'):
        summary['warnings'] = envelope.get('warnings')
    return summary


FULL_OUTPUT_EXCLUDED_KEYS = ('result', 'liveTools', 'response')


def emit_compact_with_file(output, cache_root, task_id, cache_key):
    """Write the full output to the task directory; print only the compact view."""
    directory = task_cache_directory(cache_root, task_id)
    os.makedirs(directory, exist_ok=True)
    full_path = os.path.join(directory, '%s.output.json' % cache_key)
    write_atomic(full_path, canonical(output))
    compact = {key: value for key, value in output.items()
               if key not in FULL_OUTPUT_EXCLUDED_KEYS}
    compact['fullOutputPath'] = full_path
    emit(compact)
    return compact


def select_connection(options):
    """Pick the report MCP from the host config without hand-passed parameters.

    Discovery is bounded: at most MAX_DISCOVERY_CANDIDATES enabled servers are
    handshaken once each, and only to identify which one exposes the fixed three
    report tools. This is capability discovery, not retry rotation: once chosen,
    the connection is bound to the task and never swapped.
    """
    explicit_file = options.connection_file
    if explicit_file and not os.path.isfile(explicit_file):
        raise ValueError('The connection file %s does not exist.' % explicit_file)

    candidates = collect_candidates(explicit_file, options.connection_name)
    if not candidates:
        raise ValueError('No enabled HTTP(S) MCP connection was found in the discovered configuration. '
                         'Check that the report MCP is configured and enabled.')
    if len(candidates) == 1:
        chosen = candidates[0]
        return Connection(chosen['name'], chosen['url'], chosen['headers'], chosen['fingerprint']), {
            'mode': 'config-single', 'file': chosen['file'], 'probed': []}, None

    probed = []
    for candidate in candidates[:MAX_DISCOVERY_CANDIDATES]:
        connection = Connection(candidate['name'], candidate['url'],
                                candidate['headers'], candidate['fingerprint'])
        try:
            live = open_live(connection, options.tools_list_without_session,
                             options.skip_initialized_notification)
        except (McpHttpError, TransportError) as error:
            probed.append({'name': candidate['name'], 'matched': False, 'reason': str(error)[:160]})
            continue
        names = {tool.get('name') for tool in live.tools}
        matched = set(REQUIRED_TOOLS).issubset(names)
        probed.append({'name': candidate['name'], 'matched': matched})
        if matched:
            return connection, {'mode': 'config-discovery', 'file': candidate['file'],
                                'probed': probed}, live
    raise ValueError('None of the enabled MCP connections exposes the required report tools (%s). '
                     'Probed: %s' % (', '.join(REQUIRED_TOOLS),
                                     ', '.join('%s=%s' % (item['name'], item['matched']) for item in probed)))


def main():
    parser = argparse.ArgumentParser(description='Unified report MCP client for the yozuyun analysis skill.')
    parser.add_argument('--action', required=True,
                        choices=['bootstrap', 'call', 'read-cache', 'cache-status', 'diagnose',
                                 'connections'])
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--connection-file')
    parser.add_argument('--connection-name')
    parser.add_argument('--tool-name')
    parser.add_argument('--arguments-json')
    parser.add_argument('--arguments-file')
    parser.add_argument('--expected-schema-hash')
    parser.add_argument('--tools-list-without-session', action='store_true')
    parser.add_argument('--skip-initialized-notification', action='store_true')
    parser.add_argument('--cache-key')
    parser.add_argument('--cache-root')
    parser.add_argument('--allow-expired-cache', action='store_true')
    options = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    if not TASK_ID_PATTERN.match(options.task_id):
        fail('Invalid task ID.')
    if options.cache_key and not CACHE_KEY_PATTERN.match(options.cache_key):
        fail('CacheKey must contain only letters, digits, dot, underscore, or hyphen and be at most 100 characters.')
    cache_root = options.cache_root or os.path.join(tempfile.gettempdir(), 'yozuyun-analysis-skill-cache')

    if options.action == 'connections':
        try:
            candidates = collect_candidates(options.connection_file, options.connection_name)
        except ValueError as error:
            fail(str(error))
        emit({
            'action': 'connections',
            'configFiles': config_search_paths(options.connection_file),
            'enabledConnections': [
                {'name': item['name'], 'url': item['url'], 'file': item['file'],
                 'headerNames': sorted(key for key in item['headers'])}
                for item in candidates
            ],
            'note': 'Credentials are never printed; only header names are listed.',
        })
        return

    try:
        existing_binding = read_task_binding(cache_root, options.task_id)
        preopened = None
        if existing_binding:
            bound_name = existing_binding.get('connectionName')
            matches = collect_candidates(options.connection_file, bound_name)
            if not matches:
                fail('This task is bound to connection %r, which is no longer present and enabled in the '
                     'MCP configuration. Do not switch connections mid-task.' % bound_name)
            chosen = matches[0]
            connection = Connection(chosen['name'], chosen['url'], chosen['headers'], chosen['fingerprint'])
            selection = {'mode': 'task-binding', 'file': chosen['file']}
            if connection.fingerprint != existing_binding.get('fingerprint'):
                fail('The credentials or endpoint of connection %r changed since this task started. '
                     'Start a new task after the configuration change.' % bound_name)
        else:
            connection, selection, preopened = select_connection(options)
    except ValueError as error:
        fail(str(error))
    except OSError as error:
        fail('The active MCP connection file cannot be read: %s' % error)

    write_task_binding(cache_root, options.task_id, connection, options)
    sys.stderr.write(
        'MCP connection: %s (via %s, %s); toolsListWithoutSession=%s; skipInitializedNotification=%s\n'
        % (connection.name, selection.get('mode'), selection.get('file'),
           str(options.tools_list_without_session).lower(),
           str(options.skip_initialized_notification).lower()))

    try:
        if options.action == 'diagnose':
            steps, outcome, server_info = run_diagnose(connection)
            emit({
                'connectionName': connection.name,
                'action': 'diagnose',
                'mode': 'standard-handshake',
                'completedAtUtc': utc_now().isoformat(),
                'outcome': outcome,
                'interpretation': DIAGNOSE_INTERPRETATIONS[outcome],
                'steps': steps,
                'serverInfo': server_info,
            })
            return

        live = preopened or open_live(connection, options.tools_list_without_session,
                                      options.skip_initialized_notification)

        if options.action == 'cache-status':
            entries = []
            directory = task_cache_directory(cache_root, options.task_id)
            if os.path.isdir(directory):
                for file_name in sorted(os.listdir(directory)):
                    if not file_name.endswith('.manifest.json'):
                        continue
                    try:
                        with open(os.path.join(directory, file_name), 'r', encoding='utf-8') as handle:
                            manifest = json.load(handle)
                        if manifest.get('taskId') != options.task_id:
                            continue
                        persisted_at = datetime.fromisoformat(manifest.get('persistedAtUtc'))
                        age = (utc_now() - persisted_at).total_seconds() / 60.0
                        entries.append({
                            'cacheKey': manifest.get('cacheKey'),
                            'toolName': manifest.get('toolName'),
                            'persistedAtUtc': manifest.get('persistedAtUtc'),
                            'ageMinutes': round(age, 2),
                            'usable': (age <= CACHE_TTL_MINUTES
                                       and manifest.get('connectionFingerprint') == connection.fingerprint
                                       and manifest.get('liveToolSchemaHash') == live.schema_hash),
                        })
                    except (ValueError, OSError):
                        continue
            emit({
                'connectionName': connection.name,
                'taskId': options.task_id,
                'ttlMinutes': CACHE_TTL_MINUTES,
                'entries': entries,
                'transportWarnings': live.http.events,
            })
            return

        if options.action == 'read-cache':
            if not options.cache_key:
                fail('read-cache requires --cache-key.')
            cached = read_task_cache(cache_root, options.task_id, options.cache_key, live, connection,
                                     options.allow_expired_cache, options)
            cached_response = cached.get('response') or {}
            cached['summary'] = summarize_envelope(cached_response.get('toolName'), None,
                                                   cached_response.get('result'))
            emit_compact_with_file(cached, cache_root, options.task_id, options.cache_key)
            return

        if options.action == 'bootstrap':
            tool_name = 'yzy_list_report_analyses'
            arguments = {}
            cache_key = 'catalog'
        else:
            if not options.tool_name:
                fail('call requires --tool-name.')
            if not options.expected_schema_hash:
                fail('call requires --expected-schema-hash from the current task bootstrap.')
            if options.expected_schema_hash != live.schema_hash:
                fail('The live MCP tool definitions changed. Run bootstrap again and rebuild the call '
                     'from the new schema.')
            tool_name = options.tool_name
            raw_arguments = options.arguments_json
            if options.arguments_file:
                try:
                    with open(options.arguments_file, 'r', encoding='utf-8') as handle:
                        raw_arguments = handle.read()
                except OSError as error:
                    fail('The arguments file cannot be read: %s' % error)
            try:
                arguments = json.loads(raw_arguments if raw_arguments is not None else '{}')
            except ValueError:
                fail('ArgumentsJson is not valid JSON. Pass a JSON object, or use --arguments-file '
                     'so shell quoting cannot corrupt it.')
            if not isinstance(arguments, dict):
                fail('ArgumentsJson must be a JSON object.')
            cache_key = options.cache_key or ('%s-%s' % (options.tool_name,
                                                         sha256_text(canonical(arguments))[:16]))

        tool_result = invoke_live_tool(live, tool_name, arguments)
        fetched_at = utc_now()
        envelope = get_business_envelope(tool_result)
        if envelope is None or envelope.get('status') != 'success':
            error_output = {
                'connectionName': connection.name,
                'toolsListWithoutSession': options.tools_list_without_session,
                'skipInitializedNotification': options.skip_initialized_notification,
                'source': 'live',
                'transportWarnings': live.http.events,
                'cache': {'used': False},
                'serverInfo': live.server_info,
                'liveToolSchemaHash': live.schema_hash,
                'summary': summarize_envelope(tool_name, arguments, tool_result),
                'result': tool_result,
            }
            if options.action == 'bootstrap':
                error_output['liveTools'] = [
                    {'name': tool.get('name'),
                     'inputSchema': tool.get('inputSchema'),
                     'outputSchema': tool.get('outputSchema')}
                    for tool in live.tools
                ]
            emit_compact_with_file(error_output, cache_root, options.task_id, cache_key)
            sys.exit(2)

        manifest = save_task_cache(cache_root, options.task_id, cache_key, tool_name, arguments,
                                   tool_result, live, connection, fetched_at)
        success_output = {
            'connectionName': connection.name,
            'toolsListWithoutSession': options.tools_list_without_session,
            'skipInitializedNotification': options.skip_initialized_notification,
            'protocolVersion': live.protocol_version,
            'transportWarnings': live.http.events,
            'source': 'live',
            'cache': {
                'used': False,
                'taskId': options.task_id,
                'cacheKey': cache_key,
                'persistedAtUtc': manifest['persistedAtUtc'],
                'expiresAtUtc': manifest['expiresAtUtc'],
                'ttlMinutes': CACHE_TTL_MINUTES,
            },
            'serverInfo': live.server_info,
            'liveToolSchemaHash': live.schema_hash,
            'summary': summarize_envelope(tool_name, arguments, tool_result),
            'result': tool_result,
        }
        if options.action == 'bootstrap':
            success_output['liveTools'] = [
                {'name': tool.get('name'),
                 'inputSchema': tool.get('inputSchema'),
                 'outputSchema': tool.get('outputSchema')}
                for tool in live.tools
            ]
        emit_compact_with_file(success_output, cache_root, options.task_id, cache_key)
    except McpHttpError as error:
        fail(str(error))
    except TransportError as error:
        fail(str(error))
    except ValueError as error:
        fail(str(error))
    except OSError as error:
        fail('Local cache operation failed: %s' % error)


if __name__ == '__main__':
    main()
