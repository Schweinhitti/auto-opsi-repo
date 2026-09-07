$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
function Value($object, $name, $default) {
    if ($object.PSObject.Properties.Name -contains $name) { return $object.$name }
    return $default
}
function Entries($uninstall = $false) {
    $regex = Value $config.detection 'display_name_regex' '^$'
    if ($uninstall) { $regex = Value $config.uninstall 'display_name_regex' $regex }
    foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,$view)
        try {
            $root = $base.OpenSubKey('SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')
            if ($null -eq $root) { continue }
            try {
                foreach ($name in $root.GetSubKeyNames()) {
                    $key = $root.OpenSubKey($name)
                    try {
                        $display = $key.GetValue('DisplayName','')
                        $match = $display -match $regex
                        if ($config.detection.method -eq 'msi') { $match = $name -eq $config.detection.product_code }
                        if ($match) {
                            $detectedVersion=$key.GetValue('DisplayVersion','0')
                            $displayVersionRegex=Value $config.detection 'version_from_display_name_regex' ''
                            if ($displayVersionRegex) {
                                if ($display -notmatch $displayVersionRegex) { throw 'Display-name version extraction failed' }
                                $detectedVersion=$Matches[1]
                            }
                            $replacements=Value $config.detection 'version_replacements' $null
                            if ($null -ne $replacements) {
                                foreach ($replacement in $replacements.PSObject.Properties) {
                                    $detectedVersion=$detectedVersion.Replace($replacement.Name,[string]$replacement.Value)
                                }
                            }
                            [PSCustomObject]@{ Name=$name; DisplayName=$display; Version=$detectedVersion; Quiet=$key.GetValue('QuietUninstallString',''); Command=$key.GetValue('UninstallString',''); WindowsInstaller=$key.GetValue('WindowsInstaller',0) }
                        }
                    } finally { $key.Dispose() }
                }
            } finally { $root.Dispose() }
        } finally { $base.Dispose() }
    }
}
function InstalledVersion {
    if ($config.detection.method -eq 'file_version') {
        $path = [Environment]::ExpandEnvironmentVariables($config.detection.path)
        if (Test-Path -LiteralPath $path) { return (Get-Item -LiteralPath $path).VersionInfo.ProductVersion }
        return $null
    }
    $items = @(Entries)
    if ($items.Count -gt 0) { return $items[0].Version }
    return $null
}
function AtLeast($actual, $desired) {
    if ($actual -eq $desired) { return $true }
    # Compare numeric vendor versions; unknown formats trigger install instead of false success.
    if ($actual -match '^\d+(\.\d+)*$' -and $desired -match '^\d+(\.\d+)*$') {
        $a=@($actual.Split('.')); $b=@($desired.Split('.'))
        for ($i=0; $i -lt [Math]::Max($a.Count,$b.Count); $i++) {
            $x=0L; $y=0L
            if ($i -lt $a.Count) { $x=[long]$a[$i] }; if ($i -lt $b.Count) { $y=[long]$b[$i] }
            if ($x -gt $y) { return $true }; if ($x -lt $y) { return $false }
        }
        return $true
    }
    return $false
}
function Run($file, $arguments) {
    Write-Host ('Running vendor executable: '+$file)
    $process = Start-Process -FilePath $file -ArgumentList $arguments -PassThru
    if (-not $process.WaitForExit(1800000)) { throw 'Vendor process exceeded 30 minute timeout; inspect client before retrying' }
    $process.WaitForExit()
    if ($process.ExitCode -notin @(0,3010,1641)) { throw ('Vendor exit code '+$process.ExitCode) }
    return $process.ExitCode
}
function RunCommand($command, $extra) {
    $command = [Environment]::ExpandEnvironmentVariables($command)
    if ($command -match '^"([^"]+)"\s*(.*)$') { $file=$Matches[1]; $args=$Matches[2] }
    elseif ($command -match '^([^\s]+\.exe)\s*(.*)$') { $file=$Matches[1]; $args=$Matches[2] }
    else { throw 'Ambiguous unquoted uninstall command; configure an explicit override' }
    return Run $file ($args+' '+$extra)
}
