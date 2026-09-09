#!/bin/bash
# Helper script to add a new package to packages.yaml

PACKAGES_FILE="catalog/packages.yaml"
if [ ! -f "$PACKAGES_FILE" ]; then
    echo "Error: $PACKAGES_FILE not found!"
    exit 1
fi

fail() {
    echo "Error: $1" >&2
    exit 1
}

escape_yaml() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '%s' "$value"
}

read -p "Package ID (e.g., my-package): " PKG_ID
read -p "OPSI Product ID (e.g., auto-my-package): " PKG_OP_ID
read -p "Package Name: " PKG_NAME
read -p "Package Description: " PKG_DESC
read -p "Enabled (true/false) [true]: " PKG_ENABLED
PKG_ENABLED=${PKG_ENABLED:-true}

if [[ ! "$PKG_ID" =~ ^[a-z0-9-]+$ ]] || [ -z "$PKG_ID" ] || [ ${#PKG_ID} -gt 32 ]; then
    fail "PKG_ID must be non-empty, lowercase alphanumeric with dashes, max 32 chars"
fi
if [[ ! "$PKG_OP_ID" =~ ^[a-z0-9][a-z0-9-]{0,31}$ ]]; then
    fail "PKG_OP_ID must match ^[a-z0-9][a-z0-9-]{0,31}$"
fi
[ -n "$PKG_NAME" ] || fail "PKG_NAME is required"
[ -n "$PKG_DESC" ] || fail "PKG_DESC is required"

PKG_ENABLED_LOWER=$(echo "$PKG_ENABLED" | tr '[:upper:]' '[:lower:]')
if [[ "$PKG_ENABLED_LOWER" != "true" && "$PKG_ENABLED_LOWER" != "false" ]]; then
    fail "Enabled must be exactly 'true' or 'false' (case-insensitive)"
fi
PKG_ENABLED="$PKG_ENABLED_LOWER"

if [ "$PKG_ENABLED" = "false" ]; then
    read -p "Disabled reason: " PKG_DISABLED_REASON
    [ -n "$PKG_DISABLED_REASON" ] || fail "disabled packages require a reason"
fi

read -p "Source Type (mozilla, winget_manifest, github_release, videolan, microsoft, manual): " PKG_SOURCE_TYPE

case "$PKG_SOURCE_TYPE" in
    mozilla|winget_manifest|github_release|videolan|microsoft|manual) ;;
    *) fail "Unsupported source type: $PKG_SOURCE_TYPE" ;;
esac

PKG_NAME_E=$(escape_yaml "$PKG_NAME")
PKG_DESC_E=$(escape_yaml "$PKG_DESC")
PKG_DISABLED_REASON_E=$(escape_yaml "$PKG_DISABLED_REASON")

NEW_PACKAGE="  - id: $PKG_ID"
NEW_PACKAGE+="\n    opsi_product_id: $PKG_OP_ID"
NEW_PACKAGE+="\n    name: \"$PKG_NAME_E\""
NEW_PACKAGE+="\n    description: \"$PKG_DESC_E\""
NEW_PACKAGE+="\n    enabled: $PKG_ENABLED"
if [ "$PKG_ENABLED" = "false" ]; then
    NEW_PACKAGE+="\n    disabled_reason: \"$PKG_DISABLED_REASON_E\""
fi

case "$PKG_SOURCE_TYPE" in
    mozilla)
        read -p "Mozilla Product (firefox, thunderbird): " MOZ_PRODUCT
        read -p "Mozilla Channel (release, esr, beta, aurora) [release]: " MOZ_CHANNEL
        MOZ_CHANNEL=${MOZ_CHANNEL:-release}
        read -p "Version URL: " MOZ_VERSION_URL
        read -p "Version Field: " MOZ_VERSION_FIELD
        read -p "Download URL Template: " MOZ_DOWNLOAD_URL_TEMPLATE
        read -p "Allowed Hosts (comma-separated): " MOZ_HOSTS
        [ -n "$MOZ_VERSION_URL" ] || fail "Mozilla version URL is required"
        [ -n "$MOZ_VERSION_FIELD" ] || fail "Mozilla version field is required"
        [ -n "$MOZ_DOWNLOAD_URL_TEMPLATE" ] || fail "Mozilla download URL template is required"
        [ -n "$MOZ_HOSTS" ] || fail "Mozilla allowed hosts are required"
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: mozilla"
        NEW_PACKAGE+="\n      product: $(escape_yaml "$MOZ_PRODUCT")"
        NEW_PACKAGE+="\n      channel: $MOZ_CHANNEL"
        NEW_PACKAGE+="\n      version_url: $(escape_yaml "$MOZ_VERSION_URL")"
        NEW_PACKAGE+="\n      version_field: $MOZ_VERSION_FIELD"
        NEW_PACKAGE+="\n      download_url_template: $(escape_yaml "$MOZ_DOWNLOAD_URL_TEMPLATE")"
        NEW_PACKAGE+="\n      allowed_hosts:"
        IFS=',' read -ra HOSTS <<< "$MOZ_HOSTS"
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $(escape_yaml "$host")"; done
        ;;
    winget_manifest)
        read -p "Winget Package Identifier (e.g., Google.Chrome): " WINGET_ID
        read -p "Allowed Hosts (comma-separated): " WINGET_HOSTS
        [ -n "$WINGET_ID" ] || fail "Winget package identifier is required"
        [ -n "$WINGET_HOSTS" ] || fail "Allowed hosts are required"
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: winget_manifest"
        NEW_PACKAGE+="\n      package_identifier: $(escape_yaml "$WINGET_ID")"
        NEW_PACKAGE+="\n      allowed_hosts:"
        IFS=',' read -ra HOSTS <<< "$WINGET_HOSTS"
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $(escape_yaml "$host")"; done
        ;;
    github_release)
        read -p "GitHub Repo (format: user/repo): " GH_REPO
        read -p "Release Type (latest, tag) [latest]: " GH_RELEASE_TYPE
        GH_RELEASE_TYPE=${GH_RELEASE_TYPE:-latest}
        read -p "Prerelease (true/false) [false]: " GH_PRERELEASE
        GH_PRERELEASE=${GH_PRERELEASE:-false}
        read -p "Asset Regex (e.g., '.*\\.exe$'): " GH_ASSET_REGEX
        read -p "Allowed Hosts (comma-separated) [github.com,release-assets.githubusercontent.com,objects.githubusercontent.com]: " GH_HOSTS
        GH_HOSTS=${GH_HOSTS:-github.com,release-assets.githubusercontent.com,objects.githubusercontent.com}
        [ -n "$GH_ASSET_REGEX" ] || fail "GitHub asset regex is required"
        [ -n "$GH_HOSTS" ] || fail "Allowed hosts are required"
        if [ "$GH_RELEASE_TYPE" = "tag" ]; then
            read -p "Git Tag (e.g., v1.2.3): " GH_TAG
            [ -n "$GH_TAG" ] || fail "GitHub tag release type requires a tag"
        fi
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: github_release"
        NEW_PACKAGE+="\n      repo: $(escape_yaml "$GH_REPO")"
        NEW_PACKAGE+="\n      release_type: $GH_RELEASE_TYPE"
        NEW_PACKAGE+="\n      prerelease: $GH_PRERELEASE"
        if [ "$GH_RELEASE_TYPE" = "tag" ]; then
            NEW_PACKAGE+="\n      tag: $(escape_yaml "$GH_TAG")"
        fi
        NEW_PACKAGE+="\n      asset_regex: $(escape_yaml "$GH_ASSET_REGEX")"
        NEW_PACKAGE+="\n      allowed_hosts:"
        IFS=',' read -ra HOSTS <<< "$GH_HOSTS"
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $(escape_yaml "$host")"; done
        ;;
    videolan)
        read -p "Version URL (e.g., https://download.videolan.org/pub/videolan/vlc/): " VL_VERSION_URL
        read -p "Version Regex (e.g., href=\"(\\d+\\.\\d+\\.\\d+)/\"): " VL_VERSION_REGEX
        read -p "Download URL Template: " VL_DOWNLOAD_URL
        read -p "Allowed Hosts (comma-separated): " VL_HOSTS
        [ -n "$VL_VERSION_URL" ] || fail "VideoLAN version URL is required"
        [ -n "$VL_VERSION_REGEX" ] || fail "VideoLAN version regex is required"
        [ -n "$VL_DOWNLOAD_URL" ] || fail "VideoLAN download URL template is required"
        [ -n "$VL_HOSTS" ] || fail "Allowed hosts are required"
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: videolan"
        NEW_PACKAGE+="\n      version_url: $(escape_yaml "$VL_VERSION_URL")"
        NEW_PACKAGE+="\n      version_regex: $(escape_yaml "$VL_VERSION_REGEX")"
        NEW_PACKAGE+="\n      download_url_template: $(escape_yaml "$VL_DOWNLOAD_URL")"
        NEW_PACKAGE+="\n      allowed_hosts:"
        IFS=',' read -ra HOSTS <<< "$VL_HOSTS"
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $(escape_yaml "$host")"; done
        ;;
    microsoft)
        read -p "API URL (e.g., https://update.code.visualstudio.com/api/update/win32-x64/stable/latest): " MS_API_URL
        read -p "Allowed Hosts (comma-separated): " MS_HOSTS
        [ -n "$MS_API_URL" ] || fail "Microsoft API URL is required"
        [ -n "$MS_HOSTS" ] || fail "Allowed hosts are required"
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: microsoft"
        NEW_PACKAGE+="\n      api_url: $(escape_yaml "$MS_API_URL")"
        NEW_PACKAGE+="\n      allowed_hosts:"
        IFS=',' read -ra HOSTS <<< "$MS_HOSTS"
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $(escape_yaml "$host")"; done
        ;;
    manual)
        echo "Using manual source configuration."
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: manual"
        ;;
esac

read -p "Architecture [x64]: " PKG_ARCH
PKG_ARCH=${PKG_ARCH:-x64}
if [ "$PKG_ARCH" != "x64" ]; then
    fail "Architecture must be exactly 'x64'"
fi
NEW_PACKAGE+="\n    architecture:"
NEW_PACKAGE+="\n      - x64"

read -p "Installer Type (exe, msi, msix, zip) [exe]: " PKG_INST_TYPE
PKG_INST_TYPE=${PKG_INST_TYPE:-exe}
case "$PKG_INST_TYPE" in
    exe|msi|msix|zip) ;;
    *) fail "Unsupported installer type: $PKG_INST_TYPE (use exe, msi, msix, or zip)" ;;
esac
read -p "Silent Args (space-separated, e.g., '/S'): " PKG_SILENT_ARGS
if [ "$PKG_INST_TYPE" = "exe" ] || [ "$PKG_INST_TYPE" = "msi" ]; then
    [ -n "$PKG_SILENT_ARGS" ] || fail "Installer type $PKG_INST_TYPE requires silent arguments"
fi
NEW_PACKAGE+="\n    installer:"
NEW_PACKAGE+="\n      type: $PKG_INST_TYPE"
if [ -n "$PKG_SILENT_ARGS" ]; then
    NEW_PACKAGE+="\n      silent_args:"
    IFS=' ' read -ra ARGS <<< "$PKG_SILENT_ARGS"
    for arg in "${ARGS[@]}"; do NEW_PACKAGE+="\n        - $(escape_yaml "$arg")"; done
fi
if [ "$PKG_INST_TYPE" = "zip" ]; then
    read -p "ZIP Target Directory (e.g., C:\\Program Files\\MyApp): " PKG_ZIP_TARGET_DIR
    [ -n "$PKG_ZIP_TARGET_DIR" ] || fail "ZIP installer requires target_dir"
    PKG_ZIP_TARGET_DIR_E=$(escape_yaml "$PKG_ZIP_TARGET_DIR")
    NEW_PACKAGE+="\n      target_dir: \"$PKG_ZIP_TARGET_DIR_E\""
fi

read -p "Detection Method (registry, file_version, custom) [registry]: " PKG_DET_METHOD
PKG_DET_METHOD=${PKG_DET_METHOD:-registry}
case "$PKG_DET_METHOD" in
    registry|file_version|custom) ;;
    *) fail "Unsupported detection method: $PKG_DET_METHOD (use registry, file_version, or custom)" ;;
esac
if [ "$PKG_DET_METHOD" = "registry" ]; then
    read -p "Display Name Regex: " PKG_DISPLAY_NAME
    [ -n "$PKG_DISPLAY_NAME" ] || fail "Registry detection requires a display name regex"
elif [ "$PKG_DET_METHOD" = "file_version" ]; then
    read -p "Detection Path: " PKG_DET_PATH
    [ -n "$PKG_DET_PATH" ] || fail "File_version detection requires a path"
elif [ "$PKG_DET_METHOD" = "custom" ]; then
    read -p "Detection Script: " PKG_DET_SCRIPT
    [ -n "$PKG_DET_SCRIPT" ] || fail "Custom detection requires a script"
fi
NEW_PACKAGE+="\n    detection:"
NEW_PACKAGE+="\n      method: $PKG_DET_METHOD"
if [ "$PKG_DET_METHOD" = "registry" ]; then
    NEW_PACKAGE+="\n      display_name_regex: $(escape_yaml "$PKG_DISPLAY_NAME")"
elif [ "$PKG_DET_METHOD" = "file_version" ]; then
    NEW_PACKAGE+="\n      path: $(escape_yaml "$PKG_DET_PATH")"
elif [ "$PKG_DET_METHOD" = "custom" ]; then
    NEW_PACKAGE+="\n      script: $(escape_yaml "$PKG_DET_SCRIPT")"
fi

read -p "Uninstall Method (registry, msi, command, vendor, zip, msix) [registry]: " PKG_UNINST_METHOD
PKG_UNINST_METHOD=${PKG_UNINST_METHOD:-registry}
case "$PKG_UNINST_METHOD" in
    registry|msi|command|vendor|zip|msix) ;;
    *) fail "Unsupported uninstall method: $PKG_UNINST_METHOD" ;;
esac
read -p "Uninstall Silent Args (space-separated, same as installer): " PKG_UNINST_SILENT_ARGS

case "$PKG_UNINST_METHOD" in
    msi)
        read -p "MSI Product Code (GUID): " PKG_UNINST_PRODUCT_CODE
        [ -n "$PKG_UNINST_PRODUCT_CODE" ] || fail "MSI uninstall requires product_code (GUID)"
        ;;
    vendor)
        read -p "Vendor Uninstall Command/Path: " PKG_UNINST_VENDOR_CMD
        [ -n "$PKG_UNINST_VENDOR_CMD" ] || fail "Vendor uninstall requires vendor uninstall command/path"
        ;;
    command)
        read -p "Explicit Uninstall Command: " PKG_UNINST_COMMAND
        [ -n "$PKG_UNINST_COMMAND" ] || fail "Command uninstall requires explicit command"
        ;;
    msix)
        read -p "MSIX Package Name: " PKG_UNINST_MSIX_NAME
        [ -n "$PKG_UNINST_MSIX_NAME" ] || fail "MSIX uninstall requires package_name"
        ;;
esac

NEW_PACKAGE+="\n    uninstall:"
NEW_PACKAGE+="\n      method: $PKG_UNINST_METHOD"
if [ -n "$PKG_UNINST_SILENT_ARGS" ]; then
    NEW_PACKAGE+="\n      silent_args:"
    IFS=' ' read -ra UARGS <<< "$PKG_UNINST_SILENT_ARGS"
    for arg in "${UARGS[@]}"; do NEW_PACKAGE+="\n        - $(escape_yaml "$arg")"; done
fi
if [ "$PKG_UNINST_METHOD" = "msi" ]; then
    NEW_PACKAGE+="\n      product_code: $(escape_yaml "$PKG_UNINST_PRODUCT_CODE")"
elif [ "$PKG_UNINST_METHOD" = "vendor" ]; then
    NEW_PACKAGE+="\n      vendor_command: $(escape_yaml "$PKG_UNINST_VENDOR_CMD")"
elif [ "$PKG_UNINST_METHOD" = "command" ]; then
    NEW_PACKAGE+="\n      command: $(escape_yaml "$PKG_UNINST_COMMAND")"
elif [ "$PKG_UNINST_METHOD" = "msix" ]; then
    NEW_PACKAGE+="\n      package_name: $(escape_yaml "$PKG_UNINST_MSIX_NAME")"
fi

read -p "Redistribution (internal_only, allowed, unknown) [internal_only]: " PKG_REDIST
PKG_REDIST=${PKG_REDIST:-internal_only}
case "$PKG_REDIST" in
    allowed|internal_only|unknown) ;;
    *) fail "Unsupported redistribution: $PKG_REDIST (use allowed, internal_only, or unknown)" ;;
esac
NEW_PACKAGE+="\n    redistribution: $PKG_REDIST"

read -p "Package Revision [1]: " PKG_REV
PKG_REV=${PKG_REV:-1}
if [[ ! "$PKG_REV" =~ ^[1-9][0-9]*$ ]]; then
    fail "Package Revision must be a positive integer"
fi
NEW_PACKAGE+="\n    package_revision: $PKG_REV"

if printf "\n%b\n" "$NEW_PACKAGE" >> "$PACKAGES_FILE"; then
    echo ""
    echo "Package '$PKG_ID' has been added to $PACKAGES_FILE"
    echo "Please review the file to ensure correct YAML formatting."
else
    fail "Failed to write package to $PACKAGES_FILE"
fi