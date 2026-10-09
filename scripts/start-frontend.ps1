# Inicia somente a interface Angular.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\frontend')
npm start
exit $LASTEXITCODE
