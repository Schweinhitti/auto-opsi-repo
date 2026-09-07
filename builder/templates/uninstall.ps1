. (Join-Path $PSScriptRoot 'runtime.ps1')
try {
    $code=0
    $extra=@(Value $config.uninstall 'silent_args' @()) -join ' '
    switch ($config.uninstall.method) {
        'registry' {
            foreach ($entry in @(Entries $true)) {
                if ($entry.WindowsInstaller -eq 1 -and $entry.Name -match '^\{[A-Fa-f0-9-]+\}$') {
                    $result=Run 'msiexec.exe' ('/x '+$entry.Name+' /qn /norestart')
                } elseif ($entry.Quiet) { $result=RunCommand $entry.Quiet '' }
                elseif ($extra) { $result=RunCommand $entry.Command $extra }
                else { throw 'No quiet uninstall string or configured silent arguments' }
                if ($result -ne 0) { $code=$result }
            }
        }
        'msi' { $code=Run 'msiexec.exe' ('/x '+$config.uninstall.product_code+' /qn /norestart') }
        'vendor' { $code=Run ([Environment]::ExpandEnvironmentVariables($config.uninstall.path)) $extra }
        'command' { $code=RunCommand $config.uninstall.command $extra }
        'zip' {
            $target=[Environment]::ExpandEnvironmentVariables($config.installer.target_dir)
            if ($target -notmatch '^[A-Za-z]:\\.+\\[^\\]+$') { throw 'Unsafe removal target' }
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        }
        'msix' {
            Get-AppxProvisionedPackage -Online | Where-Object DisplayName -eq $config.uninstall.package_name | Remove-AppxProvisionedPackage -Online -AllUsers | Out-Null
        }
    }
    if ($code -eq 0 -and (InstalledVersion)) { throw 'Application still detected after uninstall' }
    exit $code
} catch { Write-Error $_; exit 1 }
