# Um terminal mantém frontend e backend em execução.
$ErrorActionPreference = 'Stop'
& node (Join-Path $PSScriptRoot 'start-dev.mjs')
exit $LASTEXITCODE
