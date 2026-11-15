import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import installer as i

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.game=self.root/'中文 Steam library/Isaac';(self.game/'Repentogon').mkdir(parents=True)
        for name in ('zhlLoader.dll','isaac-ng.exe','zhlREPENTOGON.dll'):(self.game/'Repentogon'/name).write_bytes(b'original')
        self.home=self.root/'Local AppData';self.package=self.root/'package'
        for name in ('python/python.exe','python/pythonw.exe','companion.py','external/overlay.py',i.DLL):
            p=self.package/'payload'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'package-v1')
        self.manifest('0.7.42')
    def tearDown(self):self.tmp.cleanup()
    def manifest(self,version):
        data={'app':i.APP,'version':version,'protocol':1,'files':{p.relative_to(self.package/'payload').as_posix():i.digest(p) for p in (self.package/'payload').rglob('*') if p.is_file()}}
        (self.package/'manifest.json').write_text(json.dumps(data));return data
    def runop(self,name):return i.operate(name,self.game,self.package,self.home)
    def state(self):return i.read_json(i.installed_root(self.game,self.home)/'installation.json')
    def test_lifecycle_and_user_files(self):
        result=self.runop('install');first=Path(result['runtime'])
        (first/'user-added.txt').write_text('keep')
        saves=self.game/'data/samira_isaac/save1.dat';saves.parent.mkdir(parents=True);saves.write_text('player progress')
        (self.package/'payload/companion.py').write_bytes(b'new');self.manifest('0.7.43')
        self.runop('update');self.assertNotEqual(self.state()['current'],first.relative_to(i.installed_root(self.game,self.home)).as_posix())
        self.runop('rollback');self.assertTrue(self.state()['current'].startswith('versions/0.7.42-'))
        self.runop('uninstall');self.assertFalse((self.game/'Repentogon'/i.DLL).exists())
        self.assertEqual(saves.read_text(),'player progress');self.assertEqual((first/'user-added.txt').read_text(),'keep')
        self.assertEqual((self.game/'Repentogon/zhlREPENTOGON.dll').read_bytes(),b'original')
        self.runop('uninstall') # idempotent
    def test_repair_corrupt_runtime_and_bridge(self):
        result=self.runop('install');(Path(result['runtime'])/'companion.py').unlink()
        (self.game/'Repentogon'/i.DLL).write_bytes(b'corrupt')
        self.assertIn('companion.py',self.runop('status')['damaged'])
        self.runop('repair');self.assertEqual(self.runop('status')['damaged'],[])
        self.assertEqual((self.game/'Repentogon'/i.DLL).read_bytes(),b'package-v1')
    def test_bad_package_keeps_active(self):
        self.runop('install');state=self.state();ini=(self.game/'Repentogon'/i.INI).read_bytes()
        (self.package/'payload/companion.py').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):self.runop('update')
        self.assertEqual(self.state(),state);self.assertEqual((self.game/'Repentogon'/i.INI).read_bytes(),ini)
    def test_failed_switch_restores_bridge(self):
        self.runop('install');state=self.state();ini=(self.game/'Repentogon'/i.INI).read_bytes();original=i.atomic
        def fail_record(path,*args,**kwargs):
            if path.name=='installation.json':raise OSError('simulated disk failure')
            return original(path,*args,**kwargs)
        with patch.object(i,'atomic',fail_record):
            with self.assertRaises(OSError):self.runop('repair')
        self.assertEqual(self.state(),state);self.assertEqual((self.game/'Repentogon'/i.INI).read_bytes(),ini)
    def test_traversal_and_unknown_dll(self):
        for value in ('../outside','C:/outside','evil:stream'):
            with self.assertRaises(ValueError):i.scoped(self.root,value)
        (self.game/'Repentogon'/i.DLL).write_bytes(b'not ours')
        with self.assertRaises(RuntimeError):self.runop('install')
        self.assertEqual((self.game/'Repentogon'/i.DLL).read_bytes(),b'not ours')
    def test_downgrade_rejected(self):
        self.runop('install');self.manifest('0.7.41')
        with self.assertRaises(ValueError):self.runop('update')
    def test_running_game_rejected_before_changes(self):
        with patch.object(i,'ensure_closed',side_effect=RuntimeError('game running')):
            with self.assertRaises(RuntimeError):self.runop('install')
        self.assertFalse((self.game/'Repentogon'/i.DLL).exists())
    def test_custom_install_found_after_package_moves(self):
        result=self.runop('install')
        self.assertEqual(i.installed_root(self.game),Path(result['base']))
        self.assertEqual(i.operate('status',self.game,self.root/'deleted-package')['version'],'0.7.42')
    def test_long_native_library_path_rejected(self):
        self.home=self.root/('long-profile-'+'a'*130)
        with self.assertRaisesRegex(ValueError,'too long'):self.runop('install')
        self.assertFalse((self.game/'Repentogon'/i.DLL).exists())

if __name__=='__main__':unittest.main(verbosity=2)
