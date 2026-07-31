### ENV VARS ###
# Google Cloud
$env:GOOGLE_APPLICATION_CREDENTIALS = "$HOME\.config\google-cloud\vertexai-service-account.json"
$env:GOOGLE_CLOUD_PROJECT = "<your-google-cloud-project-id>"

$env:STARSHIP_CONFIG = "$HOME\.config\starship.toml"
$env:Path += ";$HOME\.local\bin"

### GLOBAL SETTINGS ###
# Suppress multiline warning
$ErrorView = 'CategoryView'


### CUSTOM FUNCTIONS ###

# function fn_showconfig {
#     python $HOME\.local\bin\sshconfig.py $args
# }

function Test-FullWidth {
    param (
        [char]$Char
    )

    $eastAsianWidth = [System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($Char)

    # East Asian Wide (W) and East Asian Full-width (F) are considered full-width
    return $eastAsianWidth -in @(
        [System.Globalization.UnicodeCategory]::OtherLetter,
        [System.Globalization.UnicodeCategory]::LetterNumber,
        [System.Globalization.UnicodeCategory]::OtherNumber,
        [System.Globalization.UnicodeCategory]::OtherSymbol
    )
}

function Get-Substring {
    param (
        [string]$String,
        [int]$StartIndex,
        [int]$Length
    )

    $curr = 0

    for ($i = 0; $i -lt $String.Length; $i++) {
        if (Test-FullWidth $String[$i]) {
            $curr += 2
        }
        else {
            $curr++
        }

        if ($curr -ge $StartIndex) {
            $startIndex = $i
            break
        }
    }

    for ($i = $startIndex; $i -lt $String.Length; $i++) {
        if (Test-FullWidth $String[$i]) {
            $curr += 2
        }
        else {
            $curr++
        }

        if ($curr -ge $StartIndex + $Length) {
            return $String.Substring($startIndex, $i - $startIndex)
        }
    }

    return $String.Substring($startIndex, $String.Length - $startIndex)
}


function ls_custom {
    param([switch]$a, [switch]$l, [switch]$la, [switch]$al, [switch]$h, [switch]$lah)
    if ($la -or $al) {
        $a = $true
        $l = $true
    }
    if ($lah) {
        $a = $true
        $l = $true
        $h = $true
    }

    $regex_opts = ([System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Compiled)

    $hidden = New-Object System.Text.RegularExpressions.Regex('^\.', $regex_opts)
    $compressed = New-Object System.Text.RegularExpressions.Regex('\.(zip|tar|gz|rar)$', $regex_opts)
    $executable = New-Object System.Text.RegularExpressions.Regex('\.(exe|bat|cmd|ps1|psm1|vbs|rb|reg|dll|o|lib|py|sh)$', $regex_opts)

    $width = $Host.UI.RawUI.WindowSize.Width
    $cols = 5
    if ($width -le 82) {
        $cols = 3
    }
    if ($l) {
        write-output "`n    Directory: $((Get-Location).Path)`n"
        $format_title = "{0} {1, 29} {2,15} {3}"
        write-host ($format_title -f "Mode", "LastWriteTime", "Length", "Name") -ForegroundColor Green
        write-host ($format_title -f "----", "-------------", "------", "----") -ForegroundColor Green

        $getHumanReadableSize = {
            param($size)
            if ($size -lt 1kb) {
                return $size.tostring()
            }
            elseif ($size -lt 1mb) {
                if ($size / 1kb -lt 10) {
                    return [string]::Format("{0:0.0}K", [math]::Round($size / 1kb, 2))
                }
                else {
                    return [string]::Format("{0:0}K", [math]::Round($size / 1kb, 2))
                }
            }
            elseif ($size -lt 1gb) {
                if ($size / 1mb -lt 10) {
                    return [string]::Format("{0:0.0}M", [math]::Round($size / 1mb, 2))
                }
                else {
                    return [string]::Format("{0:0}M", [math]::Round($size / 1mb, 2))
                }
            }
            elseif ($size -lt 1tb) {
                if ($size / 1gb -lt 10) {
                    return [string]::Format("{0:0.0}G", [math]::Round($size / 1gb, 2))
                }
                else {
                    return [string]::Format("{0:0}G", [math]::Round($size / 1gb, 2))
                }
            }
            else {
                if ($size / 1tb -lt 10) {
                    return [string]::Format("{0:0.0}T", [math]::Round($size / 1tb, 2))
                }
                else {
                    return [string]::Format("{0:0}T", [math]::Round($size / 1tb, 2))
                }
            }
        }

        $WriteFileInfo = {
            param($mode, $lwt, $len)
            write-host ("{0} {1, 28:dd-MMM-yy    hh:mm} {2,15}" -f $mode, $lwt, $len) -NoNewline
        }
        get-childitem $args | foreach-object {
            $out = $_.name
            $isHidden = $hidden.IsMatch($_.name)
            if ($h) {
                $len = $getHumanReadableSize.Invoke($_.length)[0]
            }
            else {
                $len = $_.length
            }
            if ($_.GetType().Name -eq 'DirectoryInfo') {
                if ($isHidden -AND $a) {
                    &$WriteFileInfo $_.mode $_.lastwritetime " "
                    write-host (" {0}" -f $_.name) -ForegroundColor DarkBlue
                }
                elseif ($isHidden) {
                    # do nothing
                }
                else {
                    &$WriteFileInfo $_.mode $_.lastwritetime " "
                    write-host (" {0}" -f $_.name) -ForegroundColor Blue
                }
            }
            elseif ($isHidden) {
                if ($a) {
                    &$WriteFileInfo $_.mode $_.lastwritetime $len
                    write-host (" {0}" -f $_.name) -ForegroundColor DarkGray
                }

            }
            elseif ($compressed.IsMatch($_.name)) {
                &$WriteFileInfo $_.mode $_.lastwritetime $len
                write-host (" {0}" -f $_.name) -ForegroundColor Red
            }
            elseif ($executable.IsMatch($out)) {
                &$WriteFileInfo $_.mode $_.lastwritetime $len
                write-host (" {0}" -f $_.name) -ForegroundColor Green
            }
            else {
                &$WriteFileInfo $_.mode $_.lastwritetime $len
                write-host (" {0}" -f $_.name)
            }
        }
    }
    else {
        invoke-expression ("Get-ChildItem $args") |
        foreach-object {
            $i = 0
            $colwid = [int]($width / $cols)
            $pad = [int]($width / $cols) - 1
        } `
        {
            $out = $_.Name

            $outLen = 0
            $shrinkVal = 0
            # iterate over chars in $out, counting full-width chars
            for ($j = 0; $j -lt $out.Length; $j++) {
                if (Test-FullWidth $out[$j]) {
                    $outLen += 2
                    $shrinkVal++
                }
                else {
                    $outLen++
                }
            }
            $isHidden = $hidden.IsMatch($out)
            if ($isHidden -AND ( -NOT $a )) {
                $nnl = $i % $cols -ne 0
            }
            else {
                $nnl = ++$i % $cols -ne 0
            }
            if ($outLen -ge $colwid - 1) {
                $out = "$(Get-Substring -String $out -StartIndex 0 -Length ($colwid - 5))…"
                $shrinkVal = 0
                for ($j = 0; $j -lt $out.Length; $j++) {
                    if (Test-FullWidth $out[$j]) {
                        $shrinkVal++
                    }
                }
            }
            if ($_.GetType().Name -eq 'DirectoryInfo') {
                if ($isHidden -AND $a) {
                    # write-host ("{0,-$pad}" -f $out) -Fore DarkBlue -NoNewLine:$nnl
                    write-host $out.padRight($pad - $shrinkVal) -ForegroundColor DarkBlue -NoNewLine:$nnl
                }
                elseif ($isHidden) {
                    # do nothing
                }
                else {
                    # write-host ("{0,-$pad}" -f $out) -Fore Blue -NoNewLine:$nnl
                    write-host $out.padRight($pad - $shrinkVal) -ForegroundColor Blue -NoNewLine:$nnl
                }
            }
            elseif ($isHidden) {
                if ($a) {
                    # write-host ("{0,-$pad}" -f $out) -Fore DarkGray -NoNewLine:$nnl
                    write-host $out.padRight($pad - $shrinkVal) -ForegroundColor DarkGray -NoNewLine:$nnl
                }

            }
            elseif ($compressed.IsMatch($out)) {
                # write-host ("{0,-$pad}" -f $out) -Fore Red -NoNewLine:$nnl
                write-host $out.padRight($pad - $shrinkVal) -ForegroundColor Red -NoNewLine:$nnl
            }
            elseif ($executable.IsMatch($out)) {
                # write-host ("{0,-$pad}" -f $out) -Fore Green -NoNewLine:$nnl
                write-host $out.padRight($pad - $shrinkVal) -ForegroundColor Green -NoNewLine:$nnl
            }
            else {
                # write-host ("{0,-$pad}" -f $out) -NoNewLine:$nnl
                write-host $out.padRight($pad - $shrinkVal) -NoNewLine:$nnl
            }
        }
    }
}

Function cd_custom {
    if ($Args) {
        if (test-path -Path $Args -PathType Container) {
            set-location @Args
            $numObj = 0
            $regex_opts = ([System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Compiled)
            $hidden = New-Object System.Text.RegularExpressions.Regex('^\.', $regex_opts)

            try {
                get-childitem -n -erroraction Stop | foreach-object { if (!($hidden.IsMatch($_))) { $numObj++ } }
                if ( $numObj -le 30 ) {
                    ls
                }
                else {
                    Write-Output "There are a total of $numObj entries in $((Get-Location).path)"
                }
            }
            catch {
                $_
            }

        }
        elseif (test-path -Path $Args -PathType Leaf) {
            Write-Host -ForegroundColor Red "ERROR: Destination directory is a file"
        }
        else {
            Write-Host -ForegroundColor Red "ERROR: Destination directory does not exist"
        }
    }
    else {
        set-location $(get-location)
    }
}

Function Remove-DupDownloads {
    param (
        [string]$SearchPath = ".",
        [switch]$Recurse = $false
    )

    $FilePattern = '.*\([1-9][0-9]*\).*'
    $GCIParams = @{
        'Path' = $SearchPath
        'File' = $true
    }

    if ($Recurse) {
        $GCIParams.Add('Recurse', $true)
    }

    $RecycleBin = (New-Object -ComObject Shell.Application).Namespace(0xA)

    Get-ChildItem @GCIParams |
    Where-Object { $_.Name -match $FilePattern } |
    ForEach-Object {
        write-output "Moving file to Recycle Bin: $($_.FullName)"
        $RecycleBin.MoveHere($_.FullName)
    }
}

### Starship
function unzip_custom {
    param (
        [Parameter(Mandatory = $true, Position = 0)]
        [string]$Path,
        [Parameter(Mandatory = $false, Position = 1)]
        [Alias("o")]
        [string]$DestinationPath = "."
    )

    if (-not (Test-Path $Path)) {
        Write-Error "File not found: $Path"
        return
    }

    if (-not (Test-Path $DestinationPath)) {
        New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null
    }

    Expand-Archive -Path $Path -DestinationPath $DestinationPath -Force
}

function Invoke-Starship-PreCommand {
    $loc = $executionContext.SessionState.Path.CurrentLocation;
    $prompt = "$([char]27)]9;12$([char]7)"
    if ($loc.Provider.Name -eq "FileSystem") {
        $prompt += "$([char]27)]9;9;`"$($loc.ProviderPath)`"$([char]27)\"
    }
    $host.ui.Write($prompt)
}

Invoke-Expression (&starship init powershell)
# Get-ChildItem "$PROFILE\..\Completions\" | ForEach-Object {
#     . $_.FullName
# }

###
set-psreadlineoption -colors @{ "InlinePrediction" = "#838383" }

### Alias
set-alias -Name touch -Value New-Item
set-alias -Name rmdup -Value Remove-DupDownloads -Option AllScope
set-alias -Name sshconfig -Value fn_showconfig
set-alias -Name cd -Value cd_custom -Option AllScope
set-alias -Name ls -Value ls_custom -Option AllScope
set-alias -Name which -Value get-command
set-alias -Name unzip -Value unzip_custom -Option AllScope
