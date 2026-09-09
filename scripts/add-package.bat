@echo off
setlocal

rem Helper script to add a new package to packages.yaml
set PACKAGES_FILE=catalog\packages.yaml

if not exist "%PACKAGES_FILE%" (
    echo Error: %PACKAGES_FILE% not found!
    exit /b 1
)

echo.
echo === Adding New Package to packages.yaml ===
echo.

set /p PKG_ID=Package ID (e.g., my-package): 
set /p PKG_OP_ID=OPSI Product ID (e.g., auto-my-package): 
set /p PKG_NAME=Package Name: 
set /p PKG_DESC=Package Description: 
set /p PKG_ENABLED=Enabled (true/false) [true]: 
if not defined PKG_ENABLED set PKG_ENABLED=true
set /p PKG_SOURCE_TYPE=Source Type (mozilla, winget_manifest, github_release, videolan, microsoft, manual): 

set "NEW_PACKAGE=    - id: %PKG_ID%"
>>"%PACKAGES_FILE%" echo(%NEW_PACKAGE%
>>"%PACKAGES_FILE%" echo(    opsi_product_id: %PKG_OP_ID%
>>"%PACKAGES_FILE%" echo(    name: "%PKG_NAME%"
>>"%PACKAGES_FILE%" echo(    description: "%PKG_DESC%"
>>"%PACKAGES_FILE%" echo(    enabled: %PKG_ENABLED%

rem Add source section based on type
if /i "%PKG_SOURCE_TYPE%"=="mozilla" (
    set /p MOZ_PRODUCT=Mozilla Product (firefox, thunderbird): 
    set /p MOZ_CHANNEL=Mozilla Channel (release, esr, beta, aurora) [release]: 
    if not defined MOZ_CHANNEL set MOZ_CHANNEL=release
    set /p MOZ_VERSION_URL=Version URL (optional): 
    set /p MOZ_VERSION_FIELD=Version Field (optional): 
    >>"%PACKAGES_FILE%" echo(    source:
    >>"%PACKAGES_FILE%" echo(      type: mozilla
    >>"%PACKAGES_FILE%" echo(      product: %MOZ_PRODUCT%
    >>"%PACKAGES_FILE%" echo(      channel: %MOZ_CHANNEL%
    if defined MOZ_VERSION_URL >>"%PACKAGES_FILE%" echo(      version_url: %MOZ_VERSION_URL%
    if defined MOZ_VERSION_FIELD >>"%PACKAGES_FILE%" echo(      version_field: %MOZ_VERSION_FIELD%
) else if /i "%PKG_SOURCE_TYPE%"=="winget_manifest" (
    set /p WINGET_ID=Winget Package Identifier (e.g., Google.Chrome): 
    set /p WINGET_HOSTS=Allowed Hosts (comma-separated): 
    >>"%PACKAGES_FILE%" echo(    source:
    >>"%PACKAGES_FILE%" echo(      type: winget_manifest
    >>"%PACKAGES_FILE%" echo(      package_identifier: %WINGET_ID%
    if defined WINGET_HOSTS (
        >>"%PACKAGES_FILE%" echo(      allowed_hosts:
        for %%h in (%WINGET_HOSTS%) do >>"%PACKAGES_FILE%" echo(        - %%h
    )
) else if /i "%PKG_SOURCE_TYPE%"=="github_release" (
    set /p GH_REPO=GitHub Repo (format: user/repo): 
    set /p GH_RELEASE_TYPE=Release Type (latest, tag) [latest]: 
    if not defined GH_RELEASE_TYPE set GH_RELEASE_TYPE=latest
    set /p GH_PRERELEASE=Prerelease (true/false) [false]: 
    if not defined GH_PRERELEASE set GH_PRERELEASE=false
    set /p GH_ASSET_REGEX=Asset Regex (e.g., '.*\.exe$'): 
    set /p GH_HOSTS=Allowed Hosts (comma-separated) [github.com,release-assets.githubusercontent.com,objects.githubusercontent.com]: 
    if not defined GH_HOSTS set GH_HOSTS=github.com,release-assets.githubusercontent.com,objects.githubusercontent.com
    >>"%PACKAGES_FILE%" echo(    source:
    >>"%PACKAGES_FILE%" echo(      type: github_release
    >>"%PACKAGES_FILE%" echo(      repo: %GH_REPO%
    >>"%PACKAGES_FILE%" echo(      release_type: %GH_RELEASE_TYPE%
    >>"%PACKAGES_FILE%" echo(      prerelease: %GH_PRERELEASE%
    if defined GH_ASSET_REGEX >>"%PACKAGES_FILE%" echo(      asset_regex: %GH_ASSET_REGEX%
    >>"%PACKAGES_FILE%" echo(      allowed_hosts:
    for %%h in (%GH_HOSTS%) do >>"%PACKAGES_FILE%" echo(        - %%h
) else if /i "%PKG_SOURCE_TYPE%"=="videolan" (
    set /p VL_VERSION_URL=Version URL (e.g., https://download.videolan.org/pub/videolan/vlc/): 
    set /p VL_VERSION_REGEX=Version Regex (e.g., href="(\\d+\\.\\d+\\.\\d+)/"): 
    set /p VL_DOWNLOAD_URL=Download URL Template (optional): 
    set /p VL_HOSTS=Allowed Hosts (comma-separated): 
    >>"%PACKAGES_FILE%" echo(    source:
    >>"%PACKAGES_FILE%" echo(      type: videolan
    if defined VL_VERSION_URL >>"%PACKAGES_FILE%" echo(      version_url: %VL_VERSION_URL%
    if defined VL_VERSION_REGEX >>"%PACKAGES_FILE%" echo(      version_regex: %VL_VERSION_REGEX%
    if defined VL_DOWNLOAD_URL >>"%PACKAGES_FILE%" echo(      download_url_template: %VL_DOWNLOAD_URL%
    if defined VL_HOSTS (
        >>"%PACKAGES_FILE%" echo(      allowed_hosts:
        for %%h in (%VL_HOSTS%) do >>"%PACKAGES_FILE%" echo(        - %%h
    )
) else if /i "%PKG_SOURCE_TYPE%"=="microsoft" (
    set /p MS_API_URL=API URL (e.g., https://update.code.visualstudio.com/api/update/win32-x64/stable/latest): 
    set /p MS_HOSTS=Allowed Hosts (comma-separated): 
    >>"%PACKAGES_FILE%" echo(    source:
    >>"%PACKAGES_FILE%" echo(      type: microsoft
    if defined MS_API_URL >>"%PACKAGES_FILE%" echo(      api_url: %MS_API_URL%
    if defined MS_HOSTS (
        >>"%PACKAGES_FILE%" echo(      allowed_hosts:
        for %%h in (%MS_HOSTS%) do >>"%PACKAGES_FILE%" echo(        - %%h
    )
) else (
    echo Unsupported source type. Using minimal source configuration.
    >>"%PACKAGES_FILE%" echo(    source:
    >>"%PACKAGES_FILE%" echo(      type: manual
)

rem Add common sections
set /p PKG_ARCH=Architecture (comma-separated) [x64]: 
if not defined PKG_ARCH set PKG_ARCH=x64
set "PKG_ARCH=%PKG_ARCH:,= %"
>>"%PACKAGES_FILE%" echo(    architecture:
for %%a in (%PKG_ARCH%) do >>"%PACKAGES_FILE%" echo(      - %%a

set /p PKG_INST_TYPE=Installer Type (exe, msi, nullsoft, etc.) [exe]: 
if not defined PKG_INST_TYPE set PKG_INST_TYPE=exe
set /p PKG_SILENT_ARGS=Silent Args (space-separated, e.g., '/S'): 
>>"%PACKAGES_FILE%" echo(    installer:
>>"%PACKAGES_FILE%" echo(      type: %PKG_INST_TYPE%
if defined PKG_SILENT_ARGS (
    >>"%PACKAGES_FILE%" echo(      silent_args:
    for %%a in (%PKG_SILENT_ARGS%) do >>"%PACKAGES_FILE%" echo(        - %%a
)

set /p PKG_DET_METHOD=Detection Method (registry, file, script) [registry]: 
if not defined PKG_DET_METHOD set PKG_DET_METHOD=registry
set /p PKG_DISPLAY_NAME=Display Name Regex (optional): 
>>"%PACKAGES_FILE%" echo(    detection:
>>"%PACKAGES_FILE%" echo(      method: %PKG_DET_METHOD%
if defined PKG_DISPLAY_NAME >>"%PACKAGES_FILE%" echo(      display_name_regex: %PKG_DISPLAY_NAME%

set /p PKG_UNINST_METHOD=Uninstall Method (registry, file, script) [registry]: 
if not defined PKG_UNINST_METHOD set PKG_UNINST_METHOD=registry
set /p PKG_UNINST_SILENT_ARGS=Uninstall Silent Args (space-separated, same as installer): 
>>"%PACKAGES_FILE%" echo(    uninstall:
>>"%PACKAGES_FILE%" echo(      method: %PKG_UNINST_METHOD%
if defined PKG_UNINST_SILENT_ARGS (
    >>"%PACKAGES_FILE%" echo(      silent_args:
    for %%a in (%PKG_UNINST_SILENT_ARGS%) do >>"%PACKAGES_FILE%" echo(        - %%a
)

set /p PKG_REDIST=Redistribution (internal_only, external) [internal_only]: 
if not defined PKG_REDIST set PKG_REDIST=internal_only
>>"%PACKAGES_FILE%" echo(    redistribution: %PKG_REDIST%

set /p PKG_REV=Package Revision [1]: 
if not defined PKG_REV set PKG_REV=1
>>"%PACKAGES_FILE%" echo(    package_revision: %PKG_REV%

echo.
echo Package '%PKG_ID%' has been added to %PACKAGES_FILE%
echo Please review the file to ensure correct YAML formatting.

endlocal
