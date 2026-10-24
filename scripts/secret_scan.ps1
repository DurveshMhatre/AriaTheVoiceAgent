$ErrorActionPreference = 'Stop'
$patterns = @('AIza[0-9A-Za-z_-]{20,}', 'gsk_[0-9A-Za-z_-]{20,}', 'sk-[0-9A-Za-z_-]{20,}', '(?i)LIVEKIT_API_SECRET[ \t]*=[ \t]*[^\r\n\s$]{8,}', '(?i)SARVAM_API_KEY[ \t]*=[ \t]*[^\r\n\s$]{8,}', '(?i)GEMINI_API_KEY[ \t]*=[ \t]*[^\r\n\s$]{8,}', '(?i)GROQ_API_KEY[ \t]*=[ \t]*[^\r\n\s$]{8,}', '(?i)SUPABASE_SERVICE_ROLE_KEY[ \t]*=[ \t]*[^\r\n\s$]{8,}')
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
  $files = git @gitArgs diff-tree --no-commit-id --name-only -r $commit
  foreach ($file in $files) {
    $content = git @gitArgs show "${commit}:$file" 2>$null
    if ($LASTEXITCODE -eq 0 -and $content -match $regex) { $hits += "history:${commit}:$file" }
  }
}
if ($hits.Count -gt 0) {
  $hits | Sort-Object -Unique | ForEach-Object { Write-Output $_ }
  Write-Output "FAIL secret-pattern hits: $($hits.Count)"
  exit 1
}
Write-Output "PASS secret scan: $($tracked.Count) tracked files and $($commits.Count) commits checked"
