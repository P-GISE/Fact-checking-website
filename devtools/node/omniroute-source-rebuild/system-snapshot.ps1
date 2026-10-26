$ErrorActionPreference = 'Stop'
$system = Get-CimInstance Win32_OperatingSystem
$rows = @(Get-CimInstance Win32_Process | ForEach-Object {
  @{ pid = [int]$_.ProcessId; parent = [int]$_.ParentProcessId; born = $_.CreationDate.ToUniversalTime().Ticks.ToString(); node = ($_.Name -eq 'node.exe') }
})
@{ freeBytes = [double]$system.FreePhysicalMemory * 1024; totalBytes = [double]$system.TotalVisibleMemorySize * 1024; rows = $rows } | ConvertTo-Json -Depth 4 -Compress
