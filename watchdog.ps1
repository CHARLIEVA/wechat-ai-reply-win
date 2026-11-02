# watchdog.ps1 - restarts the bot when its heartbeat is stale (hung) or its process is gone.
# 看门狗：心跳超时（卡死）或进程消失时重启机器人。
#
# - Checks every 30s; heartbeat older than WD_STALE_SEC (default 300s) => restart via run_bot.bat
#   (proxy variables cleared).  每 30 秒检查一次；心跳超过 WD_STALE_SEC（默认 300 秒）就用 run_bot.bat 重启（清空代理变量）。
# - Cooldown 300s between restarts, doubling up to 1800s if restarts don't help; reset after 30 min healthy.
#   两次重启至少间隔 300 秒；连续无效则翻倍，最多 1800 秒；健康 30 分钟后恢复。
# - If WeChat is not running or looks logged out, it only logs and does NOT restart or try to log in.
#   微信没运行或疑似退出登录时只记日志，不重启、不尝试登录。
# - Single instance (named mutex). Log: logs\watchdog.log
# - Pause: create a file named watchdog.disable next to this script. 暂停：在脚本同目录新建 watchdog.disable。
# Install as a scheduled task: install_watchdog.bat   卸载：uninstall_watchdog.bat
$ErrorActionPreference = 'Continue'
$Root     = $PSScriptRoot
$LogDir   = Join-Path $Root 'logs'
$HB       = if ($env:HEARTBEAT_FILE) { Join-Path $Root $env:HEARTBEAT_FILE } else { Join-Path $LogDir 'bot.heartbeat' }
$BotOut   = Join-Path $LogDir 'bot.stdout.log'
$Log      = Join-Path $LogDir 'watchdog.log'
$Disable  = Join-Path $Root 'watchdog.disable'
$StaleSec = if ($env:WD_STALE_SEC) { [int]$env:WD_STALE_SEC } else { 300 }
$CheckSec = 30
$BaseCool = 300
$MaxCool  = 1800
$WeChatProc = if ($env:WD_WECHAT_PROCESS) { $env:WD_WECHAT_PROCESS } else { 'Weixin' }

New-Item -ItemType Directory -Force $LogDir | Out-Null
$mutex = New-Object System.Threading.Mutex($false, 'Global\WechatAiReplyWinWatchdog')
if (-not $mutex.WaitOne(0)) { exit 0 }   # another watchdog is already running

function W($m) { Add-Content -Path $Log -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) -Encoding UTF8 }

function Get-BotProcs {
  # the run_bot.bat wrapper and the python process running bot.py (py -3.13 -u bot.py)
  Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -notmatch 'watchdog' -and
    ($_.CommandLine -match 'run_bot\.bat' -or $_.CommandLine -match '(^|[\\\s"])bot\.py')
  }
}

function WeChat-State {
  if (-not (Get-Process -Name $WeChatProc -ErrorAction SilentlyContinue)) { return 'not-running' }
  $py = @(Get-BotProcs | Where-Object { $_.Name -match 'python|py\.exe' })
  if ($py.Count -eq 0 -and (Test-Path $BotOut) -and (Get-Item $BotOut).Length -gt 0) {
    $txt = Get-Content $BotOut -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($txt -and $txt -notmatch '\[start\]') { return 'logged-out?' }   # bot never connected
  }
  return 'ok'
}

function Start-Bot {
  Get-BotProcs | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; W "killed pid=$($_.ProcessId) $($_.Name)" } catch {} }
  Start-Sleep 2
  if (Test-Path $BotOut) { Copy-Item $BotOut ($BotOut + '.prev') -Force }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'cmd.exe'
  $psi.Arguments = '/c set HTTP_PROXY=& set HTTPS_PROXY=& set ALL_PROXY=& set http_proxy=& set https_proxy=& set all_proxy=& "' + (Join-Path $Root 'run_bot.bat') + '"'
  $psi.WorkingDirectory = $Root
  $psi.UseShellExecute = $true
  $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
  $p = [System.Diagnostics.Process]::Start($psi)
  W "started run_bot.bat pid=$($p.Id)"
}

W "watchdog start pid=$PID stale=${StaleSec}s check=${CheckSec}s cooldown=${BaseCool}s"
$lastRestart = [datetime]::MinValue
$cool = $BaseCool
$lastWc = ''
while ($true) {
  try {
    if (Test-Path $Disable) { Start-Sleep $CheckSec; continue }
    $py = @(Get-BotProcs | Where-Object { $_.Name -match 'python|py\.exe' })
    $age = $null
    if (Test-Path $HB) { $age = ((Get-Date) - (Get-Item $HB).LastWriteTime).TotalSeconds }
    $reason = $null
    if ($py.Count -eq 0) { $reason = 'process-gone' }
    elseif ($age -eq $null -or $age -gt $StaleSec) { $reason = "heartbeat-stale age=$([int]$age)s" }

    if ($reason) {
      $wc = WeChat-State
      if ($wc -ne 'ok') {
        if ($wc -ne $lastWc) { W "bot unhealthy ($reason) but WeChat $wc -> NOT restarting; log in to WeChat manually" }
        $lastWc = $wc
      } else {
        $lastWc = 'ok'
        $since = ((Get-Date) - $lastRestart).TotalSeconds
        if ($since -lt $cool) {
          W "unhealthy ($reason) but in cooldown ($([int]$since)/${cool}s)"
        } else {
          W "RESTART reason=$reason"
          Start-Bot
          if ($since -lt ($cool + $StaleSec + 120)) { $cool = [Math]::Min($cool * 2, $MaxCool) }
          $lastRestart = Get-Date
        }
      }
    } elseif ($cool -ne $BaseCool -and ((Get-Date) - $lastRestart).TotalSeconds -gt 1800) {
      $cool = $BaseCool; W 'healthy 30min, cooldown reset'
    }
  } catch { W "error $($_.Exception.Message)" }
  Start-Sleep $CheckSec
}
