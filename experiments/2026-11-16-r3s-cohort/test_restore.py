"""No optimizer: evaluator restore places missing files, verifies hashes, and never overwrites a different file."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import restore_evaluators as r


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();d=Path(self.tmp.name);self.lib=d/'lib'/'uav-test.so';data=b'binary'
        self.archive=d/'a.tar.gz'
        with tarfile.open(self.archive,'w:gz') as t:
            info=tarfile.TarInfo('uav-test.so');info.size=len(data);t.addfile(info,io.BytesIO(data))
        self.protocol=d/'protocol.json'
        self.protocol.write_text(json.dumps(dict(dependencies=dict(evaluator_hashes={str(self.lib):hashlib.sha256(data).hexdigest()}))))

    def tearDown(self):self.tmp.cleanup()

    def test_missing_file_is_restored_and_then_left_alone(self):
        self.assertEqual(r.restore(self.protocol,self.archive),[str(self.lib)]);self.assertEqual(self.lib.read_bytes(),b'binary')
        self.assertEqual(r.restore(self.protocol,self.archive),[])

    def test_different_file_is_not_overwritten(self):
        self.lib.parent.mkdir(parents=True);self.lib.write_bytes(b'other')
        with self.assertRaises(SystemExit):r.restore(self.protocol,self.archive)
        self.assertEqual(self.lib.read_bytes(),b'other')

    def test_real_archive_matches_the_protocol(self):
        here=Path(r.__file__).resolve().parent;want=json.loads((here/'protocol.json').read_text())['dependencies']['evaluator_hashes']
        with tarfile.open(here/'runtime-evaluators.tar.gz') as t:
            for path,digest in want.items():self.assertEqual(hashlib.sha256(t.extractfile(Path(path).name).read()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
