#!/bin/sh

# Thin macOS launcher: all protocol, cache, and diagnosis logic lives in report_mcp.py
# so Windows and macOS share one implementation. Uses the system /bin/sh only to locate
# a suitable Python 3.8+ interpreter and forward arguments verbatim.

set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CORE="$DIR/report_mcp.py"
[ -f "$CORE" ] || { printf '%s\n' "Core script not found: $CORE" >&2; exit 1; }

PYTHON=''
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  printf '%s\n' 'Python 3.8+ is required to run the report MCP client. Install Python 3 (pip packages are NOT required), then retry. Do not switch MCP connections.' >&2
  exit 1
fi

exec "$PYTHON" "$CORE" "$@"
