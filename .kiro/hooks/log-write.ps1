# Kiro postToolUse hook: appends an audit line for every file write.
# Reads the hook JSON event from STDIN and logs to kiro_change_logs/_audit.log
$ErrorActionPreference = 'SilentlyContinue'

$raw = [Console]::In.ReadToEnd()
$evt = $null
try { $evt = $raw | ConvertFrom-Json } catch { }

$root = Get-Location
$dir  = Join-Path $root 'kiro_change_logs'
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$toolName = if ($evt -and $evt.tool_name) { $evt.tool_name } else { 'unknown' }

# Try to extract the file path that was written, if present.
$path = $null
if ($evt -and $evt.tool_input) {
    if ($evt.tool_input.path) { $path = $evt.tool_input.path }
}

$stamp = (Get-Date).ToString('o')
$line  = "$stamp  tool=$toolName  path=$path"
Add-Content -Path (Join-Path $dir '_audit.log') -Value $line

exit 0
