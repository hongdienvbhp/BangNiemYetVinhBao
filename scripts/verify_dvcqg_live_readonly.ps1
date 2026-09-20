param(
  [string]$CrosswalkPath = "data/priority-51-crosswalk.json",
  [string]$OutputPath = "data/source-audit/dvcqg-live-verification-current.json",
  [int]$Port = 9224,
  [int]$NavigationWaitMs = 900,
  [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$chrome = @(
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "Google Chrome not found." }

function Receive-CdpMessage([System.Net.WebSockets.ClientWebSocket]$Ws) {
  $buffer = New-Object byte[] 262144
  $stream = New-Object System.IO.MemoryStream
  do {
    $result = $Ws.ReceiveAsync(
      [ArraySegment[byte]]::new($buffer),
      [Threading.CancellationToken]::None
    ).GetAwaiter().GetResult()
    $stream.Write($buffer, 0, $result.Count)
  } while (-not $result.EndOfMessage)
  [Text.Encoding]::UTF8.GetString($stream.ToArray())
}

function Invoke-Cdp(
  [System.Net.WebSockets.ClientWebSocket]$Ws,
  [int]$Id,
  [string]$Method,
  [hashtable]$Params
) {
  $message = @{ id = $Id; method = $Method; params = $Params } |
    ConvertTo-Json -Compress -Depth 10
  $bytes = [Text.Encoding]::UTF8.GetBytes($message)
  $Ws.SendAsync(
    [ArraySegment[byte]]::new($bytes),
    [Net.WebSockets.WebSocketMessageType]::Text,
    $true,
    [Threading.CancellationToken]::None
  ).GetAwaiter().GetResult() | Out-Null

  while ($true) {
    $raw = Receive-CdpMessage $Ws
    $parsed = $raw | ConvertFrom-Json
    if ($parsed.id -eq $Id) { return $parsed }
  }
}

function Normalize-Text([string]$Value) {
  if ($null -eq $Value) { return "" }
  $normalized = $Value.Normalize([Text.NormalizationForm]::FormC)
  $normalized = [regex]::Replace($normalized, "\s+", " ").Trim()
  $normalized = $normalized.TrimEnd(".", " ")
  return $normalized.ToLowerInvariant()
}

$crosswalk = Get-Content -Raw -Encoding UTF8 $CrosswalkPath | ConvertFrom-Json
$items = @($crosswalk.items)
if ($items.Count -ne 51) { throw "Expected 51 priority procedures, found $($items.Count)." }
if ($Limit -gt 0) { $items = @($items | Select-Object -First $Limit) }

$profile = Join-Path $env:TEMP ("dvcqg-readonly-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $profile | Out-Null
$chromeProcess = $null
$ws = $null

try {
  $chromeProcess = Start-Process -FilePath $chrome -PassThru -ArgumentList @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$profile",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--new-window",
    "about:blank"
  )

  $targets = $null
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
      $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json" -TimeoutSec 2
      if ($targets) { break }
    } catch {}
    Start-Sleep -Milliseconds 300
  }
  if (-not $targets) { throw "Chrome DevTools endpoint did not become ready." }

  $page = $targets |
    Where-Object { $_.type -eq "page" -and $_.url -eq "about:blank" } |
    Select-Object -First 1
  if (-not $page) {
    $page = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
  }
  if (-not $page) { throw "No Chrome page target found." }

  $ws = [Net.WebSockets.ClientWebSocket]::new()
  $ws.ConnectAsync(
    [Uri]$page.webSocketDebuggerUrl,
    [Threading.CancellationToken]::None
  ).GetAwaiter().GetResult() | Out-Null

  $id = 1
  Invoke-Cdp $ws $id "Page.enable" @{} | Out-Null
  $results = New-Object System.Collections.Generic.List[object]

  foreach ($item in $items) {
    $id++
    Invoke-Cdp $ws $id "Page.navigate" @{ url = [string]$item.dvcUrl } | Out-Null
    Start-Sleep -Milliseconds $NavigationWaitMs

    $payload = $null
    for ($poll = 0; $poll -lt 6; $poll++) {
      $id++
      $expression = @'
JSON.stringify({
  title: document.title || "",
  url: location.href || "",
  text: document.body ? document.body.innerText : "",
  links: Array.from(document.querySelectorAll("a[href]")).map(a => ({
    text: (a.innerText || "").trim(),
    href: a.href || ""
  })).filter(x => x.href)
})
'@
      $evaluation = Invoke-Cdp $ws $id "Runtime.evaluate" @{
        expression = $expression
        returnByValue = $true
      }
      $json = [string]$evaluation.result.result.value
      if ($json) { $payload = $json | ConvertFrom-Json }

      $body = [string]$payload.text
      if ($body -and
          -not $body.Contains("Request Rejected") -and
          ($body.Contains([string]$item.name) -or $body.Length -gt 700)) {
        break
      }
      Start-Sleep -Milliseconds 700
    }

    $bodyText = [string]$payload.text
    $normalizedBody = Normalize-Text $bodyText
    $normalizedExpected = Normalize-Text ([string]$item.name)
    $nameVisible = $false
    if ($normalizedExpected) {
      $nameVisible = $normalizedBody.Contains($normalizedExpected)
    }

    $agencyVisible =
      $normalizedBody.Contains((Normalize-Text "UBND xã Vĩnh Bảo")) -or
      $normalizedBody.Contains((Normalize-Text "Ủy ban nhân dân xã Vĩnh Bảo"))

    $wafRejected = $bodyText.Contains("Request Rejected")
    $extractedIds = New-Object System.Collections.Generic.HashSet[string]
    foreach ($link in @($payload.links)) {
      $href = [string]$link.href
      if ($href -match "[?&]formalityId=([^&]+)") {
        [void]$extractedIds.Add([Uri]::UnescapeDataString($matches[1]))
      }
    }
    if ([string]$payload.url -match "[?&]formalityId=([^&]+)") {
      [void]$extractedIds.Add([Uri]::UnescapeDataString($matches[1]))
    }

    $mode = [string]$item.mappingMode
    $status =
      if ($wafRejected) { "WAF_REJECTED" }
      elseif ($nameVisible -and $agencyVisible) { "VERIFIED_VISIBLE_IDENTITY_AND_AGENCY" }
      elseif ($nameVisible) { "VERIFIED_VISIBLE_IDENTITY" }
      else { "UNRESOLVED_VISIBLE_IDENTITY" }

    $results.Add([pscustomobject]@{
      ordinal = [int]$item.ordinal
      code = [string]$item.code
      expected_name = [string]$item.name
      mapping_mode = $mode
      stored_formality_id = [string]$item.formalityId
      requested_url = [string]$item.dvcUrl
      rendered_url = [string]$payload.url
      page_title = [string]$payload.title
      name_visible = [bool]$nameVisible
      vinh_bao_agency_visible = [bool]$agencyVisible
      extracted_formality_ids = [string[]]($extractedIds | ForEach-Object { [string]$_ })
      result = $status
    })
  }

  [object[]]$resultArray = @($results | ForEach-Object { $_ })
  $now = (Get-Date).ToUniversalTime().ToString("o")
  $manifest = [ordered]@{
    format = "DVCQG_LIVE_READONLY_VERIFICATION"
    version = 1
    verified_at = $now
    scope = "51 priority TTHC technical/public identity verification"
    source = "https://dichvucong.gov.vn/"
    security_scope = "Temporary Chrome profile; public rendered DOM only; no cookies, localStorage, credentials, tokens, citizen dossiers, submissions, or write-back captured."
    legal_status_policy = "DVCQG identity/display evidence is technical only. Legal/effective status remains determined by official competent-authority evidence."
    totals = [ordered]@{
      items = $resultArray.Count
      verified_identity_and_agency = ($resultArray | Where-Object { $_.result -eq "VERIFIED_VISIBLE_IDENTITY_AND_AGENCY" } | Measure-Object).Count
      verified_identity_only = ($resultArray | Where-Object { $_.result -eq "VERIFIED_VISIBLE_IDENTITY" } | Measure-Object).Count
      unresolved = ($resultArray | Where-Object { $_.result -eq "UNRESOLVED_VISIBLE_IDENTITY" } | Measure-Object).Count
      waf_rejected = ($resultArray | Where-Object { $_.result -eq "WAF_REJECTED" } | Measure-Object).Count
    }
    items = $resultArray
  }

  $parent = Split-Path -Parent $OutputPath
  if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  $manifest | ConvertTo-Json -Depth 8 |
    Set-Content -Encoding UTF8 $OutputPath

  $manifest.totals | ConvertTo-Json -Compress
  $resultArray |
    Where-Object { $_.result -notlike "VERIFIED*" -or $_.mapping_mode -ne "formality_id" } |
    Select-Object ordinal,code,mapping_mode,stored_formality_id,name_visible,vinh_bao_agency_visible,extracted_formality_ids,result |
    ConvertTo-Json -Depth 5
}
finally {
  if ($ws) { $ws.Dispose() }
  if ($chromeProcess -and -not $chromeProcess.HasExited) {
    Stop-Process -Id $chromeProcess.Id -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Milliseconds 300
  Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}
