# Ghost hosting

[Repository overview and theme workflow](../README.md)

Terraform describes the replacement Hetzner server and its two primary IPs.
Set `server_type` to the purchased plan (`cpx02` by default, or `cx23`). Ansible
configures Ubuntu 24.04, Node 22, MySQL 8, Ghost 6.72.0, Nginx, UFW, and a 2 GiB
swap file. Ghost runs as an unprivileged account and listens only on loopback.
The custom theme, posts, and uploads must be supplied separately; server setup
does not restore an existing site.

Use this runbook in order: prepare private inputs, adopt or provision the server,
configure it, and inspect the running Ghost installation.
All commands below run from the repository root. Deployment is manual.

| Files | Purpose |
| --- | --- |
| [terraform/](terraform/) | Replacement server and primary IPs; existing SSH key lookup |
| [ansible/site.yml](ansible/site.yml) | Server packages, Ghost, MySQL, Nginx, TLS, and UFW |

## Boundaries

- Terraform manages **only the replacement server**. The legacy server is not in
  its state. The `backups` setting defaults to true; preserve the observed value
  when importing and review the extra charge before enabling it. The shared SSH
  public key is looked up, not owned or deleted by Terraform.
- UFW is the firewall on the server; no Hetzner cloud firewall is currently
  attached. Only SSH, HTTP, and HTTPS are allowed inbound, including IPv6.
- Cloudflare DNS and certificate issuance remain manual. DNS cutovers and the
  original server rebuild each require separate approval. Neither is performed
  by these playbooks. Origin certificates require proxied Cloudflare traffic
  with Full (strict) TLS; browsers do not trust them directly.
- `site.yml` reconciles configuration. It refuses a different installed Ghost
  version. It does not import data or run Ghost major-version migrations.

## Private inputs

Keep a directory **outside this repository**, mode `0700`, with files mode
`0600`. In the examples, `DEPLOY_PRIVATE` points to that directory. Store its
backup securely: losing Terraform state or credentials makes recovery harder.

Keep these private: Hetzner API token, Terraform state/backups/plans, real
inventory and variable files, SSH private keys, SMTP credentials, Ghost config,
origin private key, SQL dumps, exports (which include drafts and user details),
and execution logs. `.gitignore` is a fallback, not a substitute for this
separation. Never use `git add -f` for deployment files or paste plans/configs
into a public PR. CI has no cloud or deployment credentials.

Copy `terraform/site.tfvars.example`, `ansible/inventory.example.yml`, and
`ansible/site.example.yml` into that private directory and replace the example
values. Supply the API token through `HCLOUD_TOKEN` in your environment, not
Terraform variables. Use a project-scoped Hetzner token. Verify the SSH host
fingerprint through the console before recording it in `known_hosts`.

The private Ghost config must use `ghost_prod`, `ghostapp`, MySQL on
`127.0.0.1`, content under the installation's `content/` directory, and a working
SMTP relay. Use a strong generated database password and keep the same value
on subsequent runs. Password rotation is a separate operation: the playbook only
sets a database password when creating the user and verifies existing credentials
before replacing the app config. The preview URL is `http://localhost:2371`.
Real SMTP is supported during preview; a login verification email must reach
the owner.
Do not publish posts or send newsletters while rehearsing.

For a fresh server, supply `origin_certificate_file` and `origin_key_file`.
Alternatively generate the key and CSR on the server, issue the certificate
through Cloudflare, and install both at the configured certificate directory.
Omit those two variables when reconciling a server with existing certificate
files; the playbook leaves them in place. Never retrieve a server-generated
private key merely to run a dry run. Check certificate expiry before cutover
and renew it before it expires; renewal is not automated here.

## Terraform: adopt before applying

Install Terraform 1.5+ and use the committed provider lock file. The original
server must **never** be imported into this replacement stack: replacing it
could lose the legacy plan.

```sh
terraform -chdir=hosting/terraform init
terraform -chdir=hosting/terraform import \
  -state="$DEPLOY_PRIVATE/terraform.tfstate" \
  -var-file="$DEPLOY_PRIVATE/site.tfvars" \
  'hcloud_primary_ip.site["ipv4"]' "$TEMP_IPV4_ID"
terraform -chdir=hosting/terraform import \
  -state="$DEPLOY_PRIVATE/terraform.tfstate" \
  -var-file="$DEPLOY_PRIVATE/site.tfvars" \
  'hcloud_primary_ip.site["ipv6"]' "$TEMP_IPV6_ID"
terraform -chdir=hosting/terraform import \
  -state="$DEPLOY_PRIVATE/terraform.tfstate" \
  -var-file="$DEPLOY_PRIVATE/site.tfvars" \
  hcloud_server.site "$TEMP_SERVER_ID"
terraform -chdir=hosting/terraform plan \
  -state="$DEPLOY_PRIVATE/terraform.tfstate" \
  -var-file="$DEPLOY_PRIVATE/site.tfvars" \
  -out="$DEPLOY_PRIVATE/review.tfplan"
```

Import runs once for existing resources; omit import only when intentionally
creating a new paid server. Review the plan before manually applying the saved
plan. Import can leave provider defaults and the existing `public_net` block
unrecorded, producing an in-place adoption diff; verify that its IP IDs match
the current server. Stop if a plan proposes a replacement or an unexpected
resource. `prevent_destroy` guards the server and both IPs. Terraform cannot
reconcile creation-time SSH keys after import; manage subsequent key changes
explicitly on the server.

## Configure Ghost

Install the pinned Ansible dependencies in a Python 3.12+ virtual environment:

```sh
python3 -m venv "$DEPLOY_PRIVATE/venv"
"$DEPLOY_PRIVATE/venv/bin/pip" install -r hosting/ansible/requirements.txt
"$DEPLOY_PRIVATE/venv/bin/ansible-galaxy" collection install -r hosting/ansible/requirements.yml
"$DEPLOY_PRIVATE/venv/bin/ansible-playbook" \
  -i "$DEPLOY_PRIVATE/inventory.yml" hosting/ansible/site.yml \
  -e "@$DEPLOY_PRIVATE/site.yml" --check
```

A dry run predicts changes; it cannot prove a fresh installation works. For a
new empty site, review and run `site.yml` without `--check` to start Ghost.
When preparing a server for a later restore, add `-e ghost_start=false` to leave
Ghost stopped and the database empty. On an existing server, reconciliation
may restart services; choose a suitable time.

Node 22 patch updates follow the package repository; Ghost and Ghost CLI versions
are pinned. OS release upgrades and unrelated package upgrades are separate
maintenance operations.

## Preview and readiness

```sh
ssh -N -L 127.0.0.1:2371:127.0.0.1:2368 root@"$TEMP_IPV4"
```

Open `http://localhost:2371/` and `/ghost/`. A fresh installation has no existing
posts or owner account until they are created or restored. Server setup is not
permission to switch production traffic: validate content, owner access, SMTP,
and production TLS before any separately approved DNS change.

## Validation

[Hosting CI](../.github/workflows/hosting.yml) validates Terraform configuration
and Ansible syntax without deployment credentials. These checks do not apply
infrastructure or connect to a server. Use `--check` to review configuration
changes before applying them; a dry run does not replace a fresh-server test.
