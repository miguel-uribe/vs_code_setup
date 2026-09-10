#!/usr/bin/env bash
# Lanzador para macOS y Linux. La logica real vive en setup_env.py.
set -euo pipefail
if ! command -v uv >/dev/null 2>&1; then
    echo "uv no esta instalado. Instalalo con:" >&2
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --script "$DIR/setup_env.py" "$@"
