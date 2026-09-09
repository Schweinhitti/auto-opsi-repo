@echo off
setlocal EnableDelayedExpansion

rem Helper script to add a new package to packages.yaml
set "PACKAGES_FILE=%~dp0catalog\packages.yaml"

if not exist "%PACKAGES_FILE%" (
    echo Error: %PACKAGES_FILE% not found!
    exit /b 1
)

echo.
echo === Adding New Package to packages.yaml ===
echo.

rem Helper: escape backslashes and double quotes for YAML
call :escape_yaml PKG_ID
call :escape_yaml PKG_OP_ID
call :escape_yaml PKG_NAME
call :escape_yaml PKG_DESC
call :escape_yaml PKG_DISABLED_REASON

set /p PKG_ID=Package ID (e.g., my-package):
if not defined PKG_ID set PKG_ID=my-package
call :validate_pkg_id "%PKG_ID%" || exit /b 1

set /p PKG_OP_ID=OPSI Product ID (e.g., auto-my-package):
call :validate_op_id "%PKG_OP_ID%" || exit /b 1

set /p PKG_NAME=Package Name:
if not defined PKG_NAME (
    echo Error: Package name is required.
    exit /b 1
)

set /p PKG_DESC=Package Description:
if not defined PKG_DESC (
    echo Error: Package description is required.
    exit /b 1
)

set /p PKG_ENABLED=Enabled (true/false) [true]:
if not defined PKG_ENABLED set PKG_ENABLED=true
if /i "%PKG_ENABLED%"=="false" (
    set /p PKG_DISABLED_REASON=Disabled reason:
    if not defined PKG_DISABLED_REASON (
        echo Error: disabled packages require a reason.
        exit /b 1
    )
) else (
    set "PKG_DISABLED_REASON="
)

set /p PKG_SOURCE_TYPE=Source Type (mozilla, winget_manifest, github_release, videolan, microsoft):
if not defined PKG_SOURCE_TYPE set PKG_SOURCE_TYPE=mozilla

rem Validate source type for enabled packages
if /i "%PKG_ENABLED%"=="true" (
    if /i "%PKG_SOURCE_TYPE%"=="manual" (
        echo Error: manual source type not allowed for enabled packages.
        exit /b 1
    )
    if /i not "%PKG_SOURCE_TYPE%"=="mozilla" if /i not "%PKG_SOURCE_TYPE%"=="winget_manifest" if /i not "%PKG_SOURCE_TYPE%"=="github_release" if /i not "%PKG_SOURCE_TYPE%"=="videolan" if /i not "%PKG_SOURCE_TYPE%"=="microsoft" (
        echo Error: unrecognized source type '%PKG_SOURCE_TYPE%' for enabled package.
        exit /b 1
    )
)

set "NEW_PACKAGE=  - id: %PKG_ID%"
set "NEW_PACKAGE=!NEW_PACKAGE!\n    opsi_product_id: %PKG_OP_ID%"
set "NEW_PACKAGE=!NEW_PACKAGE!\n    name: \"%PKG_NAME%\""
set "NEW_PACKAGE=!NEW_PACKAGE!\n    description: \"%PKG_DESC%\""
set "NEW_PACKAGE=!NEW_PACKAGE!\n    enabled: %PKG_ENABLED%"
if /i "%PKG_ENABLED%"=="false" if defined PKG_DISABLED_REASON (
    set "NEW_PACKAGE=!NEW_PACKAGE!\n    disabled_reason: \"%PKG_DISABLED_REASON%\""
)

rem Source configuration
set "SOURCE_CONFIG="

if /i "%PKG_SOURCE_TYPE%"=="mozilla" (
    set /p MOZ_PRODUCT=Mozilla Product (firefox, thunderbird):
    if not defined MOZ_PRODUCT (
        echo Error: Mozilla product is required.
        exit /b 1
    )
    set /p MOZ_CHANNEL=Mozilla Channel (release, esr, beta, aurora) [release]:
    if not defined MOZ_CHANNEL set MOZ_CHANNEL=release
    set /p MOZ_DOWNLOAD_URL=Download URL Template (required, e.g., https://download.mozilla.org/?product={product}-{channel}-latest-ssl&os=win64&lang=en-US):
    if not defined MOZ_DOWNLOAD_URL (
        echo Error: download_url_template is required for mozilla source.
        exit /b 1
    )
    set /p MOZ_VERSION_URL=Version URL (optional):
    set /p MOZ_VERSION_FIELD=Version Field (optional):
    call :prompt_required_hosts MOZ_HOSTS
    set "SOURCE_CONFIG=    source:\n      type: mozilla\n      product: %MOZ_PRODUCT%\n      channel: %MOZ_CHANNEL%\n      download_url_template: \"%MOZ_DOWNLOAD_URL%\""
    if defined MOZ_VERSION_URL set "SOURCE_CONFIG=!SOURCE_CONFIG!\n      version_url: \"%MOZ_VERSION_URL%\""
    if defined MOZ_VERSION_FIELD set "SOURCE_CONFIG=!SOURCE_CONFIG!\n      version_field: \"%MOZ_VERSION_FIELD%\""
    set "SOURCE_CONFIG=!SOURCE_CONFIG!\n      allowed_hosts:"
    for %%h in (!MOZ_HOSTS!) do set "SOURCE_CONFIG=!SOURCE_CONFIG!\n        - %%h"

) else if /i "%PKG_SOURCE_TYPE%"=="winget_manifest" (
    set /p WINGET_ID=Winget Package Identifier (e.g., Google.Chrome):
    if not defined WINGET_ID (
        echo Error: Winget package identifier is required.
        exit /b 1
    )
    call :prompt_required_hosts WINGET_HOSTS
    set "SOURCE_CONFIG=    source:\n      type: winget_manifest\n      package_identifier: \"%WINGET_ID%\"\n      allowed_hosts:"
    for %%h in (!WINGET_HOSTS!) do set "SOURCE_CONFIG=!SOURCE_CONFIG!\n        - %%h"

) else if /i "%PKG_SOURCE_TYPE%"=="github_release" (
    set /p GH_REPO=GitHub Repo (format: user/repo):
    if not defined GH_REPO (
        echo Error: GitHub repo is required.
        exit /b 1
    )
    set /p GH_RELEASE_TYPE=Release Type (latest, tag) [latest]:
    if not defined GH_RELEASE_TYPE set GH_RELEASE_TYPE=latest
    set /p GH_PRERELEASE=Prerelease (true/false) [false]:
    if not defined GH_PRERELEASE set GH_PRERELEASE=false
    set /p GH_ASSET_REGEX=Asset Regex (e.g., '.*\.exe$'):
    if not defined GH_ASSET_REGEX (
        echo Error: Asset regex is required for github_release.
        exit /b 1
    )
    if /i "%GH_RELEASE_TYPE%"=="tag" (
        set /p GH_TAG=Tag (required when release_type=tag):
        if not defined GH_TAG (
            echo Error: Tag is required when release_type=tag.
            exit /b 1
        )
    )
    set /p GH_HOSTS=Allowed Hosts (comma-separated) [github.com,release-assets.githubusercontent.com,objects.githubusercontent.com]:
    if not defined GH_HOSTS set GH_HOSTS=github.com,release-assets.githubusercontent.com,objects.githubusercontent.com
    set "SOURCE_CONFIG=    source:\n      type: github_release\n      repo: \"%GH_REPO%\"\n      release_type: %GH_RELEASE%\n      prerelease: %GH_PRERELEASE%\n      asset_regex: \"%GH_ASSET_REGEX%\""
    if /i "%GH_RELEASE_TYPE%"=="tag" if defined GH_TAG set "SOURCE_CONFIG=!SOURCE_CONFIG!\n      tag: \"%GH_TAG%\""
    set "SOURCE_CONFIG=!SOURCE_CONFIG!\n      allowed_hosts:"
    for %%h in (!GH_HOSTS!) do set "SOURCE_CONFIG=!SOURCE_CONFIG!\n        - %%h"

) else if /i "%PKG_SOURCE_TYPE%"=="videolan" (
    set /p VL_VERSION_URL=Version URL (e.g., https://download.videolan.org/pub/videolan/vlc/):
    if not defined VL_VERSION_URL (
        echo Error: version_url is required for videolan source.
        exit /b 1
    )
    set /p VL_VERSION_REGEX=Version Regex (e.g., href=\"(\\d+\\.\\d+\\.\\d+)/\"):
    if not defined VL_VERSION_REGEX (
        echo Error: version_regex is required for videolan source.
        exit /b 1
    )
    set /p VL_DOWNLOAD_URL=Download URL Template (required, e.g., https://download.videolan.org/pub/videolan/vlc/{version}/win64/vlc-{version}-win64.exe):
    if not defined VL_DOWNLOAD_URL (
        echo Error: download_url_template is required for videolan source.
        exit /b 1
    )
    call :prompt_required_hosts VL_HOSTS
    set "SOURCE_CONFIG=    source:\n      type: videolan\n      version_url: \"%VL_VERSION_URL%\"\n      version_regex: \"%VL_VERSION_REGEX%\"\n      download_url_template: \"%VL_DOWNLOAD_URL%\"\n      allowed_hosts:"
    for %%h in (!VL_HOSTS!) do set "SOURCE_CONFIG=!SOURCE_CONFIG!\n        - %%h"

) else if /i "%PKG_SOURCE_TYPE%"=="microsoft" (
    set /p MS_API_URL=API URL (e.g., https://update.code.visualstudio.com/api/update/win32-x64/stable/latest):
    if not defined MS_API_URL (
        echo Error: api_url is required for microsoft source.
        exit /b 1
    )
    call :prompt_required_hosts MS_HOSTS
    set "SOURCE_CONFIG=    source:\n      type: microsoft\n      api_url: \"%MS_API_URL%\"\n      allowed_hosts:"
    for %%h in (!MS_HOSTS!) do set "SOURCE_CONFIG=!SOURCE_CONFIG!\n        - %%h"

) else (
    rem manual or unrecognized - only allowed for disabled packages
    if /i "%PKG_ENABLED%"=="true" (
        echo Error: source type '%PKG_SOURCE_TYPE%' not allowed for enabled packages.
        exit /b 1
    )
    set "SOURCE_CONFIG=    source:\n      type: manual"
)

set "NEW_PACKAGE=!NEW_PACKAGE!\n%SOURCE_CONFIG%"

rem Architecture - must be exactly x64
set /p PKG_ARCH=Architecture [x64]:
if not defined PKG_ARCH set PKG_ARCH=x64
if /i not "%PKG_ARCH%"=="x64" (
    echo Error: Architecture must be exactly 'x64'.
    exit /b 1
)
set "NEW_PACKAGE=!NEW_PACKAGE!\n    architecture:\n      - x64"

rem Installer type
set /p PKG_INST_TYPE=Installer Type (exe, msi, msix, zip) [exe]:
if not defined PKG_INST_TYPE set PKG_INST_TYPE=exe
if /i not "%PKG_INST_TYPE%"=="exe" if /i not "%PKG_INST_TYPE%"=="msi" if /i not "%PKG_INST_TYPE%"=="msix" if /i not "%PKG_INST_TYPE%"=="zip" (
    echo Error: unsupported installer type. Use exe, msi, msix, or zip.
    exit /b 1
)

set /p PKG_SILENT_ARGS=Silent Args (space-separated, e.g., '/S'):
if /i "%PKG_INST_TYPE%"=="exe" if not defined PKG_SILENT_ARGS (
    echo Error: exe installers require silent arguments.
    exit /b 1
)
if /i "%PKG_INST_TYPE%"=="msi" if not defined PKG_SILENT_ARGS (
    echo Error: msi installers require silent arguments.
    exit /b 1
)
if /i "%PKG_INST_TYPE%"=="zip" (
    set /p PKG_TARGET_DIR=Target Directory (required for zip):
    if not defined PKG_TARGET_DIR (
        echo Error: zip installers require target_dir.
        exit /b 1
    )
)

set "NEW_PACKAGE=!NEW_PACKAGE!\n    installer:\n      type: %PKG_INST_TYPE%"
if defined PKG_SILENT_ARGS (
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      silent_args:"
    for %%a in (%PKG_SILENT_ARGS%) do set "NEW_PACKAGE=!NEW_PACKAGE!\n        - %%a"
)
if /i "%PKG_INST_TYPE%"=="zip" if defined PKG_TARGET_DIR (
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      target_dir: \"%PKG_TARGET_DIR%\""
)

rem Detection method
set /p PKG_DET_METHOD=Detection Method (registry, file_version, custom) [registry]:
if not defined PKG_DET_METHOD set PKG_DET_METHOD=registry

set "NEW_PACKAGE=!NEW_PACKAGE!\n    detection:\n      method: %PKG_DET_METHOD%"

if /i "%PKG_DET_METHOD%"=="registry" (
    set /p PKG_DISPLAY_NAME=Display Name Regex:
    if not defined PKG_DISPLAY_NAME (
        echo Error: registry detection requires a display name regex.
        exit /b 1
    )
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      display_name_regex: \"%PKG_DISPLAY_NAME%\""
) else if /i "%PKG_DET_METHOD%"=="file_version" (
    set /p PKG_DET_PATH=File Path for version detection (e.g., C:\Program Files\App\app.exe):
    if not defined PKG_DET_PATH (
        echo Error: file_version detection requires a file path.
        exit /b 1
    )
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      path: \"%PKG_DET_PATH%\""
) else if /i "%PKG_DET_METHOD%"=="custom" (
    set /p PKG_DET_SCRIPT=Custom Detection Script (PowerShell, returns $true/$false):
    if not defined PKG_DET_SCRIPT (
        echo Error: custom detection requires a script.
        exit /b 1
    )
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      script: \"%PKG_DET_SCRIPT%\""
) else (
    echo Error: unknown detection method '%PKG_DET_METHOD%'.
    exit /b 1
)

rem Uninstall method
set /p PKG_UNINST_METHOD=Uninstall Method (registry, msi, vendor, command, msix, zip) [registry]:
if not defined PKG_UNINST_METHOD set PKG_UNINST_METHOD=registry

set "NEW_PACKAGE=!NEW_PACKAGE!\n    uninstall:\n      method: %PKG_UNINST_METHOD%"

if /i "%PKG_UNINST_METHOD%"=="registry" (
    set /p PKG_UNINST_DISPLAY_NAME=Uninstall Display Name Regex:
    if defined PKG_UNINST_DISPLAY_NAME set "NEW_PACKAGE=!NEW_PACKAGE!\n      display_name_regex: \"%PKG_UNINST_DISPLAY_NAME%\""
    set /p PKG_UNINST_SILENT_ARGS=Uninstall Silent Args (space-separated):
    if defined PKG_UNINST_SILENT_ARGS (
        set "NEW_PACKAGE=!NEW_PACKAGE!\n      silent_args:"
        for %%a in (%PKG_UNINST_SILENT_ARGS%) do set "NEW_PACKAGE=!NEW_PACKAGE!\n        - %%a"
    )
) else if /i "%PKG_UNINST_METHOD%"=="msi" (
    set /p PKG_UNINST_PRODUCT_CODE=MSI Product Code (GUID):
    if not defined PKG_UNINST_PRODUCT_CODE (
        echo Error: msi uninstall requires product_code.
        exit /b 1
    )
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      product_code: \"%PKG_UNINST_PRODUCT_CODE%\""
) else if /i "%PKG_UNINST_METHOD%"=="vendor" (
    set /p PKG_UNINST_VENDOR=Vendor Name:
    if not defined PKG_UNINST_VENDOR (
        echo Error: vendor uninstall requires vendor name.
        exit /b 1
    )
    set /p PKG_UNINST_SILENT_ARGS=Uninstall Silent Args (space-separated):
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      vendor: \"%PKG_UNINST_VENDOR%\""
    if defined PKG_UNINST_SILENT_ARGS (
        set "NEW_PACKAGE=!NEW_PACKAGE!\n      silent_args:"
        for %%a in (%PKG_UNINST_SILENT_ARGS%) do set "NEW_PACKAGE=!NEW_PACKAGE!\n        - %%a"
    )
) else if /i "%PKG_UNINST_METHOD%"=="command" (
    set /p PKG_UNINST_CMD=Uninstall Command:
    if not defined PKG_UNINST_CMD (
        echo Error: command uninstall requires command.
        exit /b 1
    )
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      command: \"%PKG_UNINST_CMD%\""
) else if /i "%PKG_UNINST_METHOD%"=="msix" (
    set /p PKG_UNINST_PKG_NAME=MSIX Package Name:
    if not defined PKG_UNINST_PKG_NAME (
        echo Error: msix uninstall requires package_name.
        exit /b 1
    )
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      package_name: \"%PKG_UNINST_PKG_NAME%\""
) else if /i "%PKG_UNINST_METHOD%"=="zip" (
    set /p PKG_UNINST_TARGET_DIR=Target Directory to remove:
    if not defined PKG_UNINST_TARGET_DIR (
        echo Error: zip uninstall requires target_dir.
        exit /b 1
    )
    set "NEW_PACKAGE=!NEW_PACKAGE!\n      target_dir: \"%PKG_UNINST_TARGET_DIR%\""
) else (
    echo Error: unknown uninstall method '%PKG_UNINST_METHOD%'.
    exit /b 1
)

set /p PKG_REDIST=Redistribution (internal_only, allowed) [internal_only]:
if not defined PKG_REDIST set PKG_REDIST=internal_only
if /i not "%PKG_REDIST%"=="internal_only" if /i not "%PKG_REDIST%"=="allowed" (
    echo Error: redistribution must be 'internal_only' or 'allowed'.
    exit /b 1
)
set "NEW_PACKAGE=!NEW_PACKAGE!\n    redistribution: %PKG_REDIST%"

set /p PKG_REV=Package Revision [1]:
if not defined PKG_REV set PKG_REV=1
set "NEW_PACKAGE=!NEW_PACKAGE!\n    package_revision: %PKG_REV%"

rem Write the complete package entry to file
(
    echo %NEW_PACKAGE%
) >> "%PACKAGES_FILE%"

echo.
echo Package '%PKG_ID%' has been added to %PACKAGES_FILE%
echo Please review the file to ensure correct YAML formatting.

endlocal
exit /b 0

:escape_yaml
rem Escape backslashes and double quotes in a variable
set "var=%1"
if defined !var! (
    set "val=!!var!!"
    set "val=!val:\=\\!"
    set "val=!val:"=\"!"
    set "%var%=!val!"
)
exit /b 0

:validate_pkg_id
rem Validate PKG_ID format
set "test_id=%~1"
echo %test_id% | findstr /r "^[a-z0-9][a-z0-9-]*$" >nul
if errorlevel 1 (
    echo Error: Package ID must contain only lowercase letters, numbers, and hyphens, starting with alphanumeric.
    exit /b 1
)
rem Check length (max 32 chars for id part after prefix)
set "len=0"
:set_len_loop
if not "!test_id:~%len%,1!"=="" set /a len+=1 & goto set_len_loop
if %len% gtr 32 (
    echo Error: Package ID too long (max 32 characters).
    exit /b 1
)
exit /b 0

:validate_op_id
rem Validate OPSI Product ID format: ^[a-z0-9][a-z0-9-]{0,31}$
set "test_id=%~1"
echo %test_id% | findstr /r "^[a-z0-9][a-z0-9-]*$" >nul
if errorlevel 1 (
    echo Error: OPSI Product ID must contain only lowercase letters, numbers, and hyphens, starting with alphanumeric.
    exit /b 1
)
set "len=0"
:set_op_len_loop
if not "!test_id:~%len%,1!"=="" set /a len+=1 & goto set_op_len_loop
if %len% gtr 32 (
    echo Error: OPSI Product ID too long (max 32 characters).
    exit /b 1
)
exit /b 0

:prompt_required_hosts
rem Prompt for allowed_hosts and reject blank input for enabled packages
set "host_var=%1"
set /p %host_var%=Allowed Hosts (comma-separated, required):
if not defined !host_var! (
    echo Error: allowed_hosts is required for enabled packages.
    exit /b 1
)
rem Convert commas to spaces for FOR loop
set "%host_var%=!!host_var:,= !"
exit /b 0