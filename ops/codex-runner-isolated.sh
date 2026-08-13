#!/bin/sh
# Run the n8n Codex node without inheriting the host user's interactive
# plugins/MCP configuration. The node invokes this program as `... exec ...`.
set -eu

CODEX_JS=/home/node/.n8n/nodes/node_modules/@openai/codex/bin/codex.js

if [ "${1:-}" = "exec" ]; then
  shift
  exec node "$CODEX_JS" exec --ignore-user-config -c reasoning_effort='"high"' "$@"
fi

exec node "$CODEX_JS" "$@"
