"""Exercise the WinForms setup's actual ProcessStartInfo path, not a CLI substitute."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
HARNESS=r'''
using System;
using System.Diagnostics;
using System.Reflection;
using System.Web.Script.Serialization;
class SetupHarness {
 [STAThread]static void Main(string[] args) {
  using(var form=new Setup()) {
   var flags=BindingFlags.Instance|BindingFlags.NonPublic;
   if(args[0]=="quote") {
    var quote=typeof(Setup).GetMethod("Q",flags);
    Func<string,string> q=s=>(string)quote.Invoke(form,new object[]{s});
    var values=new JavaScriptSerializer().Deserialize<string[]>(args[2]);
    string command="-I -c "+q("import sys,json;print(json.dumps(sys.argv[1:]))");
    foreach(string value in values)command+=" "+q(value);
    var start=new ProcessStartInfo(args[1],command);
    start.UseShellExecute=false;start.CreateNoWindow=true;start.RedirectStandardOutput=true;
    using(var p=Process.Start(start)){Console.Write(p.StandardOutput.ReadToEnd());p.WaitForExit();Environment.ExitCode=p.ExitCode;}
   } else {
    typeof(Setup).GetField("python",flags).SetValue(form,args[1]);
    typeof(Setup).GetField("root",flags).SetValue(form,args[2]);
    typeof(Setup).GetField("package",flags).SetValue(form,args[2]);
    var result=typeof(Setup).GetMethod("Call",flags).Invoke(form,new object[]{args[4],args[3],"",args.Length>5?args[5]:""});
    Console.Write(new JavaScriptSerializer().Serialize(result));
   }
  }
 }
}
'''

class SetupArgumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='setup-args-')
        cls.root=Path(cls.temp.name);cs=cls.root/'Harness.cs';cs.write_text(HARNESS)
        cls.exe=cls.root/'Harness.exe'
        csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework/v4.0.30319/csc.exe'
        subprocess.run([str(csc),'/nologo','/target:exe','/main:SetupHarness','/r:System.Windows.Forms.dll',
                        '/r:System.Drawing.dll','/r:System.Web.Extensions.dll','/out:'+str(cls.exe),str(HERE/'Setup.cs'),str(cs)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def run_harness(self,args,env=None):
        result=subprocess.run([str(self.exe),*args],env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=45)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)
    def test_windows_argv_roundtrip(self):
        values=['',r'C:\Program Files (x86)\Steam\Samira-Companion'+'\\',
                'C:\\中文 目录\\包\\','C:\\','\\','two trailing\\\\',
                'a "quoted" value',r'backslash\"quote','plain','a b','line\nbreak']
        self.assertEqual(self.run_harness(['quote',sys.executable,json.dumps(values)]),values)
    def test_real_setup_call_install_repair_uninstall(self):
        package=self.root/'中文 Companion package';package.mkdir()
        (package/'installer.py').write_bytes((HERE/'installer.py').read_bytes())
        files={}
        for name in ('python/python.exe','python/pythonw.exe','companion.py','external/overlay.py','zhlSamiraCompanion.dll'):
            target=package/'payload'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'isolated test payload')
            files[name]=hashlib.sha256(target.read_bytes()).hexdigest()
        config=package/'payload/external/presentation.json';config.write_text('{"mode":"glfw"}')
        files['external/presentation.json']=hashlib.sha256(config.read_bytes()).hexdigest()
        (package/'manifest.json').write_text(json.dumps(dict(app='SamiraCompanion',version='0.7.71',protocol=1,displayModes=['glfw','layered'],files=files)))
        game=self.root/'Steam library 中文'/'Isaac';(game/'Repentogon').mkdir(parents=True)
        for name in ('isaac-ng.exe','zhlLoader.dll','zhlREPENTOGON.dll'):(game/'Repentogon'/name).write_bytes(b'original')
        saves=game/'data/save.dat';saves.parent.mkdir();saves.write_bytes(b'preserve save')
        env=dict(os.environ,LOCALAPPDATA=str(self.root/'local'))
        def call(action,mode=''):return self.run_harness(['call',sys.executable,str(package)+'\\',str(game)+'\\',action,mode],env)
        installed=call('install','layered');self.assertEqual(call('status')['presentation'],'layered');call('display','glfw');self.assertEqual(call('status')['presentation'],'glfw');self.assertEqual(call('status')['damaged'],[])
        self.assertEqual(call('status')['version'],'0.7.71')
        (Path(installed['runtime'])/'companion.py').write_bytes(b'corrupt')
        self.assertIn('companion.py',call('status')['damaged']);call('repair')
        self.assertEqual(call('status')['damaged'],[])
        call('uninstall');self.assertFalse(call('status')['installed'])
        self.assertEqual(saves.read_bytes(),b'preserve save')
        self.assertEqual((game/'Repentogon/zhlREPENTOGON.dll').read_bytes(),b'original')

if __name__=='__main__':unittest.main(verbosity=2)
