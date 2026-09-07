. (Join-Path $PSScriptRoot 'runtime.ps1')
try {
    $installed=InstalledVersion
    if ($installed -and (AtLeast $installed $config.detection_version)) { Write-Output "Already installed: $installed"; exit 0 }
    if ($installed -and (Value $config.installer 'uninstall_previous' $false)) {
        & (Join-Path $PSHOME 'powershell.exe') -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'uninstall.ps1')
        if ($LASTEXITCODE -notin @(0,3010,1641)) { throw 'Required removal of previous version failed' }
    }
    $installer=Join-Path $PSScriptRoot ('installer.'+$config.installer.type)
    $args=@($config.installer.silent_args) -join ' '
    $code=0
    switch ($config.installer.type) {
        'msi' { $code=Run 'msiexec.exe' ('/i "'+$installer+'" '+$args) }
        'exe' { $code=Run $installer $args }
        'msix' { Add-AppxProvisionedPackage -Online -PackagePath $installer -SkipLicense | Out-Null }
        'zip' {
            $target=[Environment]::ExpandEnvironmentVariables($config.installer.target_dir)
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            Copy-Item -Path (Join-Path $PSScriptRoot 'payload\*') -Destination $target -Recurse -Force
        }
    }
    if ($code -eq 0 -and $config.detection.method -ne 'custom') {
        $installed=InstalledVersion
        if (-not $installed -or -not (AtLeast $installed $config.detection_version)) { throw 'Post-install version detection failed' }
    }
    exit $code
} catch { Write-Error $_; exit 1 }
