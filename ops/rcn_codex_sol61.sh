#!/bin/sh
# RCN-only runtime; preserve the shared Codex installation used by other jobs.
set -eu
CODEX_JS=/home/node/.n8n/codex/rcn-runtime-0.162.1/node_modules/@openai/codex/bin/codex.js
if [ "${1:-}" = "exec" ]; then
  shift
  exec node "$CODEX_JS" exec "$@" -c model_reasoning_effort='"high"'
fi
exec node "$CODEX_JS" "$@"
