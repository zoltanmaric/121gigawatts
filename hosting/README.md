# Ghost hosting

[Repository overview and theme workflow](../README.md)

This configuration runs Ghost on a permanent Hetzner CX23 with Ubuntu 24.04, Node 22, MySQL 8,
Ghost 6.72.0, and Nginx. Ghost runs as an unprivileged account on loopback; Nginx
serves HTTPS. UFW allows SSH, HTTP, and HTTPS. A 2 GiB swap file provides spare
capacity. MySQL uses Ubuntu's defaults rather than custom low-memory limits.

Terraform owns the server and its primary IPs, with deletion guards. It looks up
an existing SSH public key without owning it. Daily paid backups are controlled
by `backups`; preserve the observed setting when adopting an existing server.
Cloudflare DNS, origin certificate issuance/renewal, and production cutover are
manual. Git pushes and CI never deploy.

## Private inputs

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Terraform
1.5+. Run commands from the repository root. Choose an absolute directory outside
Git for private inputs and state:

```sh
export DEPLOY_PRIVATE=/absolute/private/ghost
uv run --locked hosting/manage.py setup
```

`uv` supplies the locked Python/Ansible environment. `setup` installs pinned
Ansible collections, initializes Terraform, and copies missing input templates.
It does not overwrite existing files or change cloud resources. Fill in:

| Private file | Purpose |
| --- | --- |
| `site.tfvars` (or `site.tfvars.json`) | Server name, plan, location, IP names, SSH key name, backup setting and labels |
| `inventory.yml` | SSH host, account, key path and strict host-key checking |
| `site.yml` | Domain, preview URL and paths to private configuration/certificates |
| `config.production.json` | Ghost settings, database password and SMTP credentials; supply separately |

Supply a project-scoped `HCLOUD_TOKEN` through the environment. Verify the SSH
host fingerprint before recording it in `known_hosts`. Keep the directory mode
`0700` and private files `0600`. The wrapper keeps Terraform state, saved plans,
provider data, and Ansible working files inside that directory. Do not copy them
into Git or public review comments. `.gitignore` is only a fallback.

The Ghost configuration must use `ghost_prod`, `ghostapp`, MySQL on
`127.0.0.1`, Ghost on `127.0.0.1:2368`, and the installation's `content/` directory.
Use a strong generated database password and keep it stable between runs. The
playbook sets it only when creating the database user and verifies existing
credentials before replacing the app config; password rotation is separate.
The preview URL is `http://localhost:2371`. Supply working SMTP for login emails.

Supply `origin_certificate_file` and `origin_key_file`, or install the certificate
and server-generated key directly in the configured certificate directory and
omit those inputs. Cloudflare Origin CA certificates require proxied traffic
with Full (strict) TLS; browsers do not trust them directly. Renew before expiry.

## Infrastructure

For an existing CX23, adoption discovers its attached IP IDs and imports all
three resources. It refuses state that already tracks different resources and
can resume a partial import. It does not change the server.

```sh
uv run --locked hosting/manage.py adopt --server-id "$SERVER_ID"
uv run --locked hosting/manage.py plan
```

Review the saved plan before explicitly applying it:

```sh
uv run --locked hosting/manage.py apply
```

For an intentionally new paid server, omit `adopt`. Inspect every creation,
resize, backup setting, and deletion proposal. Import may produce an in-place
diff recording provider defaults and the existing public-network IDs; verify
the IDs against the server. Creation-time SSH keys cannot be reconciled after
import; manage later key changes explicitly on the server.

Commit `.terraform.lock.hcl` and `manage.py.lock`: they pin public dependencies
and checksums, not infrastructure state or credentials.

## Server configuration

```sh
uv run --locked hosting/manage.py check
uv run --locked hosting/manage.py configure
```

`check` predicts changes without applying them. `configure` may restart services.
For an empty server that will receive a content restore, use `configure --hold`
to install Ghost without starting it or initializing its database. Otherwise it
starts a new empty site. Setup does not restore content or upgrade an existing
Ghost version; mismatched versions are refused.

Node 22 patch updates follow the package repository. Ghost and Ghost CLI are
pinned. OS release upgrades are separate maintenance operations. Reconciliation
removes the obsolete `99-ghost-small.cnf` override if present; this requires a
MySQL restart, so review that change before applying to a running site.

## Preview

```sh
ssh -N -L 127.0.0.1:2371:127.0.0.1:2368 root@"$SERVER_IPV4"
```

Open `http://localhost:2371/` and `/ghost/`. Validate content, owner access, SMTP,
and production TLS before a separately approved DNS cutover. The migration is
one-way to the CX23; any old server is kept only for rollback until retirement
is explicitly approved.

## Validation

```sh
uv run --locked hosting/manage.py validate
```

This is also the [CI entry point](../.github/workflows/hosting.yml). It validates
Terraform and Ansible and runs local tests without deployment credentials or a
server connection. Syntax checks and dry runs do not replace a fresh-server
rehearsal. Review public changes using [the hosting agent guidelines](AGENTS.md).
