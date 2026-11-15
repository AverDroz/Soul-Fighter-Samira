"""Build a fork's offline installer using a verified existing runtime package."""
import argparse,hashlib,json,os,re,shutil,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def safe(root,name):
    rel=Path(name)
    if rel.is_absolute() or rel.drive or '..' in rel.parts or ':' in name:raise ValueError('Unsafe runtime path: '+name)
    p=(root/rel).resolve()
    if not p.is_relative_to(root.resolve()):raise ValueError('Runtime path escaped root')
    return p
def copy(source,target):target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)

def build(runtime,zig,output):
    from check_display_support import check_display_support
    check_display_support(ROOT)
    from check_native_resources import check
    check(ROOT/'mod')
    info=json.loads((ROOT/'hero.json').read_text());version=info['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('hero.json version must be X.Y.Z')
    runtime=Path(runtime).resolve();manifest=json.loads((runtime/'manifest.json').read_text())
    if manifest.get('protocol')!=1:raise ValueError('Expected protocol 1 runtime')
    files=manifest['files'];base=runtime/'payload'
    for name,sha in files.items():
        p=safe(base,name)
        if not p.is_file() or digest(p)!=sha:raise ValueError('Missing/corrupt runtime file: '+name)
    out=Path(output).resolve()
    archive_path=out.with_name(out.name+'.zip')
    if out.exists() or archive_path.exists():raise ValueError('Use a new output directory; releases are never overwritten')
    if not (base/'python/python.exe').is_file():raise ValueError('Missing embedded Python runtime')
    out.mkdir(parents=True);payload=out/'payload';payload.mkdir()
    for name in files:
        if name.startswith(('python/','external/assets/fonts/')):copy(safe(base,name),payload/name)
    # Reuse the private Python dependencies and their licenses. No download,
    # global Python installation or process creation until the explicit build.
    env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(ROOT/'build/zig-cache'),ZIG_LOCAL_CACHE_DIR=str(ROOT/'build/zig-local-cache'))
    subprocess.run([str(Path(zig).resolve()),'cc','-target','x86-windows-gnu','-O2','-s','-shared',
                    str(ROOT/'companion/bridge.c'),'-o',str(payload/info['dll'])],env=env,check=True)
    csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework/v4.0.30319/csc.exe'
    subprocess.run([str(csc),'/nologo','/target:winexe','/platform:anycpu','/r:System.Windows.Forms.dll',
                    '/r:System.Drawing.dll','/r:System.Web.Extensions.dll','/out:'+str(out/info['setup']),str(ROOT/'companion/Setup.cs')],check=True)
    for source in (ROOT/'external').glob('*.py'):
        if not source.name.startswith('test_'):copy(source,payload/'external'/source.name)
    for source in (ROOT/'external/assets').rglob('*'):
        if source.is_file():copy(source,payload/'external/assets'/source.relative_to(ROOT/'external/assets'))
    for part in ('hud','combat'):
        for source in (ROOT/'mod/resources/gfx'/info['id']/part).rglob('*'):
            if source.is_file():copy(source,payload/source.relative_to(ROOT))
    copy(ROOT/'reference/source/model.glb',payload/'reference/source/model.glb')
    copy(ROOT/'reference/source/rig-events.json',payload/'reference/source/rig-events.json')
    copy(ROOT/'external/presentation.json',payload/'external/presentation.json')
    copy(ROOT/'companion/companion.py',payload/'companion.py')
    copy(ROOT/'companion/installer.py',out/'installer.py')
    (out/'README.txt').write_text(info['name']+' Companion '+version+'\n\nClose Isaac. Run '+info['setup']+
        '. Install/update/repair/uninstall through this tool. Continue using your REPENTOGON launcher.\n'+
        '关闭游戏后运行安装工具；以后仍从原来的 REPENTOGON 启动器进入游戏。\n',encoding='utf8')
    shipped={p.relative_to(payload).as_posix():digest(p) for p in sorted(payload.rglob('*')) if p.is_file()}
    (out/'manifest.json').write_text(json.dumps(dict(app=info['app'],version=version,protocol=1,
        platform='Windows-x64 / REPENTOGON-x86',displayModes=['glfw','layered'],customRepentogonPath=True,files=shipped),indent=2),encoding='utf8')
    (out/'BUILD-INPUTS.json').write_text(json.dumps(dict(source_example=info['source_example'],
        runtime_manifest_sha256=digest(runtime/'manifest.json'),zig_sha256=digest(Path(zig))),indent=2),encoding='utf8')
    with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,out.name+'/'+p.relative_to(out).as_posix())
    print('Built',out,'and',archive_path,'with',len(shipped),'verified payload files')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime-package',required=True);p.add_argument('--zig',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();build(a.runtime_package,a.zig,a.output)
