#!/usr/bin/env bash
# O frontend usa sua própria porta e comunica-se pela API configurada.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm start
