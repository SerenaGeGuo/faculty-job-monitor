# Triggered by the "FacultyJobMonitor" scheduled task on every logon.
# Only actually runs the scan if at least $minIntervalDays have passed
# since the last run, so logging in daily doesn't re-scan daily.

$logDir = Join-Path $PSScriptRoot "logs"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$markerFile = Join-Path $logDir "last_run.marker"
$minIntervalDays = 6

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "run_$timestamp.log"

if (Test-Path $markerFile) {

    $lastRun = Get-Content $markerFile -Raw | ForEach-Object { [datetime]$_ }
    $daysSince = (Get-Date) - $lastRun

    if ($daysSince.TotalDays -lt $minIntervalDays) {
        $daysRounded = [math]::Round($daysSince.TotalDays, 1)
        "Skipped: last run was $daysRounded day(s) ago (threshold: $minIntervalDays days)." |
            Out-File -FilePath $logFile
        exit 0
    }
}

Set-Location $PSScriptRoot

# Prevent the system from sleeping while the scan runs (a full run
# can take several minutes; without this, Windows' own idle/sleep
# timers can suspend or kill the process partway through).
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class SleepBlocker {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
    public const uint ES_CONTINUOUS = 0x80000000;
    public const uint ES_SYSTEM_REQUIRED = 0x00000001;
}
"@

[SleepBlocker]::SetThreadExecutionState(
    [SleepBlocker]::ES_CONTINUOUS -bor [SleepBlocker]::ES_SYSTEM_REQUIRED
) | Out-Null

try {
    & "$PSScriptRoot\.venv\Scripts\python.exe" main.py *>> $logFile
    $exitCode = $LASTEXITCODE
}
finally {
    [SleepBlocker]::SetThreadExecutionState([SleepBlocker]::ES_CONTINUOUS) | Out-Null
}

# Only record this as "the last run" if main.py actually succeeded.
# A crashed run must NOT count toward the throttle - otherwise a
# single failure silently blocks the next several days of legitimate
# logon-triggered attempts too.
if ($exitCode -eq 0) {
    (Get-Date).ToString("o") | Set-Content -Path $markerFile
}
else {
    "main.py exited with code $exitCode - marker NOT updated, will retry on next logon." |
        Out-File -FilePath $logFile -Append
}
