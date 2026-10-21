param(
  [switch]$NoPull
)

$ErrorActionPreference = "Stop"

function Run-Git([string[]]$GitArgs) {
  $output = & git @GitArgs 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "git $($GitArgs -join ' ') failed: $($output -join [Environment]::NewLine)"
  }
  return @($output)
}

$root = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $root) {
  throw "Not inside a Git repository."
}

Set-Location ($root.Trim())
$machine = if ($env:COMPUTERNAME) { $env:COMPUTERNAME } else { [Environment]::MachineName }
$branch = ((Run-Git @("branch","--show-current")) -join "").Trim()

Write-Host "AI SAFE START"
Write-Host "Machine : $machine"
Write-Host "Repo    : $((Split-Path -Leaf (Get-Location)))"
Write-Host "Branch  : $branch"

Run-Git @("fetch","origin","--prune") | Out-Null

$dirty = @(& git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw "Unable to read git status." }

$upstream = (& git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $upstream) {
  $upstream = if ($branch -eq "main") { "origin/main" } else { "" }
}
$upstream = $upstream.Trim()

$ahead = 0
$behind = 0
if ($upstream) {
  $counts = ((Run-Git @("rev-list","--left-right","--count","HEAD...$upstream")) -join "").Trim() -split "\s+"
  if ($counts.Count -ge 2) {
    $ahead = [int]$counts[0]
    $behind = [int]$counts[1]
  }
}

Write-Host "Upstream: $upstream"
Write-Host "Ahead   : $ahead"
Write-Host "Behind  : $behind"
Write-Host "Dirty   : $($dirty.Count -gt 0)"

if ($dirty.Count -gt 0) {
  Write-Warning "Working tree has local changes. No automatic pull/reset/checkout was performed."
  & git status --short
  exit 0
}

if ($ahead -gt 0 -and $behind -gt 0) {
  Write-Warning "Local and remote have diverged. No destructive action was performed."
  exit 0
}

if (-not $NoPull -and $upstream -and $behind -gt 0 -and $ahead -eq 0) {
  Write-Host "Safe fast-forward detected. Pulling..."
  $remoteBranch = $upstream -replace "^origin/",""
  Run-Git @("pull","--ff-only","origin",$remoteBranch) | ForEach-Object { Write-Host $_ }
}

if ($ahead -gt 0) {
  Write-Warning "Local branch has unpushed commits. Push/checkpoint before handing off to another machine or executor."
}

Write-Host "SAFE_START_OK"
