## Summary

Describe the problem and the focused change that solves it.

## Validation

List each command or manual check you ran and its result. Note any check that wasn't run and
why.

## Security and Redistribution

Describe any impact on source trust, allowed hosts or URL prefixes, redirects, checksums,
installer contents, privileges, secrets, deployment behavior, or redistribution terms. Write
`None` if the change has no such impact.

## Windows Acceptance

For client-facing package changes, report the applicable install, repeat detection, upgrade,
uninstall, and reboot checks from `docs/CLIENT_ACCEPTANCE.md`. State `Not run` or `Not
applicable` with a reason when appropriate. Don't claim acceptance based only on unit tests,
a dry run, or a valid OPSI archive.

## Checklist

- [ ] The pull request is focused and contains no unrelated changes.
- [ ] Tests or checks covering the change are listed above.
- [ ] No secrets, credentials, private data, installers, generated packages, or vulnerability
      details are included.
- [ ] Package source, checksum, revision, detection, uninstall, and redistribution effects
      have been reviewed where applicable.
