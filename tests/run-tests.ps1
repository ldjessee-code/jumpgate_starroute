# tests/run-tests.ps1 — Python unittest and Node tests for this repo (X-27).
# From the repo root the suites are:
#   .\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
#   node --test "tests/js/"
# A suite that exits 0 after running 0 tests is still a failure.
[CmdletBinding()]
param(
  [ValidateSet('all', 'node', 'python')]
  [string]$Only = 'all',
  [switch]$Raw,
  [switch]$ParseOnly,
  [string]$Text = '',
  [ValidateSet('python', 'node')]
  [string]$Kind = 'python',
  [string]$NodeTarget = 'tests/js/',
  [string]$PythonStart = 'tests',
  [string]$Root = ''
)

$ErrorActionPreference = 'Continue'
$TestsDir = Split-Path -Parent $PSCommandPath
$RepoRoot = Split-Path -Parent $TestsDir

function Normalize-Report([string]$Value) {
  $esc = [char]27
  $stripped = [regex]::Replace($Value, "$esc\[[0-9;]*[A-Za-z]", '')
  return $stripped.Replace("`r", '')
}

function ConvertFrom-Packed([string]$Value) {
  $marker = [string][char]1
  $step = $Value.Replace('\\', $marker)
  $step = $step.Replace('\r', "`r").Replace('\n', "`n")
  return $step.Replace($marker, '\')
}

function Get-PythonCounts([string]$Value) {
  $clean = Normalize-Report $Value
  $ranMatches = [regex]::Matches($clean, '(?m)^Ran (\d+) tests?\b')
  if ($ranMatches.Count -lt 1) { return $null }
  $last = $ranMatches[$ranMatches.Count - 1]
  $ran = [int]$last.Groups[1].Value
  $tail = $clean.Substring($last.Index)
  $failed = 0
  if ($tail -match '(?m)^FAILED\b') {
    $failN = 0
    $errN = 0
    $unexp = 0
    if ($tail -match 'failures=(\d+)') { $failN = [int]$Matches[1] }
    if ($tail -match 'errors=(\d+)') { $errN = [int]$Matches[1] }
    if ($tail -match 'unexpected successes=(\d+)') { $unexp = [int]$Matches[1] }
    if (($failN + $errN + $unexp) -eq 0) { return $null }
    $failed = $failN + $errN + $unexp
  } elseif (-not ($tail -match '(?m)^NO TESTS RAN\b' -or $tail -match '(?m)^OK\b')) {
    return $null
  }
  $skipped = 0
  if ($tail -match 'skipped=(\d+)') { $skipped = [int]$Matches[1] }
  $pass = $ran - $failed - $skipped
  if ($pass -lt 0) { $pass = 0 }
  return @{ Ran = $ran; Pass = $pass; Failed = $failed }
}

function Get-NodeCounts([string]$Value) {
  $clean = Normalize-Report $Value
  $info = [regex]::Escape([string][char]0x2139)
  $prefix = '(?:#|' + $info + '|i)'
  $testsRe = '(?m)^[ \t]*' + $prefix + '[ \t]+tests[ \t]+(\d+)[ \t]*$'
  $passRe = '(?m)^[ \t]*' + $prefix + '[ \t]+pass[ \t]+(\d+)[ \t]*$'
  $failRe = '(?m)^[ \t]*' + $prefix + '[ \t]+fail[ \t]+(\d+)[ \t]*$'
  $testsMatches = [regex]::Matches($clean, $testsRe)
  $passMatches = [regex]::Matches($clean, $passRe)
  $failMatches = [regex]::Matches($clean, $failRe)
  if ($testsMatches.Count -lt 1 -or $passMatches.Count -lt 1 -or $failMatches.Count -lt 1) {
    return $null
  }
  $ran = [int]$testsMatches[$testsMatches.Count - 1].Groups[1].Value
  $pass = [int]$passMatches[$passMatches.Count - 1].Groups[1].Value
  $failed = [int]$failMatches[$failMatches.Count - 1].Groups[1].Value
  return @{ Ran = $ran; Pass = $pass; Failed = $failed }
}

function Test-CountGate($Parsed, [int]$ExitCode, [bool]$CheckExit) {
  if ($null -eq $Parsed) { return $false }
  if ($Parsed.Ran -eq 0) { return $false }
  if ($Parsed.Failed -gt 0) { return $false }
  if ($Parsed.Pass -lt 0) { return $false }
  if ($CheckExit -and $ExitCode -ne 0) { return $false }
  return $true
}

if ($ParseOnly) {
  if (-not $Kind) {
    Write-Output 'PARSE_ERROR kind'
    exit 1
  }
  $decoded = ConvertFrom-Packed $Text
  $parsed = $null
  if ($Kind -eq 'python') {
    $parsed = Get-PythonCounts $decoded
  } else {
    $parsed = Get-NodeCounts $decoded
  }
  if ($null -eq $parsed) {
    Write-Output "${Kind}: PARSE_ERROR"
    exit 1
  }
  Write-Output "${Kind}: ran $($parsed.Ran), failed $($parsed.Failed)"
  if (Test-CountGate -Parsed $parsed -ExitCode 0 -CheckExit $false) { exit 0 }
  exit 1
}

# A nested full-suite run would rediscover this script's own tests.
if ($env:STARROUTE_RUNNER_DEPTH -eq '1' -and [string]::IsNullOrEmpty($Root)) {
  Write-Output 'runner recursion blocked'
  exit 1
}
$env:STARROUTE_RUNNER_DEPTH = '1'

if ($Root) {
  if ([System.IO.Path]::IsPathRooted($Root)) {
    $WorkRoot = [System.IO.Path]::GetFullPath($Root)
  } else {
    $WorkRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Root))
  }
} else {
  $WorkRoot = $RepoRoot
}

$PythonExe = Join-Path $RepoRoot '.venv\Scripts\python.exe'

function Invoke-Captured {
  param(
    [string]$FileName,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory
  )
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FileName
  foreach ($arg in $ArgumentList) {
    [void]$psi.ArgumentList.Add($arg)
  }
  $psi.WorkingDirectory = $WorkingDirectory
  $psi.UseShellExecute = $false
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $utf8 = New-Object System.Text.UTF8Encoding $false
  $psi.StandardOutputEncoding = $utf8
  $psi.StandardErrorEncoding = $utf8
  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  [void]$proc.Start()
  $proc.StandardInput.Close()
  $outTask = $proc.StandardOutput.ReadToEndAsync()
  $errTask = $proc.StandardError.ReadToEndAsync()
  $stdout = $outTask.GetAwaiter().GetResult()
  $stderr = $errTask.GetAwaiter().GetResult()
  [void]$proc.WaitForExit()
  return @{
    ExitCode = [int]$proc.ExitCode
    Output   = ($stdout + $stderr)
  }
}

$gateOk = $true
$summaries = @()

if ($Only -eq 'all' -or $Only -eq 'python') {
  $py = Invoke-Captured -FileName $PythonExe -ArgumentList @(
    '-m', 'unittest', 'discover', '-s', $PythonStart, '-t', '.', '-v'
  ) -WorkingDirectory $WorkRoot
  Write-Output "----- python raw exit $($py.ExitCode) -----"
  Write-Output $py.Output
  $parsedPy = Get-PythonCounts $py.Output
  if ($null -eq $parsedPy) {
    $summaries += 'python: PARSE_ERROR'
    $gateOk = $false
  } else {
    $summaries += "python: ran $($parsedPy.Ran), failed $($parsedPy.Failed)"
    if (-not (Test-CountGate -Parsed $parsedPy -ExitCode $py.ExitCode -CheckExit $true)) {
      $gateOk = $false
    }
  }
}

if ($Only -eq 'all' -or $Only -eq 'node') {
  $nodeExe = (Get-Command -Name node -ErrorAction Stop).Source
  $nd = Invoke-Captured -FileName $nodeExe -ArgumentList @(
    '--test', $NodeTarget
  ) -WorkingDirectory $WorkRoot
  Write-Output "----- node raw exit $($nd.ExitCode) -----"
  Write-Output $nd.Output
  $parsedNd = Get-NodeCounts $nd.Output
  if ($null -eq $parsedNd) {
    $summaries += 'node: PARSE_ERROR'
    $gateOk = $false
  } else {
    $summaries += "node: ran $($parsedNd.Ran), failed $($parsedNd.Failed)"
    if (-not (Test-CountGate -Parsed $parsedNd -ExitCode $nd.ExitCode -CheckExit $true)) {
      $gateOk = $false
    }
  }
}

foreach ($line in $summaries) {
  Write-Output $line
}
if ($gateOk) { exit 0 }
exit 1
