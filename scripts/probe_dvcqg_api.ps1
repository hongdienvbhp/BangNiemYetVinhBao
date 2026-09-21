param(
  [string]$MasterPath = "data/thu-tuc.json",
  [int]$Port = 9227
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
    $result = $Ws.ReceiveAsync([ArraySegment[byte]]::new($buffer), [Threading.CancellationToken]::None).GetAwaiter().GetResult()
    $stream.Write($buffer, 0, $result.Count)
  } while (-not $result.EndOfMessage)
  [Text.Encoding]::UTF8.GetString($stream.ToArray())
}
function Invoke-Cdp([System.Net.WebSockets.ClientWebSocket]$Ws,[int]$Id,[string]$Method,[hashtable]$Params) {
  $message = @{id=$Id;method=$Method;params=$Params} | ConvertTo-Json -Compress -Depth 12
  $bytes=[Text.Encoding]::UTF8.GetBytes($message)
  $Ws.SendAsync([ArraySegment[byte]]::new($bytes),[Net.WebSockets.WebSocketMessageType]::Text,$true,[Threading.CancellationToken]::None).GetAwaiter().GetResult()|Out-Null
  while($true){$raw=Receive-CdpMessage $Ws;$parsed=$raw|ConvertFrom-Json;if($parsed.id -eq $Id){return $parsed}}
}

$master=Get-Content -Raw -Encoding UTF8 $MasterPath|ConvertFrom-Json
$item=@($master.thuTuc|Where-Object{$_.priority51 -eq $true -and $_.formalityId}|Select-Object -First 1)[0]
$url=[string]$item.nopHoSoUrl
$profile=Join-Path $env:TEMP ("dvcqg-api-probe-"+[guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $profile|Out-Null
$p=$null;$ws=$null
try {
  $p=Start-Process -FilePath $chrome -PassThru -ArgumentList @("--headless=new","--remote-debugging-port=$Port","--user-data-dir=$profile","--no-first-run","--disable-extensions","about:blank")
  $targets=$null
  for($i=0;$i-lt 30;$i++){try{$targets=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json" -TimeoutSec 2;if($targets){break}}catch{};Start-Sleep -Milliseconds 250}
  $page=$targets|Where-Object{$_.type-eq"page"}|Select-Object -First 1
  $ws=[Net.WebSockets.ClientWebSocket]::new()
  $ws.ConnectAsync([Uri]$page.webSocketDebuggerUrl,[Threading.CancellationToken]::None).GetAwaiter().GetResult()|Out-Null
  $id=1
  Invoke-Cdp $ws $id "Page.enable" @{}|Out-Null
  $id++;Invoke-Cdp $ws $id "Network.enable" @{}|Out-Null
  $id++;Invoke-Cdp $ws $id "Page.navigate" @{url=$url}|Out-Null
  Start-Sleep -Seconds 7
  $id++
  $expr=@'
JSON.stringify({
  href: location.href,
  title: document.title,
  resources: performance.getEntriesByType("resource").map(r=>r.name)
    .filter(u => /api|formal|procedure|tthc|thu-tuc|service/i.test(u)),
  scripts: Array.from(document.scripts).map(s=>s.src).filter(Boolean)
})
'@
  $eval=Invoke-Cdp $ws $id "Runtime.evaluate" @{expression=$expr;returnByValue=$true}
  [string]$eval.result.result.value
}
finally {
  if($ws){$ws.Dispose()}
  if($p -and -not $p.HasExited){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}
  Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}
