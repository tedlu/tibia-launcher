Param(
  [Parameter(HelpMessage='Path to the EXE to sign')]
  [string]$ExePath = "dist\tibialauncher.exe",

  [ValidateSet('pfx','thumb')]
  [string]$Mode = 'thumb',

  [Parameter(HelpMessage='Path to PFX (Mode=pfx)')]
  [string]$PfxPath = "",
  [Parameter(HelpMessage='Password for PFX (Mode=pfx)')]
  [string]$PfxPassword = "",

  [Parameter(HelpMessage='Certificate thumbprint (Mode=thumb)')]
  [string]$Thumbprint = "",

  [ValidateSet('User','Machine')]
  [string]$StoreLocation = 'User',

  [string]$TimestampUrl = "http://timestamp.digicert.com",
  [string]$DisplayName = "Tibia Launcher",
  [string]$DisplayUrl = "https://yourserver.com",

  [switch]$Help
)

if ($Help) {
  Write-Host "Usage: .\\sign-exe.ps1 [-ExePath path] [-Mode pfx|thumb] [-PfxPath path -PfxPassword pwd] [-Thumbprint hash] [-StoreLocation User|Machine]" -ForegroundColor Cyan
  Write-Host "Examples:" -ForegroundColor Cyan
  Write-Host "  .\\sign-exe.ps1 -Mode pfx -PfxPath C:\\certs\\code.pfx -PfxPassword secret" -ForegroundColor Gray
  Write-Host "  .\\sign-exe.ps1 -Mode thumb -Thumbprint THUMBPRINTHERE -StoreLocation Machine" -ForegroundColor Gray
  return
}

function Get-SignToolPath {
  # Try PATH first
  $candidate = (Get-Command signtool -ErrorAction SilentlyContinue | Select-Object -First 1).Source
  if ($candidate) { return $candidate }
  # Probe common Windows 10/11 SDK install directories for the latest x64 signtool
  $kits = Join-Path "$Env:ProgramFiles(x86)" "Windows Kits\\10\\bin"
  if (Test-Path $kits) {
    $versions = Get-ChildItem -Path $kits -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending
    foreach ($v in $versions) {
      $path = Join-Path $v.FullName "x64\\signtool.exe"
      if (Test-Path $path) { return $path }
    }
  }
  throw "signtool.exe not found. Install the Windows 10/11 SDK or add signtool to PATH."
}
$_signtool = Get-SignToolPath

if (-not (Test-Path $ExePath)) { throw "EXE not found: $ExePath" }

function Sign-WithPfx {
  param($exe,$pfx,$pwd,$ts,$name,$url)
  if (-not (Test-Path $pfx)) { throw "PFX not found: $pfx" }
  & $_signtool sign `
    /fd SHA256 `
    /f $pfx /p $pwd `
    /tr $ts /td SHA256 `
    /d $name /du $url `
    $exe
}

function Sign-WithThumb {
  param($exe,$thumb,$ts,$name,$url,$storeLoc)
  if (-not $thumb) { throw "Thumbprint is required for Mode=thumb" }
  # Normalize thumbprint: remove spaces and make uppercase
  $thumbNorm = ($thumb -replace "\s", "").ToUpperInvariant()
  $args = @('/fd','SHA256','/sha1',$thumbNorm,'/s','My')
  if ($storeLoc -eq 'Machine') { $args += '/sm' }
  $args += @('/tr',$ts,'/td','SHA256','/d',$name,'/du',$url,$exe)
  & $_signtool sign @args
}

Write-Host "Signing $ExePath using mode=$Mode" -ForegroundColor Cyan
if ($Mode -eq 'pfx') {
  if (-not $PfxPath -or -not $PfxPassword) { throw "Provide -PfxPath and -PfxPassword" }
  Sign-WithPfx -exe $ExePath -pfx $PfxPath -pwd $PfxPassword -ts $TimestampUrl -name $DisplayName -url $DisplayUrl
}
else {
  if (-not $Thumbprint) { throw "Provide -Thumbprint for Mode=thumb" }
  Sign-WithThumb -exe $ExePath -thumb $Thumbprint -ts $TimestampUrl -name $DisplayName -url $DisplayUrl -storeLoc $StoreLocation
}

Write-Host "Verifying signature..." -ForegroundColor Cyan
& $_signtool verify /pa /all $ExePath
Write-Host "Done." -ForegroundColor Green