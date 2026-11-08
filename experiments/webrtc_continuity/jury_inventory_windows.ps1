# Read local OS state only. No ICMP, sockets, DNS, firewall or route modification.
$ErrorActionPreference = 'Stop'
try {
  $root = Join-Path $env:USERPROFILE 'SmartConnectPrivate'
  [IO.Directory]::CreateDirectory($root) | Out-Null
  $started = [DateTime]::UtcNow
  $label = $started.ToString('yyyyMMddTHHmmssZ')
  $history = Join-Path $root ('PRIVATE-inventory-B-' + $label + '.jsonl')
  $current = Join-Path $root 'current-interfaces.json'
  $encoding = New-Object Text.UTF8Encoding($false)
  Write-Host 'Read-only local inventory running for at most 420 seconds. No addresses printed.'
  Write-Host 'In SmartConnect, link SmartConnectPrivate/current-interfaces.json before recording.'
  while (([DateTime]::UtcNow - $started).TotalSeconds -lt 420) {
    $interfaces = @()
    $adapters = @(Get-NetAdapter -IncludeHidden)
    foreach ($adapter in $adapters) {
      $network = 'unknown'
      if ($adapter.NdisPhysicalMedium -in @(1,9)) { $network = 'wifi' }
      elseif ($adapter.NdisPhysicalMedium -eq 14) { $network = 'ethernet' }
      elseif ($adapter.NdisPhysicalMedium -eq 8) { $network = 'cellular' }
      $addresses = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue | ForEach-Object { $_.IPAddress })
      $interfaces += @{ id=('adapter-' + $adapter.ifIndex); index=[int]$adapter.ifIndex; active=($adapter.Status -eq 'Up'); network=$network; addresses=$addresses }
    }
    $row = @{schema=1;kind='interface_inventory';platform='windows';role='B';captured_at=[DateTime]::UtcNow.ToString('o');interfaces=$interfaces}
    $json = ConvertTo-Json -InputObject $row -Depth 6 -Compress
    [IO.File]::WriteAllText($current,$json,$encoding)
    [IO.File]::AppendAllText($history,$json + [Environment]::NewLine,$encoding)
    Start-Sleep -Seconds 5
  }
  Write-Host 'Inventory finished. Keep the private history off the presentation screen.'
} catch { Write-Host 'Local inventory unavailable; private details suppressed. Do not disable security settings.'; exit 1 }
