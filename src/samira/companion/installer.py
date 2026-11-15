"""Offline transactional companion installer. Never changes Isaac executables or saves."""
import argparse, configparser, ctypes, hashlib, json, os, re, shutil, sys, uuid, winreg
from pathlib import Path
from ctypes import wintypes as w

APP = 'SamiraCompanion'
DLL = 'zhlSamiraCompanion.dll'
INI = 'samira-companion.ini'

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def atomic(path, text, encoding='utf-8'):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_text(text, encoding=encoding); os.replace(tmp, path)
    finally: tmp.unlink(missing_ok=True)

def read_json(path): return json.loads(path.read_text(encoding='utf-8-sig'))

def scoped(root, relative):
    path = Path(relative)
    if path.is_absolute() or path.drive or '..' in path.parts or ':' in str(path):
        raise ValueError('Unsafe package path: '+str(relative))
    resolved = (root/path).resolve()
    if not resolved.is_relative_to(root.resolve()): raise ValueError('Path escapes package: '+str(relative))
    return resolved

def selected_path(value):
    value = str(value or '').strip().strip('"')
    if not value or any(ch in value for ch in ('"','\n','\r')): raise ValueError('Select a valid folder path.')
    return Path(os.path.expandvars(value)).expanduser().resolve()


def is_repentogon(path):
    return all((path/name).is_file() for name in ('zhlLoader.dll','isaac-ng.exe','zhlREPENTOGON.dll'))


def game_root(value):
    p = selected_path(value)
    if p.is_file(): p = p.parent
    if p.name.lower() == 'repentogon' and (p.parent/'isaac-ng.exe').is_file(): p = p.parent
    if not (p/'isaac-ng.exe').is_file() and not is_repentogon(p/'Repentogon'):
        raise ValueError('Select the Isaac game folder containing isaac-ng.exe.')
    return p


def repentogon_root(value):
    p = selected_path(value)
    if p.is_file(): p = p.parent
    if is_repentogon(p): return p
    if is_repentogon(p/'Repentogon'): return p/'Repentogon'
    raise ValueError('Select the REPENTOGON runtime folder containing isaac-ng.exe, zhlLoader.dll and zhlREPENTOGON.dll (not just the launcher).')


def installed_root(game, home=None, repentogon=None):
    if home is None:
        # Also find installations made with a custom short --home path.
        try:
            cfg=configparser.ConfigParser(interpolation=None);cfg.read((repentogon or game/'Repentogon')/INI,encoding='utf-16')
            runtime=Path(cfg['Samira']['Runtime']);candidate=runtime.parent.parent
            state=read_json(candidate/'installation.json')
            if state.get('app')==APP and Path(state['game']).resolve()==game.resolve():return candidate
        except (OSError,ValueError,KeyError,configparser.Error):pass
    key = hashlib.sha256(str(game).casefold().encode()).hexdigest()[:16]
    return Path(home or Path(os.environ['LOCALAPPDATA'])/APP)/'installations'/key

def launcher_game():
    # Official launcher configuration lives in the Windows Documents known folder.
    buf=ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None,5,None,0,buf)!=0: return None
    try:
        cfg=configparser.ConfigParser(interpolation=None)
        cfg.read(Path(buf.value)/'My Games/repentogon_launcher.ini',encoding='utf-8-sig')
        return game_root(cfg['General']['IsaacExecutable'])
    except (OSError,ValueError,KeyError,configparser.Error): return None


def discover_games():
    steam = []
    for hive, name, value in [(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                               (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')]:
        try:
            with winreg.OpenKey(hive, name) as key: steam.append(Path(winreg.QueryValueEx(key,value)[0]))
        except OSError: pass
    roots = set(steam)
    for p in steam:
        try:
            for match in re.findall(r'"path"\s+"([^"]+)"', (p/'steamapps/libraryfolders.vdf').read_text(encoding='utf-8')):
                roots.add(Path(match.replace('\\\\','\\')))
        except OSError: pass
    result = []
    for root in roots:
        p = root/'steamapps/common/The Binding of Isaac Rebirth'
        try: result.append(str(game_root(p)))
        except ValueError: pass
    configured=launcher_game()
    if configured: result.insert(0,str(configured))
    records=Path(os.environ['LOCALAPPDATA'])/APP/'installations'
    for record in records.glob('*/installation.json'):
        try:
            state=read_json(record)
            if state.get('app')==APP: result.append(str(game_root(state['game'])))
        except (OSError,ValueError,KeyError): pass
    return list(dict.fromkeys(result))


def process_paths():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; k.OpenProcess.restype=w.HANDLE
    k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    k.CloseHandle.argtypes=[w.HANDLE]
    pids=(w.DWORD*8192)(); count=w.DWORD()
    if not ctypes.windll.psapi.EnumProcesses(pids,ctypes.sizeof(pids),ctypes.byref(count)): raise ctypes.WinError()
    for pid in pids[:count.value//ctypes.sizeof(w.DWORD)]:
        handle=k.OpenProcess(0x1000,False,pid)
        if not handle: continue
        try:
            buf=ctypes.create_unicode_buffer(32768); length=w.DWORD(32768)
            if k.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(length)): yield Path(buf.value).resolve()
        finally: k.CloseHandle(handle)


def discover_repentogon(game):
    candidates=[]
    try:
        base=installed_root(game)
        state=read_json(base/'installation.json')
        if state.get('app')==APP and Path(state['game']).resolve()==game:
            candidates.append(Path(state.get('repentogon',str(game/'Repentogon'))))
    except (OSError,ValueError,KeyError): pass
    candidates.extend((game/'Repentogon',game))
    try: candidates.extend(p.parent for p in process_paths() if p.name.lower()=='isaac-ng.exe')
    except OSError: pass
    return list(dict.fromkeys(str(p.resolve()) for p in candidates if is_repentogon(p)))


def discover(selected_game=None):
    games=[str(game_root(selected_game))] if selected_game else discover_games()
    return {'games':games,'repentogon':discover_repentogon(Path(games[0])) if games else []}


def ensure_closed(game, repentogon=None):
    targets={game/'isaac-ng.exe',game/'Repentogon/isaac-ng.exe',(repentogon or game/'Repentogon')/'isaac-ng.exe'}
    if any(path in targets for path in process_paths()):
        raise RuntimeError('Close Isaac before installing, repairing, updating or uninstalling.')

def validate_manifest(package):
    manifest=read_json(package/'manifest.json')
    if manifest.get('app')!=APP or manifest.get('protocol')!=1 or not re.fullmatch(r'\d+\.\d+\.\d+',manifest.get('version','')):
        raise ValueError('Unsupported package/manifest version.')
    files=manifest['files']
    if not isinstance(files,dict) or not all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in files.values()):
        raise ValueError('Invalid file hashes.')
    for required in ('python/pythonw.exe','python/python.exe','companion.py','external/overlay.py',DLL):
        if required not in files: raise ValueError('Package is incomplete: '+required)
    for relative, expected in files.items():
        source=scoped(package/'payload',relative)
        if not source.is_file() or digest(source)!=expected: raise ValueError('Package file is missing or corrupt: '+relative)
    return manifest

def verify_runtime(root, manifest):
    return [name for name,expected in manifest['files'].items()
            if not scoped(root,name).is_file() or digest(scoped(root,name))!=expected]

def remove_owned_tree(root, manifest):
    # Remove only recorded package files. User-added files and settings are preserved.
    for name in manifest['files']:
        p=scoped(root,name)
        if p.is_file(): p.unlink()
    for p in sorted(root.rglob('*'),key=lambda x:len(x.parts),reverse=True):
        if p.is_dir() and not p.is_symlink():
            try: p.rmdir()
            except OSError: pass
    try: root.rmdir()
    except OSError: pass

def bridge_ini(game, runtime):
    return '[Samira]\nProtocol=1\nGame='+str(game)+'\nRuntime='+str(runtime)+'\n'

def switch(game, base, state, entry, previous, dest):
    dll=dest/DLL; ini=dest/INI
    former=Path(state.get('repentogon',str(game/'Repentogon')))
    moving=bool(state.get('current')) and former!=dest
    former_files={}
    if moving:
        for name in (DLL,INI):
            file=former/name
            if file.exists(): former_files[name]=file.read_bytes()
        if former_files and (INI not in former_files or str(base) not in former_files[INI].decode('utf-16')):
            raise RuntimeError('Previous bridge belongs to another installation; no files changed.')
    old_dll=dll.read_bytes() if dll.exists() else None
    old_ini=ini.read_bytes() if ini.exists() else None
    if old_ini is not None and str(base) not in old_ini.decode('utf-16'):
        raise RuntimeError('Bridge belongs to another installation; no files changed.')
    if old_dll is not None:
        known={v['manifest']['files'][DLL] for v in state.get('versions',[])}
        if digest(dll) not in known and (not state.get('current') or moving):
            raise RuntimeError('Unrecognized bridge DLL. Refusing to overwrite it.')
    runtime=scoped(base,entry['directory'])
    try:
        temp=dest/(DLL+'.new'); shutil.copy2(runtime/DLL,temp); os.replace(temp,dll)
        atomic(ini,bridge_ini(game,runtime),encoding='utf-16')
        if moving:
            for name in former_files: (former/name).unlink()
        state.update(app=APP,game=str(game),repentogon=str(dest),current=entry['directory'],previous=previous)
        atomic(base/'installation.json',json.dumps(state,ensure_ascii=False,indent=2))
    except Exception:
        # Restore the former bridge/config; game is required to be closed.
        if old_dll is None: dll.unlink(missing_ok=True)
        else: dll.write_bytes(old_dll)
        if old_ini is None: ini.unlink(missing_ok=True)
        else: ini.write_bytes(old_ini)
        for name,data in former_files.items(): (former/name).write_bytes(data)
        raise
    finally: (dest/(DLL+'.new')).unlink(missing_ok=True)

def effective_presentation(base,state):
    mode=state.get('presentation')
    if mode in ('glfw','layered'):return mode
    if state.get('current'):
        try:
            mode=read_json(scoped(base,state['current'])/'external/presentation.json').get('mode')
            if mode in ('glfw','layered'):return mode
        except (OSError,ValueError):pass
    return 'glfw'

def operate(action, game, package, home=None, repentogon=None, presentation=None):
    if presentation not in (None,'glfw','layered'):raise ValueError('Invalid display mode.')
    game=game_root(game)
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateMutexW.argtypes=[w.LPVOID,w.BOOL,w.LPCWSTR];k.CreateMutexW.restype=w.HANDLE
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
    k.ReleaseMutex.argtypes=[w.HANDLE];k.CloseHandle.argtypes=[w.HANDLE]
    mutex=k.CreateMutexW(None,False,'Local\\SamiraSetup-'+hashlib.sha256(str(game).casefold().encode()).hexdigest()[:16])
    if not mutex:raise ctypes.WinError(ctypes.get_last_error())
    acquired=k.WaitForSingleObject(mutex,0) in (0,128)
    try:
        if not acquired:raise RuntimeError('Another setup operation is in progress for this game.')
        return _operate(action,game,package,home,repentogon,presentation)
    finally:
        if acquired:k.ReleaseMutex(mutex)
        k.CloseHandle(mutex)

def _operate(action, game, package, home=None, repentogon=None, presentation=None):
    game=game_root(game)
    selected=repentogon_root(repentogon) if repentogon else None
    base=installed_root(game,home,selected); record=base/'installation.json'
    state=read_json(record) if record.exists() else {'app':APP,'game':str(game),'versions':[]}
    if state.get('app')!=APP or Path(state.get('game','')).resolve()!=game: raise ValueError('Installation identity mismatch.')
    if selected:
        dest=selected
    elif state.get('repentogon'):
        dest=Path(state['repentogon'])
    else:
        candidates=discover_repentogon(game)
        local=[p for p in candidates if Path(p) in (game/'Repentogon',game)]
        if len(local)==1: dest=Path(local[0])
        elif len(candidates)==1: dest=Path(candidates[0])
        else: raise ValueError('Select the REPENTOGON runtime folder manually; no unique installation was found.')
    former=Path(state.get('repentogon',str(game/'Repentogon')))
    if action in ('uninstall','rollback','status','display') and state.get('current') and dest!=former:
        raise ValueError('Use the installed REPENTOGON folder for this action. Use Repair or Update to change its location.')
    if action=='status':
        current=next((v for v in state['versions'] if v['directory']==state.get('current')),None)
        return {'installed':bool(current),'base':str(base),'repentogon':str(dest),'version':current['manifest']['version'] if current else None,
                'presentation':effective_presentation(base,state),
                'damaged':verify_runtime(scoped(base,current['directory']),current['manifest']) if current else []}
    ensure_closed(game,dest)
    if state.get('current') and former!=dest: ensure_closed(game,former)
    if action=='display':
        current=next((v for v in state['versions'] if v['directory']==state.get('current')),None)
        if not current or not current['manifest'].get('displayModes'):
            raise ValueError('Update companion from this full package before changing display mode.')
        if presentation is None:raise ValueError('Select Standard or Black-screen compatibility mode first.')
        state['presentation']=presentation
        atomic(record,json.dumps(state,ensure_ascii=False,indent=2))
        return {'message':'Display mode saved. Restart Isaac.','presentation':presentation,'repentogon':str(dest)}
    if action=='uninstall':
        dll=dest/DLL; ini=dest/INI
        if dll.exists() and not state.get('current') and digest(dll) not in {v['manifest']['files'][DLL] for v in state['versions']}:
            raise RuntimeError('Unrecognized bridge; no files removed.')
        if ini.exists() and str(base) not in ini.read_text(encoding='utf-16'):
            raise RuntimeError('Bridge belongs to another installation; no files removed.')
        dll.unlink(missing_ok=True); ini.unlink(missing_ok=True)
        for entry in state['versions']: remove_owned_tree(scoped(base,entry['directory']),entry['manifest'])
        state.update(current=None,previous=None,versions=[])
        atomic(record,json.dumps(state,ensure_ascii=False,indent=2))
        return {'message':'Uninstalled companion and bridge. Workshop mod, game saves, settings and logs were preserved.'}
    if action=='rollback':
        repentogon_root(dest)
        entry=next((v for v in state['versions'] if v['directory']==state.get('previous')),None)
        if not entry: raise ValueError('No previous version is available.')
        if dest not in (game/'Repentogon',game) and not entry['manifest'].get('customRepentogonPath'):
            raise ValueError('This older version does not support custom REPENTOGON paths. Keep the current version or move the bridge back with Repair first.')
        if verify_runtime(scoped(base,entry['directory']),entry['manifest']): raise ValueError('Previous version is damaged. Repair from its original package.')
        switch(game,base,state,entry,state.get('current'),dest)
        return {'message':'Rolled back to '+entry['manifest']['version']}
    repentogon_root(dest)
    manifest=validate_manifest(package)
    if presentation is not None and not manifest.get('displayModes'):
        raise ValueError('This package does not support display mode selection.')
    # Store preferences outside immutable version files. An update from the
    # layered-only test package keeps that mode even without a prior override.
    if manifest.get('displayModes'):
        state['presentation']=presentation or (effective_presentation(base,state) if state.get('current') else
            read_json(package/'payload/external/presentation.json').get('mode','glfw'))
    current=next((v for v in state['versions'] if v['directory']==state.get('current')),None)
    if current and tuple(map(int,manifest['version'].split('.')))<tuple(map(int,current['manifest']['version'].split('.'))):
        raise ValueError('Older package: use Roll back, or uninstall before installing an older release.')
    # Fresh immutable directory, including repairs; previous runtime stays intact.
    relative='versions/'+manifest['version']+'-'+uuid.uuid4().hex[:12]
    target=scoped(base,relative)
    if any(len(str(target/name))>=248 for name in manifest['files'] if name.endswith(('.dll','.pyd','.exe'))):
        raise ValueError('Runtime path is too long for Windows DLL loading. Use a shorter --home directory before installing.')
    target.mkdir(parents=True)
    entry={'directory':relative,'manifest':manifest,'package':str(package)}
    try:
        for name in manifest['files']:
            out=scoped(target,name); out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(scoped(package/'payload',name),out)
        damaged=verify_runtime(target,manifest)
        if damaged: raise ValueError('Copy verification failed: '+damaged[0])
        # Keep an installed maintenance UI independent of the extracted ZIP folder.
        for name in ('SamiraSetup.exe','installer.py'):
            if (package/name).exists():
                temp=base/(name+'.new');shutil.copy2(package/name,temp)
                try: os.replace(temp,base/name)
                except PermissionError:
                    if name!='SamiraSetup.exe' or not (base/name).exists():raise
                    # A maintenance UI may be running from this exact EXE. Its
                    # stable CLI remains usable; a later package launch replaces it.
                finally:temp.unlink(missing_ok=True)
        state['versions'].append(entry)
        switch(game,base,state,entry,state.get('current'),dest)
    except Exception:
        remove_owned_tree(target,manifest)
        raise
    return {'message':action.capitalize()+' complete: '+manifest['version'], 'base':str(base), 'runtime':str(target),'repentogon':str(dest),
            'presentation':effective_presentation(base,state)}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--action',choices=['discover','install','repair','update','uninstall','rollback','status','display'],required=True)
    p.add_argument('--game'); p.add_argument('--repentogon'); p.add_argument('--package',default=str(Path(__file__).parent)); p.add_argument('--home')
    p.add_argument('--presentation',choices=['glfw','layered'])
    a=p.parse_args()
    result=discover(a.game) if a.action=='discover' else operate(a.action,a.game,Path(a.package).resolve(),a.home,a.repentogon,a.presentation)
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':
    try: main()
    except Exception as error: print(json.dumps({'error':str(error)},ensure_ascii=True)); sys.exit(1)
