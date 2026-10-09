#!/usr/bin/env bash
# Um terminal mantém frontend e backend em execução.
set -euo pipefail
exec node "$(dirname "$0")/start-dev.mjs"
