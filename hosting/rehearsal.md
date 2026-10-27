# Fresh-server rehearsal — 2026-10-27

The Ansible installation and restore were exercised on a fresh Hetzner CX23
running Ubuntu 24.04.4. The server had already been purchased separately; this
run did not test Terraform resource creation. Terraform imported the existing
server and IPs into separate private state and produced a read-only adoption
plan, with no creation or deletion proposed. No Terraform apply was performed.

## Results

| Check | Result |
| --- | --- |
| Fresh setup, Ghost held stopped | Passed; database left empty for restore |
| Restore of prepared Ghost 6 SQL and matching content | Passed |
| Ghost version and active migrated theme | 6.72.0; custom theme active |
| Original owner credentials and restored records | Verified privately |
| Content archive integrity | Every restored file matched its saved SHA-256 hash |
| Public page and asset check | 16 pages, 122 same-origin assets; no failures |
| Authenticated Admin API | Site, posts, and pages returned 200 |
| HTTPS proxy | 200; certificate verification passed with explicit test trust |
| SMTP | TLS and authentication passed; no email sent during this run |
| Second configuration dry run | Zero changes |
| Second actual configuration run | Zero changes |
| Reboot | Ghost, MySQL, and Nginx returned active and enabled; HTTP 200 |
| Swap and firewall after reboot | 2 GiB swap active; UFW retained SSH/HTTP/HTTPS rules |
| Attempted repeat restore | Refused the nonempty database before stopping Ghost; service stayed active |

The restore preflight was strengthened to check for an empty database **before**
stopping the service. The import helper repeats that check immediately before
importing. Regression tests cover this refusal and unsafe archive paths/links.

## Limits and deployment state

- The rehearsal uses a two-day self-signed certificate for `rehearsal.invalid`,
  not a production certificate. Issue and install the real origin certificate
  before any Cloudflare cutover. Do not bypass browser certificate warnings.
- The Ghost URL remains `http://localhost:2371`; DNS and the live site were not
  changed. The preview is accessible through an SSH tunnel.
- The previous CPX02 and both primary IPs were deleted on explicit request. The
  CX23 remains available. The old CPX02 state was retired privately.
- The CX23 was purchased without daily Hetzner backups. Its private variables
  preserve that observed setting; enabling paid backups is a separate decision.
- The restore used the already saved, validated Ghost 6 snapshot, with the real
  owner restored and test API keys rotated during private snapshot preparation.
  It was not a fresh live-site export. Reconcile new live-site writes before
  a production cutover.
- External embeds and a real owner's interactive login are separate browser
  checks. Admin API verification does not exercise the staff login email flow.

Private configuration, inventory, certificates, state, logs, and evidence stay
outside the repository. Only this summary is published.
