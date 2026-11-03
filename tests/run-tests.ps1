# tests/run-tests.ps1 — Python unittest and Node tests for this repo (X-27).
# From the repo root the suites are:
#   .\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
#   node --test "tests/js/"
# A suite that exits 0 after running 0 tests is still a failure.
# Node 24 also counts a directory that never calls test() as one passing
# test named after that directory. That entry is not a real test.
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

function Get-SlashNorm([string]$Path) {
  if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
  return (($Path.Trim() -replace '\\', '/').TrimEnd('/')).ToLowerInvariant()
}

function ConvertTo-ReportedPath([string]$Name) {
  $n = $Name.Trim()
  $n = [regex]::Replace($n, '\s+#.*$', '')
  if ($n.Contains('\\')) {
    $n = $n.Replace('\\', '\')
  }
  $n = $n.Replace('\#', '#')
  return $n.Trim()
}

function Test-NodePseudoName([string]$Name, [string]$NodeTarget, [string]$WorkRoot) {
  $n = ConvertTo-ReportedPath $Name
  if ([string]::IsNullOrWhiteSpace($n)) { return $false }
  $nameNorm = Get-SlashNorm $n
  if (-not [string]::IsNullOrWhiteSpace($NodeTarget)) {
    if ($nameNorm -eq (Get-SlashNorm $NodeTarget)) { return $true }
    $base = $WorkRoot
    if ([string]::IsNullOrWhiteSpace($base)) { $base = (Get-Location).Path }
    try {
      $targetFull = $NodeTarget
      if (-not [System.IO.Path]::IsPathRooted($targetFull)) {
        $targetFull = Join-Path $base $NodeTarget
      }
      $targetFull = [System.IO.Path]::GetFullPath($targetFull)
      if ($nameNorm -eq (Get-SlashNorm $targetFull)) { return $true }
      if ($n -match '^[A-Za-z]:[\\/]' -or $n.StartsWith('\\') -or $n.StartsWith('/')) {
        $nameFull = [System.IO.Path]::GetFullPath($n)
        if ((Get-SlashNorm $nameFull) -eq (Get-SlashNorm $targetFull)) { return $true }
      }
    } catch {
    }
  }
  $looksLikePath = ($n.Contains('\') -or $n.Contains('/') -or $n -match '^[A-Za-z]:')
  if (-not $looksLikePath) { return $false }
  $candidates = @($n)
  if (-not [System.IO.Path]::IsPathRooted($n)) {
    $base = $WorkRoot
    if ([string]::IsNullOrWhiteSpace($base)) { $base = (Get-Location).Path }
    try { $candidates += (Join-Path $base $n) } catch { }
  }
  foreach ($candidate in $candidates) {
    try {
      if (Test-Path -LiteralPath $candidate) { return $true }
    } catch {
    }
  }
  return $false
}

function Get-NodeReportedNames([string]$Clean) {
  $names = @()
  $specRe = '(?m)^[ \t]*\S+[ \t]+(.+?)[ \t]+\(\d+(?:\.\d+)?ms\)[ \t]*$'
  foreach ($match in [regex]::Matches($Clean, $specRe)) {
    $names += $match.Groups[1].Value.Trim()
  }
  $tapRe = '(?m)^(?:not )?ok[ \t]+\d+[ \t]+-[ \t]+(.+?)[ \t]*$'
  foreach ($match in [regex]::Matches($Clean, $tapRe)) {
    $names += $match.Groups[1].Value.Trim()
  }
  return $names
}

function Get-NodeCounts([string]$Value, [string]$NodeTarget = '', [string]$WorkRoot = '') {
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
  $reported = [int]$testsMatches[$testsMatches.Count - 1].Groups[1].Value
  $pass = [int]$passMatches[$passMatches.Count - 1].Groups[1].Value
  $failed = [int]$failMatches[$failMatches.Count - 1].Groups[1].Value
  $pseudo = 0
  foreach ($name in (Get-NodeReportedNames $clean)) {
    if (Test-NodePseudoName $name $NodeTarget $WorkRoot) { $pseudo++ }
  }
  $ran = $reported - $pseudo
  if ($ran -lt 0) { $ran = 0 }
  return @{ Ran = $ran; Pass = $pass; Failed = $failed; Pseudo = $pseudo }
}

function Test-CountGate($Parsed, [int]$ExitCode, [bool]$CheckExit) {
  if ($null -eq $Parsed) { return $false }
  if ($Parsed.Pseudo -gt 0) { return $false }
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
    $parsed = Get-NodeCounts $decoded $NodeTarget $RepoRoot
  }
  if ($null -eq $parsed) {
    Write-Output "${Kind}: PARSE_ERROR"
    exit 1
  }
  Write-Output "${Kind}: ran $($parsed.Ran), failed $($parsed.Failed)"
  if ($Kind -eq 'node' -and $parsed.Pseudo -gt 0) {
    Write-Output 'Node entry registered no tests'
  }
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
  $parsedNd = Get-NodeCounts $nd.Output $NodeTarget $WorkRoot
  if ($null -eq $parsedNd) {
    $summaries += 'node: PARSE_ERROR'
    $gateOk = $false
  } else {
    $summaries += "node: ran $($parsedNd.Ran), failed $($parsedNd.Failed)"
    if ($parsedNd.Pseudo -gt 0) {
      $summaries += 'Node entry registered no tests'
    }
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
