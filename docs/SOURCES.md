# Source and format verification

Verified against the installed OPSI 4.3 CLI and official documentation on 2026-09-07:

- [OPSI 4.3 command-line tools](https://docs.opsi.org/opsi-docs-en/4.3/server/components/commandline.html): `opsi-cli package make SOURCE_DIR DESTINATION_DIR` creates the package, MD5 and zsync sidecars.
- [OPSI 4.3 software integration](https://docs.opsi.org/opsi-docs-en/4.3/clients/windows-client/softwareintegration.html): `OPSI/control.toml`, `[Product].version`, `[Package].version` and script fields.
- [OPSI Script secondary sections](https://docs.opsi.org/opsi-docs-en/4.3/opsi-script-manual/sec-section.html): `Winbatch /SysNative` and `getLastExitCode`.
- Installed help verified `package extract PACKAGE_ARCHIVE DESTINATION_DIR`, `manage-repo metafile create DIRECTORY`, and `manage-repo metafile scan-packages DIRECTORY`. Actual package make/extract and metadata generation are part of the local validation.

The builder derives from the official `uibmz/opsi-server:4.3` image for its current package tooling. Its server entrypoint is replaced, it runs as an unprivileged UID, and it has no server credentials or connection to the existing deployment. The base image is larger than a bespoke tools-only image; this avoids downloading an unverified binary or inventing install/CLI syntax. Pin `OPSI_BASE_IMAGE` to a reviewed digest for controlled image updates.

Official metadata origins include Mozilla product-details and archive infrastructure, GitHub's REST API, Microsoft's VS Code update API, Microsoft's `winget-pkgs` repository, VideoLAN's own release directory, the Document Foundation's release directory, and Adoptium's API. Installer origins and all redirected hosts are separately restricted in the catalog. A GitHub domain alone does not identify a vendor: GitHub release recipes bind the API request to an official repository, while WinGet recipes using GitHub also restrict the project path.

Notable verified changes:

- [7-Zip's official download page](https://www.7-zip.org/download.html) now links current Windows installers to `github.com/ip7z/7zip`. Allowing that official project is deliberate. Microsoft metadata may lag the latest vendor release.
- SumatraPDF's GitHub release records have no installer assets. Its [official installer documentation](https://www.sumatrapdfreader.org/docs/Installer-cmd-line-arguments) and Microsoft metadata identify vendor-hosted installers and machine install switches.
- Audacity 4.0.0 uses `audacity-win-4.0.0-x86_64.msi`, so the current recipe selects MSI rather than falling back to an old EXE.
- [RustDesk's deployment documentation](https://rustdesk.com/docs/en/self-host/client-deployment/) documents its direct EXE silent installer. RustDesk never uses WinGet here.

No redistribution permission is inferred from a working URL, a GitHub repository, or inclusion in WinGet. Every enabled entry defaults conservatively to `internal_only`; administrators remain responsible for vendor terms and any corresponding-source, attribution, trademark or commercial licensing obligations.

Live installer validation also established that VideoLAN, the Document Foundation and GIMP distribute these Windows binaries through external mirror operators. Such mirrors can be legitimate members of the projects' distribution networks; they are not download aggregators. This catalog nevertheless follows the request's strict direct-vendor policy and leaves those three recipes disabled instead of silently expanding host trust. Re-enabling requires an administrator decision about approved project-listed mirrors and their checksum validation, or a verified vendor-operated direct endpoint. SumatraPDF's `files2.sumatrapdfreader.org` redirect remains inside vendor infrastructure and is allowed.
