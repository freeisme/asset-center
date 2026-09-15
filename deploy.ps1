$scriptPath = Join-Path $PSScriptRoot "scripts\windows\deploy.ps1"
& $scriptPath @args
exit $LASTEXITCODE
