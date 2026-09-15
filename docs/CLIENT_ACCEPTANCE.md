# Windows client acceptance

[Back to the documentation index](README.md)

Use this checklist for every new enabled recipe and for changes to installer arguments,
detection, uninstall logic, templates, overrides, architecture, language, or package
revision. Test on a disposable OPSI-managed Windows VM that represents the production image.

Current enabled recipes target machine-wide Windows x64. ARM64 and x86 clients are outside
the supported recipe scope. Firefox and Thunderbird recipes select en-US installers. A
different language requires an explicit recipe and its own acceptance run.

Repository validation is a prerequisite, not a substitute. A valid archive, checksum,
signature result, depot import, or successful OPSI metadata scan cannot prove client
behavior.

## Before the test

Record these fields in the test ticket or change record:

| Field | Value |
|---|---|
| Date and tester | |
| Recipe commit | |
| OPSI product ID | |
| Upstream version | |
| Package revision | |
| `.opsi` filename | |
| Package SHA256 from provenance | |
| Source URL and installer SHA256 from provenance | |
| Windows edition, version, build, and x64 status | |
| OPSI client/opsi-script version | |
| Test VM snapshot name | |
| Requested installer language | |
| Detection method and expected evidence | |
| Uninstall method | |

Confirm these prerequisites with binary results:

- The product dry run exited 0 and selected the intended stable x64 installer and URL.
- The real product build exited 0.
- `scripts/audit-repository.py` exited 0 after the build.
- The generated archive was extracted and its control file, arguments, detection,
  uninstall, overrides, and installer type matched the reviewed recipe.
- The test depot lists the exact upstream version and package revision.
- `autoSetup` is false. No production group or client is assigned.
- The VM snapshot can be restored and no conflicting edition or per-user copy is installed.

Stop if any prerequisite fails. Do not compensate for a server-side failure on the client.

## Evidence to capture

For each action, retain:

- the OPSI action request and final action result;
- the relevant opsi-script log, including vendor exit code and reboot message;
- start and finish timestamps;
- screenshots or command output proving the installed version and machine scope;
- the exact registry key, file version, MSI product code, or custom-detection output;
- running processes or services before and after when the application installs them;
- reboot performed, if any, and the post-reboot detection result;
- unexpected dialogs, user-profile changes, network requests, or self-update behavior;
- a pass or fail entry for every criterion below.

Redact secrets and personal data. Do not edit logs in a way that removes failure context.

## Acceptance matrix

### 1. First install on a clean VM

1. Restore the clean snapshot and verify the recipe's detection evidence is absent.
2. Request `setup` for the exact product version and package revision.
3. Observe the session. No interactive prompt, EULA, first-run blocker, or unexpected reboot
   may interrupt unattended installation.
4. Record the vendor exit code. Codes `0`, `3010`, and `1641` are accepted by the package;
   any other code is a failure.
5. Verify the application is installed machine-wide in the expected location and launches
   for a standard user where launching is safe.
6. Verify the configured detection returns the requested version or a newer numeric version.

Pass only if the OPSI action is successful, no unapproved interaction occurs, the expected
machine-wide x64 application is usable, and detection reports the correct version.

The generated helper performs its built-in post-install detection only for exit code `0`.
For `3010` or `1641`, complete the approved reboot and verify detection afterward; the
accepted action result alone is not evidence that installation completed correctly.

### 2. Repeat install and detection

1. Request `setup` again without changing the VM.
2. Confirm the log reports an already installed version and does not launch the vendor
   installer.
3. Compare key files, services, and application settings before and after.

Pass only if the second action exits successfully, detection skips installation, and no
installation side effects occur. A second successful vendor install is a failure because it
means detection did not control the action.

### 3. Upgrade

1. Restore a snapshot with the previous approved package installed. If this is the first
   introduction and no previous package exists, mark upgrade `NOT APPLICABLE - FIRST
   INTRODUCTION`, record that evidence, and skip the remaining upgrade steps. Do not invent
   or substitute an unapproved older build.
2. Record its detected version, settings needed for a basic smoke test, and service state.
3. Request `setup` for the candidate version and revision.
4. Confirm the intended path was used: in-place upgrade by default, or remove-first only
   when `installer.uninstall_previous: true` is part of the reviewed recipe.
5. Verify the new detected version, application launch, services, and agreed user settings.
6. Run `setup` once more and confirm it now skips.

Pass only if the old version becomes the candidate version, the action succeeds without an
unapproved prompt or reboot, agreed settings survive, and repeat detection skips.

For a package-revision-only change, the upstream application version may remain unchanged.
The pass condition is that the changed deployment behavior is observed and the exact new
package revision is installed on the depot and requested from OPSI.

### 4. Uninstall

1. Start from the successfully installed candidate.
2. Request the OPSI uninstall action.
3. Record the vendor exit code and any reboot request.
4. Verify configured detection no longer finds the product.
5. Verify the main executable, expected machine-wide registration, services, and shortcuts
   are absent, subject to documented vendor data-retention behavior.
6. Run uninstall a second time if the operational policy expects idempotence. Record the
   result rather than assuming it is supported.

Pass only if the first uninstall action succeeds, detection is absent, and no runnable
machine-wide application remains. User documents or explicitly approved settings may remain
only when recorded as a product-specific limit.

### 5. Reboot codes and restart behavior

Test any installer known to return `3010` or `1641`, or any recipe whose vendor may restart
the machine:

1. Confirm the OPSI log preserves the exit code and reports a reboot request.
2. Verify the package does not turn that code into a fatal error.
3. Apply the site's normal OPSI reboot policy.
4. After reboot, verify the client is healthy, detection reports the target version, and the
   application passes its smoke test.
5. Repeat for uninstall when it requests a reboot.

Pass only if reboot handling follows site policy and post-reboot state is correct. An
installer-initiated reboot that bypasses policy is a failure unless an explicit, approved
product exception documents it.

## Detection-specific checks

Run the section matching the recipe. Record the exact evidence, not only a screenshot of the
application UI.

### Registry

- Locate all matches in both HKLM uninstall views.
- Prove `display_name_regex` matches the intended product and no unrelated installed product.
- Record `DisplayName`, `DisplayVersion`, `QuietUninstallString`, `UninstallString`,
  `WindowsInstaller`, registry view, and key name.
- If `version_from_display_name_regex` is used, prove capture group 1 is the intended numeric
  version.
- If `version_replacements` is used, record the source and normalized values.

Pass only if exactly the intended product drives detection and its version compares correctly
before install, after install, after upgrade, and after uninstall.

### File version

- Expand environment variables in `detection.path` as the system account would.
- Record the full path, file SHA256, `ProductVersion`, and architecture.
- Confirm the file is removed or no longer reports the product after uninstall.

Pass only if the file belongs to the product, reports a comparable version, and follows the
full lifecycle.

### MSI

- Record the configured brace-wrapped product code and the matching HKLM uninstall key.
- Confirm the code identifies the intended x64 machine product.
- Verify `msiexec /x` removes that product and detection becomes absent.

Pass only if the GUID is exact, unique for the tested version as expected by the vendor, and
supports the documented upgrade and uninstall path. If the vendor changes product codes per
version, the recipe or detection design must account for that before approval.

### Custom

- Review the rendered OPSI snippet from the extracted archive.
- Exercise its not-installed, installed-current, installed-older, failed-install, and
  post-uninstall branches.
- Prove it invokes `Winbatch_install` only when required and turns failures into failed OPSI
  actions.

Pass only if every branch has observed evidence and no branch reports success without the
intended client state.

## Installer-specific limits

### ZIP

ZIP install copies the validated payload over `installer.target_dir`. It does not remove
files that disappeared from a newer vendor ZIP. Test an upgrade containing a removed or
renamed file. Add a product override if stale files affect operation or security.

Verify target-directory safety, payload layout, executable version detection, shortcuts or
services if needed, and complete directory removal. Pass only if no stale executable changes
behavior and uninstall removes the dedicated target safely.

### MSIX

The generic path provisions with `Add-AppxProvisionedPackage` and deprovisions matching
packages with `Remove-AppxProvisionedPackage -AllUsers`. It does not automatically solve
dependencies, licenses, existing per-user registrations, or app-specific detection.

Test a new user profile, an existing standard-user profile, required dependencies and
licenses, launch, update, deprovisioning, and residual registrations. Pass only if all
profiles reach the intended state and product-specific detection proves it. Otherwise keep
the recipe disabled or add reviewed overrides.

### Product-specific behavior

Record and test vendor services, drivers, browser processes, shell extensions, PATH changes,
file associations, auto-updaters, user data, and licensing where applicable. Test with the
application closed and, if operationally relevant, while it is running.

Language must match the recipe. Architecture must be x64. A vendor bootstrapper that changes
installer technology, scope, registry naming, or version format requires a recipe review,
not a waiver based on a successful exit code.

## Result and approval

Use one of these final states:

- `PASS`: every applicable criterion passed with evidence on the representative Windows
  image.
- `PASS WITH APPROVED LIMIT`: all safety and lifecycle criteria passed, and each remaining
  product-specific limit has an owner, rationale, and operational control.
- `FAIL`: any binary criterion failed, evidence is missing, or behavior differs from the
  reviewed recipe.

Approval requires first install, repeat detection, uninstall, architecture, language,
applicable detection checks, and reboot handling. Upgrade must pass when a previous approved
package exists; a first introduction must carry the explicit not-applicable record described
above. ZIP, MSIX, and custom logic also require their special sections. A failed package
remains disabled or in build-enabled, acceptance-pending state and is withheld from broad
deployment until the recipe is corrected, rebuilt at an appropriate revision, re-audited,
and retested from a clean snapshot.

## Rollback

Before testing, retain the previous `.opsi` archive, sidecars, provenance, catalog revision,
and VM snapshot. If acceptance fails:

1. Stop assignment of the candidate and keep `autoSetup = false`.
2. Save logs and client evidence before changing the VM.
3. Restore the clean or previous-version snapshot for further diagnosis.
4. Keep the failed archive out of broad deployment. Do not replace its bytes under the same
   filename.
5. Restore or re-import the last approved package when service must be recovered.
6. Correct the recipe. Increase `package_revision` for packaging-only changes, or consume a
   real new upstream version when the vendor changed the software.
7. Repeat server-side verification and the complete acceptance matrix.

See [Package authoring](PACKAGE_AUTHORING.md) for revision and rebuild rules,
[Integration](INTEGRATION.md) for depot imports, and [Validation record](VALIDATION.md) for
the current repository-side evidence and outstanding Windows acceptance status.
