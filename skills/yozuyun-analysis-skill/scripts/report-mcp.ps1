[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('bootstrap', 'call', 'read-cache', 'cache-status', 'diagnose', 'connections')]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$')]
    [string]$TaskId,

    [string]$ConnectionFile,
    [string]$ConnectionName,
    [string]$ToolName,
    [string]$ArgumentsJson = '{}',
    [string]$ArgumentsFile,
    [string]$ExpectedSchemaHash,
    [switch]$ToolsListWithoutSession,
    [switch]$SkipInitializedNotification,
    [string]$CacheKey,
    [string]$CacheRoot,
    [switch]$AllowExpiredCache
)

# Thin Windows launcher: all protocol, cache, and diagnosis logic lives in report_mcp.py
# so Windows and macOS share one implementation. Uses the system PowerShell 5.1 only to
# locate a suitable Python 3.8+ interpreter and forward arguments.
#
# Connection details (url, transport, X-API-Key) are NOT parameters here: the Python core
# discovers them from the host MCP configuration. Pass -ConnectionFile/-ConnectionName only
# to override that discovery.

$ErrorActionPreference = 'Stop'
$core = Join-Path $PSScriptRoot 'report_mcp.py'
if (-not (Test-Path -LiteralPath $core -PathType Leaf)) {
    Write-Error "Core script not found: $core"
    exit 1
}

$versionProbe = 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'
$pythonCommand = $null
foreach ($candidate in @(@('py', '-3'), @('python'), @('python3'))) {
    $exe = $candidate[0]
    $pre = @()
    if ($candidate.Count -gt 1) { $pre = $candidate[1..($candidate.Count - 1)] }
    $resolved = Get-Command $exe -ErrorAction SilentlyContinue
    if ($null -eq $resolved) { continue }
    try {
        & $resolved.Source @pre -c $versionProbe 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pythonCommand = @{ Exe = $resolved.Source; Pre = $pre }
            break
        }
    }
    catch { continue }
}

if ($null -eq $pythonCommand) {
    Write-Error 'Python 3.8+ is required to run the report MCP client. Install Python from python.org (pip packages are NOT required), then retry. Do not switch MCP connections.'
    exit 1
}

$forwarded = @(
    $core,
    '--action', $Action,
    '--task-id', $TaskId
)
if (-not [string]::IsNullOrWhiteSpace($ConnectionFile)) { $forwarded += @('--connection-file', $ConnectionFile) }
if (-not [string]::IsNullOrWhiteSpace($ConnectionName)) { $forwarded += @('--connection-name', $ConnectionName) }
if (-not [string]::IsNullOrWhiteSpace($ToolName)) { $forwarded += @('--tool-name', $ToolName) }
# ArgumentsJson must reach Python byte-for-byte. Nested shells and callers
# frequently strip or double the inner quotes, so accept a file path as well.
if (-not [string]::IsNullOrWhiteSpace($ArgumentsJson)) {
    if ((Test-Path -LiteralPath $ArgumentsJson -PathType Leaf)) {
        $ArgumentsJson = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $ArgumentsJson).Path)
    }
    $forwarded += @('--arguments-json', $ArgumentsJson)
}
if (-not [string]::IsNullOrWhiteSpace($ArgumentsFile)) {
    if (-not (Test-Path -LiteralPath $ArgumentsFile -PathType Leaf)) {
        Write-Error "Arguments file not found: $ArgumentsFile"
        exit 1
    }
    $forwarded += @('--arguments-file', (Resolve-Path -LiteralPath $ArgumentsFile).Path)
}
if (-not [string]::IsNullOrWhiteSpace($ExpectedSchemaHash)) { $forwarded += @('--expected-schema-hash', $ExpectedSchemaHash) }
if ($ToolsListWithoutSession) { $forwarded += '--tools-list-without-session' }
if ($SkipInitializedNotification) { $forwarded += '--skip-initialized-notification' }
if (-not [string]::IsNullOrWhiteSpace($CacheKey)) { $forwarded += @('--cache-key', $CacheKey) }
if (-not [string]::IsNullOrWhiteSpace($CacheRoot)) { $forwarded += @('--cache-root', $CacheRoot) }
if ($AllowExpiredCache) { $forwarded += '--allow-expired-cache' }

& $pythonCommand.Exe @($pythonCommand.Pre + $forwarded)
exit $LASTEXITCODE
