# run_headless.ps1 — run an Illustrator script headless, with NO dialogs.
#
# Why this exists (measured on Illustrator 2026 / build 30 / Windows, 2026-10-30):
#   Launching with a script on ANOTHER drive (e.g. D:\...) makes Illustrator pop a
#   MODAL "File not found" box (the path is even shown without its drive letter).
#   That modal blocks the main thread: the script does not start until someone
#   clicks OK. With the script on Illustrator's OWN drive (C:) it runs straight
#   away with no dialog at all (measured: full 7.6 MB SVG -> layered .ai in 16 s).
#   => Always stage the script to %SystemDrive% before launching.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File run_headless.ps1 `
#       -Jsx "C:\path\to\script.jsx" -Log "C:\path\to\_ailog.txt" -TimeoutSec 600
#
# Options:
#   -NoKill        do not kill existing instances before launch
#   -WaitExit      wait for Illustrator to exit after the script finishes
#   -KeepLog       do not delete an existing log before launch
#   -KillOnTimeout kill Illustrator on timeout (OFF by default: a running script
#                  may still be working, and killing it is what really breaks it)
#
# Exit codes: 0 ok | 2 bad arguments/file | 3 stale instance will not die
#             4 script reported ERROR | 5 timeout | 6 timeout + KillOnTimeout
#
# Content is ASCII-only; this file carries a UTF-8 BOM so PowerShell 5.1 reads
# it as UTF-8 (without a BOM it reads ANSI, and non-ASCII strings can break
# parsing: "string is missing the terminator").

param(
  [Parameter(Mandatory=$true)][string]$Jsx,
  [Parameter(Mandatory=$true)][string]$Log,
  [int]$TimeoutSec = 600,
  [switch]$NoKill,
  [switch]$WaitExit,
  [switch]$KeepLog,
  [switch]$KillOnTimeout
)

$ErrorActionPreference = "Stop"
$ai = "C:\Program Files\Adobe\Adobe Illustrator 2026\Support Files\Contents\Windows\Illustrator.exe"

if (-not (Test-Path $ai)) { Write-Host "[run] Illustrator.exe not found: $ai"; exit 2 }
if (-not (Test-Path $Jsx)) { Write-Host "[run] script not found: $Jsx"; exit 2 }

function Get-AIProcs { @(Get-Process Illustrator -ErrorAction SilentlyContinue) }

# 1) Clean up stale instances (a stale one can steal the -r handoff)
if (-not $NoKill) {
  $procs = Get-AIProcs
  if ($procs.Count -gt 0) {
    Write-Host "[run] killing $($procs.Count) existing Illustrator process(es)"
    $procs | ForEach-Object { try { $_.Kill() } catch {} }
    for ($i = 0; $i -lt 30; $i++) {
      if ((Get-AIProcs).Count -eq 0) { break }
      Start-Sleep -Milliseconds 500
    }
    if ((Get-AIProcs).Count -eq 0) { Write-Host "[run] stale instances cleared" }
  }
}

# 2) Clear the log: its presence is the proof that the script really ran
if (-not $KeepLog -and (Test-Path $Log)) { Remove-Item $Log -Force }

# 3) Stage the script on Illustrator's own drive (this is what removes the dialog)
$stageDir = Join-Path $env:SystemDrive "ai\jobs"
New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
$staged = Join-Path $stageDir ([IO.Path]::GetFileName($Jsx))
if ([IO.Path]::GetFullPath($Jsx) -ne [IO.Path]::GetFullPath($staged)) {
  Copy-Item $Jsx $staged -Force
}
Write-Host "[run] staged script -> $staged"

# 4) Launch (-r runs the script; the script should call app.quit() when done)
Write-Host "[run] launching Illustrator with -r $staged"
Start-Process -FilePath $ai -ArgumentList @("-r", $staged) | Out-Null

# 5) Poll the log for done / ERROR
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
  if (Test-Path $Log) {
    $content = Get-Content $Log -Raw -ErrorAction SilentlyContinue
    if ($content -match "done") {
      Write-Host "[run] done"
      if ($WaitExit) { while ((Get-AIProcs).Count -gt 0) { Start-Sleep -Seconds 2 } }
      exit 0
    }
    if ($content -match "ERROR") {
      Write-Host "[run] script reported ERROR:"
      Write-Host $content
      exit 4
    }
  }
  Start-Sleep -Seconds 2
}

Write-Host "[run] timeout after ${TimeoutSec}s without 'done'"
if (Test-Path $Log) { Write-Host "--- log ---"; Get-Content $Log }
Write-Host "[run] NOTE: Illustrator was NOT killed (the script may still be working, e.g. opening a large file). Killing it is what actually breaks the run."
if ($KillOnTimeout) {
  Write-Host "[run] -KillOnTimeout given: killing Illustrator"
  Get-AIProcs | ForEach-Object { try { $_.Kill() } catch {} }
  exit 6
}
exit 5
