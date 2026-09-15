# Connect the existing OPSI 4.3 server

[Back to the documentation index](README.md)

This guide contains reusable integration instructions. The dated
[deployment record](#deployment-record-2026-09-07) at the end describes what was actually
applied on the validated host and supersedes earlier same-day intermediate states.

The repository builder never connects to or modifies your existing deployment. Run the
following integration commands yourself when ready to import packages. Replace
`/path/to/opsi-compose` with the directory containing the existing OPSI server's Compose
file. Replace **HOST-IP** with the repository host's LAN address reachable from **inside**
the OPSI container; `127.0.0.1` would point at that container, not this repository. Replace
**PORT** with the configured `HTTP_PORT`.

```bash
cd /path/to/opsi-compose

docker compose exec -u root opsi-server sh -c 'cat > /etc/opsi/package-updater.repos.d/local-auto.repo <<EOF
[repository_local_auto]
description = Automatic private OPSI software repository
active = true
baseURL = http://HOST-IP:PORT
dirs = /
autoInstall = true
autoUpdate = true
autoSetup = false
onlyDownload = false
verifyCert = false
EOF'
```

`verifyCert = false` reproduces the requested configuration for plain HTTP (there is no HTTP TLS certificate). If serving over HTTPS through a reverse proxy, change baseURL and enable `verifyCert = true` with a trusted CA.

Validate the connection and list available products:

```bash
docker compose exec opsi-server \
  opsi-package-updater list --active-repos

docker compose exec opsi-server \
  opsi-package-updater --repo local_auto list --products
```

Initial import (this explicitly imports all available products; select product IDs if you only want a subset):

```bash
docker compose exec opsi-server \
  opsi-package-updater -v --repo local_auto install
```

Future updates:

```bash
docker compose exec opsi-server \
  opsi-package-updater -v --repo local_auto update
```

Repository builds and depot imports are separate operations. The builder checks upstream every six hours. It does not ask OPSI to import anything, and it does not schedule software deployment to clients. Keep `autoSetup = false`: setting it to `true` can schedule updated applications on clients and must remain an explicit administrator choice. Vendor self-updaters may also independently update installed applications; these recipes do not globally disable them.

Install the optional depot-import timer only after validating the repository. The tracked
service file contains the validated host's
`WorkingDirectory=/opt/opsi/opsi-docker/opsi-server`; if the existing OPSI Compose project
is elsewhere, copy the service and change `WorkingDirectory` before enabling it:

```bash
cd /path/to/opsi-auto-repo
sudo install -m 0644 systemd/opsi-local-auto-update.service /etc/systemd/system/
sudo install -m 0644 systemd/opsi-local-auto-update.timer /etc/systemd/system/
sudoedit /etc/systemd/system/opsi-local-auto-update.service
sudo systemctl daemon-reload
sudo systemctl enable --now opsi-local-auto-update.timer
systemctl list-timers opsi-local-auto-update.timer
```

The timer runs at 00:30, 06:30, 12:30 and 18:30 with up to 15 minutes random delay. Long builds can be picked up on the next import. Logs and manual trigger:

```bash
sudo systemctl start opsi-local-auto-update.service
journalctl -u opsi-local-auto-update.service
```

The service uses `docker compose exec -T` because systemd has no terminal. Installing and
enabling it is a separate administrator action; the repository stack does not do so during
normal setup. Keep the `.repo` file in your existing server's normal configuration
backup/persistent storage; this project does not change that deployment's volumes.

## Deployment record: 2026-09-07

At the administrator's request, repository `local_auto` was configured with
`http://192.168.178.6:37563`. All 17 current products were imported into depot
`opsi.home.arpa` and verified through the OPSI backend. The repository configuration is
persisted under the server's `/data/etc/package-updater.repos.d/`.

Later that day, automatic downloads and depot imports were enabled for `local_auto`, and
the systemd timer was installed and enabled. It runs every six hours using `install`, which
includes newly added catalog products as well as newer versions. `autoSetup = false` keeps
client deployment manual. The obsolete `geosone` repository is inactive with
autoInstall/autoUpdate disabled; its existing products were not deleted. Previous
repository configurations are backed up inside the OPSI container under
`/data/etc/local-auto-repo-backups/2026-09-07/`.
