# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub's
[private vulnerability reporting](https://github.com/KebanFiru/signalpost/security/advisories/new)
rather than opening a public issue.

Expect an initial response within 7 days.

## Security model

signalpost generates configuration and, in binary install mode, a shell script that
runs as root. A few properties are worth stating explicitly:

**Downloads are checksum-verified.** `install.sh` pins a SHA-256 for every
component tarball it downloads (see `RELEASE_CHECKSUMS` in
`signalpost/constants.py`). A mismatch aborts the install before anything is
extracted. Checksums are regenerated with `scripts/update_versions.py`, which
fetches them from each project's official release artifacts.

**signalpost never starts anything on its own.** `signalpost deploy` writes files and
stops. Bringing the stack up is always an explicit, separate command you run
yourself, so you can read `install.sh` and the generated systemd units first.

**The Grafana admin password** is generated locally with `secrets.choice`, is
24 characters, and is passed to Grafana via a file reference — never as a
literal in the compose file or a systemd unit. It's written to
`secrets/grafana_admin_password.txt` with mode `644` (world-readable) rather
than `600`: in docker mode the file is bind-mounted into containers running
as an unprivileged, fixed-UID user that essentially never matches the host
user who ran `signalpost deploy`, and Compose's `secrets: file:` bind mount
does not remap ownership the way Swarm secrets do. Binary mode re-tightens
this to `600` after `chown`ing the file to the systemd service user.

**The stack binds to all interfaces.** Grafana (`:3000`), Prometheus
(`:9090`), Loki (`:3100`), Tempo (`:3200`) and the OTLP receivers
(`:4317`/`:4318`) are published on the host. On a machine with a public IP,
put them behind a firewall or a reverse proxy with TLS. signalpost does not do
this for you yet — see the "Reverse proxy + TLS" item on the roadmap.

**Alert webhook URLs are secrets.** If you pass `--notify` with a Slack or
Discord webhook, that URL is never inlined into
`observability/configs/alertmanager.yml` — it's written to its own file
(`secrets/alertmanager_webhook_url.txt`) that Alertmanager reads via
`api_url_file`/`webhook_url_file`, the same file-reference pattern used for
the Grafana admin password (mode `644` for the same bind-mount-ownership
reason, `600` in binary mode). `observability/` should not be committed to a
public repository regardless.
