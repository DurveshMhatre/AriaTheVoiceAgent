$ErrorActionPreference = 'Stop'
$patterns = @('AIza[0-9A-Za-z_-]{20,}', 'gsk_[0-9A-Za-z_-]{20,}', 'sk-[0-9A-Za-z_-]{20,}', 'LIVEKIT_API_SECRET[ =]+[A-Za-z0-9_-]{8,}', 'SARVAM_API_KEY[ =]+[A-Za-z0-9_-]{8,}', 'GEMINI_API_KEY[ =]+[A-Za-z0-9_-]{8,}', 'GROQ_API_KEY[ =]+[A-Za-z0-9_-]{8,}', 'SUPABASE_SERVICE_ROLE_KEY[ =]+[A-Za-z0-9_-]{8,}')
$regex = ($patterns -join '|')
$gitArgs = @('-c', "safe.directory=$((Get-Location).Path)")
$hits = @()
$tracked = git @gitArgs ls-files
foreach ($file in $tracked) {
  if (Test-Path -LiteralPath $file) {
    $content = Get-Content -Raw -LiteralPath $file
    if ($content -match $regex) { $hits += "working-tree:$file" }
  }
}
$commits = git @gitArgs rev-list --all
foreach ($commit in $commits) {
  $matches = git @gitArgs grep -I -i -l -E $regex $commit -- 2>$null
  foreach ($file in $matches) { $hits += "history:${commit}:$file" }
}
if ($hits.Count -gt 0) {
  $hits | Sort-Object -Unique | ForEach-Object { Write-Output $_ }
  Write-Output "FAIL secret-pattern hits: $($hits.Count)"
  exit 1
}
Write-Output "PASS secret scan: $($tracked.Count) tracked files and $($commits.Count) commits checked"
