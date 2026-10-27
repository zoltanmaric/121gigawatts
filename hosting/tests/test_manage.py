import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('manage', Path(__file__).parents[1] / 'manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class ManageTests(unittest.TestCase):
    def test_private_files_cannot_be_put_in_repository(self):
        with self.assertRaises(ValueError):
            manage.private_directory(manage.REPO / 'even-if-ignored')

    def test_check_is_read_only_and_holds_ghost_when_requested(self):
        host = manage.Hosting(Path('/outside repo/private'))
        with patch.object(host, 'collections'), patch.object(host, 'run') as run:
            host.configure(check=True, hold=True)
        self.assertIn('--check', run.call_args.args)
        self.assertIn('ghost_start=false', run.call_args.args)
        self.assertIn(Path('/outside repo/private/inventory.yml'), run.call_args.args)

    def test_apply_requires_existing_reviewed_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            host = manage.Hosting(Path(folder))
            with patch.object(host, 'tf') as tf, self.assertRaises(ValueError):
                host.applying()
            tf.assert_not_called()

    def test_adopt_refuses_conflicting_state_before_import(self):
        with tempfile.TemporaryDirectory() as folder:
            host = manage.Hosting(Path(folder))
            host.env['HCLOUD_TOKEN'] = 'test-only'
            host.state.touch()
            payload = {'server': {'id': 123, 'server_type': {'name': 'cx23'},
                                  'public_net': {'ipv4': {'id': 4}, 'ipv6': {'id': 6}}}}
            state = {'values': {'root_module': {'resources': [
                {'mode': 'managed', 'address': 'hcloud_server.site', 'values': {'id': '999'}}]}}}
            with patch.object(manage, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())), \
                 patch.object(host, 'init'), \
                 patch.object(host, 'tf', return_value=Mock(stdout=json.dumps(state))) as tf:
                with self.assertRaises(ValueError):
                    host.adopt(123)
            self.assertEqual([call.args[0] for call in tf.call_args_list], ['show'])
