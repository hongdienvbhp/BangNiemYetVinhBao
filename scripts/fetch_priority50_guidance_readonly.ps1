param(
  [string]$MasterPath = "data/thu-tuc.json",
  [string]$OutputPath = "data/source-audit/priority50-guidance-raw-current.json",
  [int]$Port = 9225,
  [int]$NavigationWaitMs = 500,
  [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$chrome = @(
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "Google Chrome not found." }

function Receive-CdpMessage([System.Net.WebSockets.ClientWebSocket]$Ws) {
  $buffer = New-Object byte[] 1048576
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
    ConvertTo-Json -Compress -Depth 12
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
  return $normalized.TrimEnd(".", " ").ToLowerInvariant()
}

function Get-PageSnapshot(
  [System.Net.WebSockets.ClientWebSocket]$Ws,
  [ref]$Id
) {
  $Id.Value++
  $expression = @'
JSON.stringify({
  title: document.title || "",
  url: location.href || "",
  text: document.body ? document.body.innerText : "",
  links: Array.from(document.querySelectorAll("a[href]")).map(a => ({
    text: (a.innerText || a.textContent || "").trim(),
    href: a.href || ""
  })).filter(x => x.href),
  tables: Array.from(document.querySelectorAll("table")).map((table, tableIndex) => ({
    index: tableIndex,
    rows: Array.from(table.querySelectorAll("tr")).map(tr =>
      Array.from(tr.querySelectorAll("th,td")).map(cell =>
        (cell.innerText || cell.textContent || "").replace(/\s+/g, " ").trim()
      )
    ).filter(row => row.length)
  })).filter(t => t.rows.length)
})
'@
  $evaluation = Invoke-Cdp $Ws $Id.Value "Runtime.evaluate" @{
    expression = $expression
    returnByValue = $true
  }
  $json = [string]$evaluation.result.result.value
  if (-not $json) { return $null }
  return ($json | ConvertFrom-Json)
}

function Navigate-And-Wait(
  [System.Net.WebSockets.ClientWebSocket]$Ws,
  [ref]$Id,
  [string]$Url,
  [int]$WaitMs,
  [string]$ReadyMarker = ""
) {
  $Id.Value++
  Invoke-Cdp $Ws $Id.Value "Page.navigate" @{ url = $Url } | Out-Null
  Start-Sleep -Milliseconds $WaitMs
  $payload = $null
  for ($poll = 0; $poll -lt 4; $poll++) {
    $payload = Get-PageSnapshot $Ws ([ref]$Id.Value)
    $body = [string]$payload.text
    if ($body -and -not $body.Contains("Request Rejected")) {
      if (-not $ReadyMarker -or (Normalize-Text $body).Contains((Normalize-Text $ReadyMarker))) {
        break
      }
      if ($body.Length -gt 1500) { break }
    }
    Start-Sleep -Milliseconds 350
  }
  return $payload
}

function Find-DetailLink([object]$Payload, [string]$ExpectedName, [string]$Code) {
  if (-not $Payload) { return "" }
  $expected = Normalize-Text $ExpectedName
  $best = ""
  foreach ($link in @($Payload.links)) {
    $href = [string]$link.href
    $text = Normalize-Text ([string]$link.text)
    if (-not $href) { continue }
    $isDetail = (
      $href.Contains("dvc-tthc-thu-tuc-hanh-chinh-chi-tiet") -or
      $href.Contains("dvc-chi-tiet-thu-tuc-dung-chung") -or
      $href.Contains("ma_thu_tuc=")
    )
    if (-not $isDetail) { continue }
    if ($text -and $expected -and ($text.Contains($expected) -or $expected.Contains($text))) {
      return $href
    }
    if ($text.Contains((Normalize-Text $Code))) { return $href }
    if (-not $best) { $best = $href }
  }
  return $best
}

$master = Get-Content -Raw -Encoding UTF8 $MasterPath | ConvertFrom-Json
$items = @($master.thuTuc | Where-Object { $_.priority51 -eq $true })
if ($items.Count -ne 50) { throw "Expected 50 active priority TTHC, found $($items.Count)." }
if ($Limit -gt 0) { $items = @($items | Select-Object -First $Limit) }

$profile = Join-Path $env:TEMP ("dvcqg-priority50-readonly-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $profile | Out-Null
$chromeProcess = $null
$ws = $null

try {
  $chromeProcess = Start-Process -FilePath $chrome -PassThru -ArgumentList @(
    "--headless=new",
    "--remote-debugging-port=$Port",
    "--user-data-dir=$profile",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-gpu",
    "about:blank"
  )

  $targets = $null
  for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
      $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json" -TimeoutSec 2
      if ($targets) { break }
    } catch {}
    Start-Sleep -Milliseconds 300
  }
  if (-not $targets) { throw "Chrome DevTools endpoint did not become ready." }

  $page = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
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
    $code = [string]$item.ma
    $expectedName = [string]$item.ten
    $localExecutionUrl = [string]$item.nopHoSoUrl
    $detailCandidates = @(
      "https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-hanh-chinh.html?ma_thu_tuc=$([Uri]::EscapeDataString($code))",
      "https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-dung-chung.html?ma_thu_tuc=$([Uri]::EscapeDataString($code))"
    )

    $detailPayload = $null
    $detailUrl = ""
    $status = "DETAIL_IDENTITY_UNRESOLVED"

    foreach ($candidate in $detailCandidates) {
      $payload = Navigate-And-Wait $ws ([ref]$id) $candidate $NavigationWaitMs $expectedName
      $bodyText = [string]$payload.text
      if ($bodyText.Contains("Request Rejected")) {
        $status = "WAF_REJECTED_DETAIL"
        continue
      }

      $normalizedBody = Normalize-Text $bodyText
      $nameVisible = $false
      if ($expectedName) {
        $nameVisible = $normalizedBody.Contains((Normalize-Text $expectedName))
      }
      $codeVisible = $normalizedBody.Contains((Normalize-Text $code))
      if ($nameVisible -or $codeVisible) {
        $detailPayload = $payload
        $detailUrl = [string]$payload.url
        if (-not $detailUrl) { $detailUrl = $candidate }
        $status = "DETAIL_CAPTURED"
        break
      }

      if (-not $detailPayload) {
        $detailPayload = $payload
        $detailUrl = [string]$payload.url
        if (-not $detailUrl) { $detailUrl = $candidate }
      }
    }

    $sourcePayload = $detailPayload
    $results.Add([pscustomobject]@{
      code = $code
      expectedName = $expectedName
      field = [string]$item.linhVuc
      formalityId = [string]$item.formalityId
      localExecutionUrl = $localExecutionUrl
      detailUrl = $detailUrl
      renderedUrl = [string]$sourcePayload.url
      pageTitle = [string]$sourcePayload.title
      status = $status
      bodyText = [string]$sourcePayload.text
      tables = @($sourcePayload.tables)
    })
  }

  [object[]]$resultArray = @($results | ForEach-Object { $_ })
  $now = (Get-Date).ToUniversalTime().ToString("o")
  $manifest = [ordered]@{
    format = "DVCQG_PRIORITY50_GUIDANCE_RAW"
    version = 1
    capturedAt = $now
    source = "https://dichvucong.gov.vn/"
    securityScope = "Temporary headless Chrome profile; public rendered DOM only; no login, credentials, cookies, localStorage, citizen dossiers, submissions, or write-back captured."
    targetCount = $items.Count
    totals = [ordered]@{
      detailCaptured = ($resultArray | Where-Object { $_.status -eq "DETAIL_CAPTURED" } | Measure-Object).Count
      unresolved = ($resultArray | Where-Object { $_.status -like "*UNRESOLVED*" -or $_.status -eq "DETAIL_LINK_NOT_FOUND" } | Measure-Object).Count
      wafRejected = ($resultArray | Where-Object { $_.status -like "WAF_REJECTED*" } | Measure-Object).Count
    }
    items = $resultArray
  }

  $parent = Split-Path -Parent $OutputPath
  if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  $manifest | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $OutputPath
  $manifest.totals | ConvertTo-Json -Compress
}
finally {
  if ($ws) { $ws.Dispose() }
  if ($chromeProcess -and -not $chromeProcess.HasExited) {
    Stop-Process -Id $chromeProcess.Id -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Milliseconds 300
  Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}
