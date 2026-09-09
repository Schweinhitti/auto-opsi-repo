#!/bin/bash
# Helper script to add a new package to packages.yaml

# Check if packages.yaml file exists
PACKAGES_FILE="catalog/packages.yaml"
if [ ! -f "$PACKAGES_FILE" ]; then
    echo "Error: $PACKAGES_FILE not found!"
    exit 1
fi

# Prompt for package information
echo "=== Adding New Package to packages.yaml ==="
read -p "Package ID (e.g., my-package): " PKG_ID
read -p "OPSI Product ID (e.g., auto-my-package): " PKG_OP_ID
read -p "Package Name: " PKG_NAME
read -p "Package Description: " PKG_DESC
read -p "Enabled (true/false) [true]: " PKG_ENABLED
PKG_ENABLED=${PKG_ENABLED:-true}
read -p "Source Type (mozilla, winget_manifest, github_release, videolan, microsoft, manual): " PKG_SOURCE_TYPE

# Basic template for the package entry
NEW_PACKAGE="  - id: $PKG_ID"
NEW_PACKAGE+="\n    opsi_product_id: $PKG_OP_ID"
NEW_PACKAGE+="\n    name: \"$PKG_NAME\""
NEW_PACKAGE+="\n    description: \"$PKG_DESC\""
NEW_PACKAGE+="\n    enabled: $PKG_ENABLED"

# Add source section based on type
case "$PKG_SOURCE_TYPE" in
    mozilla)
        read -p "Mozilla Product (firefox, thunderbird): " MOZ_PRODUCT
        read -p "Mozilla Channel (release, esr, beta, aurora) [release]: " MOZ_CHANNEL
        MOZ_CHANNEL=${MOZ_CHANNEL:-release}
        read -p "Version URL (optional): " MOZ_VERSION_URL
        read -p "Version Field (optional): " MOZ_VERSION_FIELD
        
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: mozilla"
        NEW_PACKAGE+="\n      product: $MOZ_PRODUCT"
        NEW_PACKAGE+="\n      channel: $MOZ_CHANNEL"
        [ -n "$MOZ_VERSION_URL" ] && NEW_PACKAGE+="\n      version_url: $MOZ_VERSION_URL"
        [ -n "$MOZ_VERSION_FIELD" ] && NEW_PACKAGE+="\n      version_field: $MOZ_VERSION_FIELD"
        ;;
    winget_manifest)
        read -p "Winget Package Identifier (e.g., Google.Chrome): " WINGET_ID
        read -p "Allowed Hosts (comma-separated): " WINGET_HOSTS
        
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: winget_manifest"
        NEW_PACKAGE+="\n      package_identifier: $WINGET_ID"
        [ -n "$WINGET_HOSTS" ] && NEW_PACKAGE+="\n      allowed_hosts:" && \
        IFS=',' read -ra HOSTS <<< "$WINGET_HOSTS" && \
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $host"; done
        ;;
    github_release)
        read -p "GitHub Repo (format: user/repo): " GH_REPO
        read -p "Release Type (latest, tag) [latest]: " GH_RELEASE_TYPE
        GH_RELEASE_TYPE=${GH_RELEASE_TYPE:-latest}
        read -p "Prerelease (true/false) [false]: " GH_PRERELEASE
        GH_PRERELEASE=${GH_PRERELEASE:-false}
read -r -p "Asset Regex (e.g., '.*\\.exe$'): " GH_ASSET_REGEX
        read -p "Allowed Hosts (comma-separated) [github.com,release-assets.githubusercontent.com,objects.githubusercontent.com]: " GH_HOSTS
        GH_HOSTS=${GH_HOSTS:-github.com,release-assets.githubusercontent.com,objects.githubusercontent.com}
        
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: github_release"
        NEW_PACKAGE+="\n      repo: $GH_REPO"
        NEW_PACKAGE+="\n      release_type: $GH_RELEASE_TYPE"
        NEW_PACKAGE+="\n      prerelease: $GH_PRERELEASE"
        [ -n "$GH_ASSET_REGEX" ] && NEW_PACKAGE+="\n      asset_regex: $GH_ASSET_REGEX"
        NEW_PACKAGE+="\n      allowed_hosts:" && \
        IFS=',' read -ra HOSTS <<< "$GH_HOSTS" && \
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $host"; done
        ;;
    videolan)
        read -p "Version URL (e.g., https://download.videolan.org/pub/videolan/vlc/): " VL_VERSION_URL
        read -p "Version Regex (e.g., href=\"(\\d+\\.\\d+\\.\\d+)/\"): " VL_VERSION_REGEX
        read -p "Download URL Template (optional): " VL_DOWNLOAD_URL
        read -p "Allowed Hosts (comma-separated): " VL_HOSTS
        
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: videolan"
        [ -n "$VL_VERSION_URL" ] && NEW_PACKAGE+="\n      version_url: $VL_VERSION_URL"
        [ -n "$VL_VERSION_REGEX" ] && NEW_PACKAGE+="\n      version_regex: $VL_VERSION_REGEX"
        [ -n "$VL_DOWNLOAD_URL" ] && NEW_PACKAGE+="\n      download_url_template: $VL_DOWNLOAD_URL"
        [ -n "$VL_HOSTS" ] && NEW_PACKAGE+="\n      allowed_hosts:" && \
        IFS=',' read -ra HOSTS <<< "$VL_HOSTS" && \
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $host"; done
        ;;
    microsoft)
        read -p "API URL (e.g., https://update.code.visualstudio.com/api/update/win32-x64/stable/latest): " MS_API_URL
        read -p "Allowed Hosts (comma-separated): " MS_HOSTS
        
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: microsoft"
        [ -n "$MS_API_URL" ] && NEW_PACKAGE+="\n      api_url: $MS_API_URL"
        [ -n "$MS_HOSTS" ] && NEW_PACKAGE+="\n      allowed_hosts:" && \
        IFS=',' read -ra HOSTS <<< "$MS_HOSTS" && \
        for host in "${HOSTS[@]}"; do NEW_PACKAGE+="\n        - $host"; done
        ;;
    manual)
        echo "Using manual source configuration."
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: manual"
        ;;
    *)
        echo "Unsupported source type. Using minimal source configuration."
        NEW_PACKAGE+="\n    source:"
        NEW_PACKAGE+="\n      type: manual"
        ;;
esac

# Add common sections
read -p "Architecture (comma-separated) [x64]: " PKG_ARCH
PKG_ARCH=${PKG_ARCH:-x64}
NEW_PACKAGE+="\n    architecture:"
IFS=',' read -ra ARCHS <<< "$PKG_ARCH"
for arch in "${ARCHS[@]}"; do NEW_PACKAGE+="\n      - $arch"; done

read -p "Installer Type (exe, msi, nullsoft, etc.) [exe]: " PKG_INST_TYPE
PKG_INST_TYPE=${PKG_INST_TYPE:-exe}
read -p "Silent Args (space-separated, e.g., '/S'): " PKG_SILENT_ARGS
NEW_PACKAGE+="\n    installer:"
NEW_PACKAGE+="\n      type: $PKG_INST_TYPE"
[ -n "$PKG_SILENT_ARGS" ] && NEW_PACKAGE+="\n      silent_args:" && \
IFS=' ' read -ra ARGS <<< "$PKG_SILENT_ARGS" && \
for arg in "${ARGS[@]}"; do NEW_PACKAGE+="\n        - $arg"; done

read -p "Detection Method (registry, file, script) [registry]: " PKG_DET_METHOD
PKG_DET_METHOD=${PKG_DET_METHOD:-registry}
read -p "Display Name Regex (optional): " PKG_DISPLAY_NAME
NEW_PACKAGE+="\n    detection:"
NEW_PACKAGE+="\n      method: $PKG_DET_METHOD"
[ -n "$PKG_DISPLAY_NAME" ] && NEW_PACKAGE+="\n      display_name_regex: $PKG_DISPLAY_NAME"

read -p "Uninstall Method (registry, file, script) [registry]: " PKG_UNINST_METHOD
PKG_UNINST_METHOD=${PKG_UNINST_METHOD:-registry}
read -p "Uninstall Silent Args (space-separated, same as installer): " PKG_UNINST_SILENT_ARGS
NEW_PACKAGE+="\n    uninstall:"
NEW_PACKAGE+="\n      method: $PKG_UNINST_METHOD"
[ -n "$PKG_UNINST_SILENT_ARGS" ] && NEW_PACKAGE+="\n      silent_args:" && \
IFS=' ' read -ra UARGS <<< "$PKG_UNINST_SILENT_ARGS" && \
for uarg in "${UARGS[@]}"; do NEW_PACKAGE+="\n        - $uarg"; done

read -p "Redistribution (internal_only, external) [internal_only]: " PKG_REDIST
PKG_REDIST=${PKG_REDIST:-internal_only}
NEW_PACKAGE+="\n    redistribution: $PKG_REDIST"

read -p "Package Revision [1]: " PKG_REV
PKG_REV=${PKG_REV:-1}
NEW_PACKAGE+="\n    package_revision: $PKG_REV"

# Add the new package to the YAML file
printf "\n%b\n" "$NEW_PACKAGE" >> "$PACKAGES_FILE"

echo ""
echo "Package '$PKG_ID' has been added to $PACKAGES_FILE"
echo "Please review the file to ensure correct YAML formatting."