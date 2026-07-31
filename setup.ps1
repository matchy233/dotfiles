[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Test-CommandAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-SymbolicLinkCapability {
    $probeRoot = Join-Path `
        ([System.IO.Path]::GetTempPath()) `
        ("dotfiles-symlink-" + [guid]::NewGuid().ToString("N"))

    try {
        New-Item -ItemType Directory -Path $probeRoot | Out-Null
        $targetPath = Join-Path $probeRoot "target.txt"
        $linkPath = Join-Path $probeRoot "link.txt"
        Set-Content -LiteralPath $targetPath -Value "probe" -NoNewline
        New-Item -ItemType SymbolicLink -Path $linkPath -Target $targetPath |
            Out-Null
        return (Test-Path -LiteralPath $linkPath)
    }
    catch {
        return $false
    }
    finally {
        if (Test-Path -LiteralPath $probeRoot) {
            Remove-Item -LiteralPath $probeRoot -Recurse -Force
        }
    }
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Name @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Backup-LegacyAgentsRepository {
    $agentsPath = Join-Path $HOME ".agents"
    $gitPath = Join-Path $agentsPath ".git"
    if (-not (Test-Path -LiteralPath $gitPath)) {
        return $null
    }

    $backupPath = Join-Path $HOME ".agents.backup-before-chezmoi"
    if (Test-Path -LiteralPath $backupPath) {
        throw "Backup already exists: $backupPath"
    }

    Write-Host "Legacy agents Git checkout detected: $agentsPath"
    git -C $agentsPath status --short --branch
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the legacy agents repository"
    }
    git -C $agentsPath fsck --no-progress
    if ($LASTEXITCODE -ne 0) {
        throw "Legacy agents repository failed git fsck"
    }

    $answer = Read-Host (
        "Rename it to .agents.backup-before-chezmoi before apply? " +
        "Type BACKUP to continue"
    )
    if ($answer -cne "BACKUP") {
        throw "Setup cancelled before renaming the legacy agents repository"
    }

    Rename-Item `
        -LiteralPath $agentsPath `
        -NewName ".agents.backup-before-chezmoi"

    $backupGitPath = Join-Path $backupPath ".git"
    if (-not (Test-Path -LiteralPath $backupGitPath)) {
        throw "Renamed backup does not contain Git metadata: $backupPath"
    }
    git -C $backupPath fsck --no-progress
    if ($LASTEXITCODE -ne 0) {
        throw "Renamed agents backup failed git fsck"
    }

    return $backupPath
}

function Initialize-PrivateDeepSeekSettings {
    param(
        [AllowNull()]
        [string]$AgentsBackupPath
    )

    $privatePath = Join-Path `
        $HOME `
        ".agents/claude/cc-deepseek.settings.json"
    $examplePath = Join-Path `
        $HOME `
        ".agents/claude/cc-deepseek.settings.example.json"

    if (-not (Test-Path -LiteralPath $privatePath)) {
        $backupPrivatePath = $null
        if ($AgentsBackupPath) {
            $backupPrivatePath = Join-Path `
                $AgentsBackupPath `
                "claude/cc-deepseek.settings.json"
        }

        if (
            $backupPrivatePath -and
            (Test-Path -LiteralPath $backupPrivatePath)
        ) {
            Copy-Item -LiteralPath $backupPrivatePath -Destination $privatePath
            Write-Host "Restored the private DeepSeek settings from backup."
        }
        elseif (Test-Path -LiteralPath $examplePath) {
            Copy-Item -LiteralPath $examplePath -Destination $privatePath
            Write-Warning (
                "Created the private DeepSeek settings from the example. " +
                "Add the API token before using it."
            )
        }
        else {
            Write-Warning "Private DeepSeek settings are missing."
            return
        }
    }

    try {
        $settings = Get-Content -LiteralPath $privatePath -Raw |
            ConvertFrom-Json
        $token = $settings.env.ANTHROPIC_AUTH_TOKEN
        if (
            [string]::IsNullOrWhiteSpace($token) -or
            $token -eq "<your-deepseek-api-key>"
        ) {
            Write-Warning (
                "The private DeepSeek token is missing or still uses the " +
                "placeholder. Edit $privatePath locally; do not add it to Git."
            )
        }
    }
    catch {
        throw "Unable to parse the private DeepSeek settings: $privatePath"
    }
}

function Invoke-DotfilesSetup {
    foreach ($command in @("git", "chezmoi", "npx")) {
        if (-not (Test-CommandAvailable -Name $command)) {
            throw "Required command is unavailable: $command"
        }
    }

    if (-not (Test-SymbolicLinkCapability)) {
        throw (
            "Windows symbolic-link creation is unavailable. Enable Developer " +
            "Mode in Settings > System > Advanced > For developers, then " +
            "rerun setup.ps1."
        )
    }

    Write-Host "Reviewing the current chezmoi changes."
    Invoke-CheckedCommand -Name "chezmoi" -Arguments @("diff")
    Write-Host "Running: chezmoi apply --dry-run --verbose"
    Invoke-CheckedCommand `
        -Name "chezmoi" `
        -Arguments @("apply", "--dry-run", "--verbose")

    Write-Warning (
        "Chezmoi manages both PowerShell profiles and .zshrc. Move any " +
        "device-only settings to ~/.config/powershell/local-profile.ps1 or " +
        "~/.zshrc.local before continuing."
    )
    $answer = Read-Host "Apply these changes? Type APPLY to continue"
    if ($answer -cne "APPLY") {
        Write-Host "Setup cancelled without applying changes."
        return
    }

    $agentsBackupPath = Backup-LegacyAgentsRepository
    Invoke-CheckedCommand -Name "chezmoi" -Arguments @("apply")
    Initialize-PrivateDeepSeekSettings `
        -AgentsBackupPath $agentsBackupPath

    Write-Host "Chezmoi setup finished. Run 'chezmoi status' to verify it."
}

if ($MyInvocation.InvocationName -ne ".") {
    Invoke-DotfilesSetup
}
