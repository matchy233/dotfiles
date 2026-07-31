$sharedProfile = Join-Path $HOME ".config/powershell/shared-profile.ps1"
if (Test-Path -LiteralPath $sharedProfile) {
    . $sharedProfile
}

$localProfile = Join-Path $HOME ".config/powershell/local-profile.ps1"
if (Test-Path -LiteralPath $localProfile) {
    . $localProfile
}
