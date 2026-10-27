#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["ansible-core==2.20.0"]
# ///
"""Set up tooling and run explicit hosting operations; never deploy implicitly."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import Request, urlopen

HOSTING = Path(__file__).resolve().parent
REPO = HOSTING.parent


def private_directory(value):
    path = Path(value).expanduser().resolve()
    if path == REPO or REPO in path.parents:
        raise ValueError('DEPLOY_PRIVATE must be outside the repository')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


class Hosting:
    def __init__(self, private):
        self.private = private
        self.state = private / 'terraform.tfstate'
        self.plan = private / 'review.tfplan'
        self.env = {**os.environ,
                    'TF_DATA_DIR': str(private / 'terraform-data'),
                    'ANSIBLE_LOCAL_TEMP': str(private / 'ansible-tmp'),
                    'ANSIBLE_COLLECTIONS_PATH': str(private / 'collections')}

    def run(self, *args, capture=False):
        return subprocess.run([str(a) for a in args], env=self.env, cwd=REPO,
                              check=True, text=True, capture_output=capture)

    def tf(self, *args, **kwargs):
        return self.run('terraform', '-chdir=' + str(HOSTING / 'terraform'), *args, **kwargs)

    def init(self):
        self.tf('init', '-input=false', '-lockfile=readonly')

    def collections(self):
        self.run('ansible-galaxy', 'collection', 'install', '-r',
                 HOSTING / 'ansible/requirements.yml', '-p', self.private / 'collections')

    def variables(self):
        for name in ('site.tfvars.json', 'site.tfvars'):
            if (self.private / name).is_file():
                return '-var-file=' + str(self.private / name)
        raise ValueError('Missing private site.tfvars or site.tfvars.json')

    def setup(self):
        for source, name in [('terraform/site.tfvars.example', 'site.tfvars'),
                             ('ansible/inventory.example.yml', 'inventory.yml'),
                             ('ansible/site.example.yml', 'site.yml')]:
            target = self.private / name
            if not target.exists():
                shutil.copyfile(HOSTING / source, target)
                target.chmod(0o600)
        self.init()
        self.collections()
        print('Tooling ready. Fill in the private example files before adopting or configuring a server.')

    def adopt(self, server_id):
        token = self.env.get('HCLOUD_TOKEN')
        if not token:
            raise ValueError('Set HCLOUD_TOKEN in the environment')
        request = Request(f'https://api.hetzner.cloud/v1/servers/{server_id}',
                          headers={'Authorization': 'Bearer ' + token})
        with urlopen(request, timeout=30) as response:
            server = json.load(response)['server']
        if server['server_type']['name'] != 'cx23':
            raise ValueError('Adoption expects the permanent CX23, not another server')
        targets = {f'hcloud_primary_ip.site["{family}"]': str(server['public_net'][family]['id'])
                   for family in ('ipv4', 'ipv6')}
        targets['hcloud_server.site'] = str(server['id'])
        self.init()
        existing = {}
        if self.state.exists():
            data = json.loads(self.tf('show', '-json', self.state, capture=True).stdout)
            existing = {r['address']: str(r['values']['id']) for r in
                        data.get('values', {}).get('root_module', {}).get('resources', [])
                        if r.get('mode') == 'managed'}
        # Check the complete mapping before any import, including resumed imports.
        if any(address not in targets or targets[address] != value for address, value in existing.items()):
            raise ValueError('Private state already tracks different resources; refusing adoption')
        for address, value in targets.items():
            if address not in existing:
                self.tf('import', '-input=false', '-state=' + str(self.state),
                        self.variables(), address, value)

    def planning(self):
        self.init()
        self.tf('plan', '-input=false', '-state=' + str(self.state),
                self.variables(), '-out=' + str(self.plan))

    def applying(self):
        if not self.plan.is_file():
            raise ValueError('Run plan and review it before apply')
        self.init()
        self.tf('apply', '-input=false', '-state=' + str(self.state), self.plan)
        self.plan.unlink()

    def configure(self, check=False, hold=False):
        self.collections()
        args = ['ansible-playbook', '-i', self.private / 'inventory.yml',
                HOSTING / 'ansible/site.yml', '-e', '@' + str(self.private / 'site.yml')]
        if check:
            args += ['--check']
        if hold:
            args += ['-e', 'ghost_start=false']
        self.run(*args)

    def validate(self):
        self.tf('fmt', '-check')
        self.init()
        self.tf('validate')
        self.collections()
        self.run('ansible-playbook', '-i', HOSTING / 'ansible/inventory.example.yml',
                 HOSTING / 'ansible/site.yml', '--syntax-check')
        self.run(sys.executable, '-m', 'unittest', 'discover', '-s', HOSTING / 'tests')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', default=os.environ.get('DEPLOY_PRIVATE'))
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('setup', 'plan', 'apply', 'validate'):
        commands.add_parser(name)
    commands.add_parser('adopt').add_argument('--server-id', type=int, required=True)
    for name in ('check', 'configure'):
        commands.add_parser(name).add_argument('--hold', action='store_true', help='Leave Ghost stopped for a later restore')
    args = parser.parse_args()
    if not args.private_dir:
        parser.error('Set DEPLOY_PRIVATE or pass --private-dir')
    os.umask(0o077)
    hosting = Hosting(private_directory(args.private_dir))
    if args.command == 'adopt':
        hosting.adopt(args.server_id)
    elif args.command in ('check', 'configure'):
        hosting.configure(check=args.command == 'check', hold=args.hold)
    else:
        getattr(hosting, {'plan': 'planning', 'apply': 'applying'}.get(args.command, args.command))()


if __name__ == '__main__':
    main()
