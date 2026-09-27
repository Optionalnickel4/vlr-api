"""Receipt verification must reject a reused PID/start and changed bytes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import asyncio
from contextlib import asynccontextmanager
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('receipt', Path(__file__).parents[1] / 'scripts/baseline/receipt.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class ReceiptTests(unittest.TestCase):
    def test_changed_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'app.py').write_text('old')
            (root / 'release.json').write_text(json.dumps({'files': {'app.py': m.sha(root / 'app.py')}}))
            (root / 'app.py').write_text('new')
            with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                m.check_manifest(root)

    def test_wrong_invocation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'release.json').write_text('{}')
            r = {'release_root': tmp, 'release_manifest_sha256': m.sha(root / 'release.json'),
                 'frontend_build_id': 'known', 'pid': 100, 'invocation_id': 'old'}
            path = root / 'receipt.json'
            path.write_text(json.dumps(r))
            with patch.object(m, 'check_manifest', return_value={'frontend_build_id': 'known'}), patch.object(m, 'service_identity', return_value={'MainPID': '100', 'InvocationID': 'new'}):
                with self.assertRaises(AssertionError):
                    m.verify(path, 'test')

    def test_start_ticks_handles_parentheses_in_process_name(self):
        stat = '100 (a name) tricky) S ' + ' '.join(str(i) for i in range(4, 53))
        with patch.object(Path, 'read_text', return_value=stat):
            self.assertEqual(m.start_ticks(100), '22')

    def test_launcher_writes_invocation_receipt_after_lifespan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'backend/source').mkdir(parents=True)
            (root / 'release.json').write_text('{}')
            events = []
            @asynccontextmanager
            async def original(application):
                events.append('startup')
                yield
                events.append('shutdown')
            app_object = SimpleNamespace(router=SimpleNamespace(lifespan_context=original))
            package = ModuleType('app')
            main = ModuleType('app.main')
            main.app = app_object
            main._scheduler = None
            package.main = main
            server = ModuleType('uvicorn')
            def run(application, **kwargs):
                async def exercise():
                    async with application.router.lifespan_context(application):
                        self.assertEqual(events, ['startup'])
                        receipt = json.loads((root / 'receipts/test-invocation.json').read_text())
                        self.assertEqual(receipt['invocation_id'], 'test-invocation')
                        self.assertEqual(receipt['frontend_build_id'], 'test-build')
                        self.assertTrue(receipt['proc_start_ticks'])
                asyncio.run(exercise())
            server.run = run
            manifest = {'artifact_archives': {}, 'frontend_build_id': 'test-build', 'dependency_inventory_sha256': 'digest'}
            with patch.dict(m.sys.modules, {'app': package, 'app.main': main, 'uvicorn': server}), patch.dict(m.os.environ, {'INVOCATION_ID': 'test-invocation'}), patch.object(m, 'check_manifest', return_value=manifest), patch.object(m.sys, 'path', list(m.sys.path)):
                m.launch(root, root / 'receipts')
            self.assertEqual(events, ['startup', 'shutdown'])
