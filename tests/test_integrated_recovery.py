"""Safety regressions; never start storage, applications or a namespace."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('gate2', Path(__file__).parents[1] / 'scripts/recovery/integrated.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class RecoverySafetyTests(unittest.TestCase):
    def test_missing_inputs_do_not_start_processes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m.subprocess, 'run') as run:
            data, errors = m.preflight(Path(tmp) / 'absent.json')
            self.assertIsNone(data)
            self.assertTrue(any('Missing reviewed input' in e for e in errors))
            run.assert_not_called()

    def test_known_fallback_rejected_even_with_review_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'input.json'
            p.write_text(json.dumps({'candidate_revision': m.CANDIDATE,
                                    'secret_free_artifacts_reviewed': True,
                                    'provenance': {'reviewed_startup_link': True, 'archive_sha256': m.FALLBACK}}))
            data, errors = m.preflight(p)
            self.assertIsNone(data)
            self.assertTrue(any('NOT attested production' in e for e in errors))

    def test_path_escape_and_absolute_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('../secret', '/etc/passwd'):
                with self.assertRaises(ValueError):
                    m.member(Path(tmp), name)

    def test_undeclared_file_environment_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'BASE', Path(tmp)):
            root = Path(tmp) / 'artifact'
            root.mkdir()
            p = root / 'x'
            p.write_text('code')
            spec = {'root': str(root), 'files': {'x': m.sha(p)}}
            for name in ('.env', 'unlisted'):
                extra = root / name
                extra.write_text('do not copy')
                with self.assertRaises(ValueError):
                    m.validate_tree(spec)
                extra.unlink()
            (root / 'link').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                m.validate_tree(spec)

    def test_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'BASE', Path(tmp)):
            p = Path(tmp) / 'x'
            p.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                m.validate_tree({'root': tmp, 'files': {'x': '0' * 64}})

    def test_sandbox_mounts_exclude_host_storage_and_credentials(self):
        command = m.sandbox_command(Path('/private/test'))
        self.assertIn('--unshare-all', command)
        self.assertIn('--clearenv', command)
        for forbidden in ('/opt', '/home', '/var', '/run', '/', '--share-net'):
            self.assertNotIn(forbidden, command)
        binds = [command[i+1:i+3] for i, x in enumerate(command) if x == '--bind']
        self.assertEqual(binds, [['/private/test/state', '/work']])


if __name__ == '__main__':
    unittest.main()
