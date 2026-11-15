"""Game-scoped supervisor. Stdlib only: no GPU/runtime assets until Samira is active."""
import argparse, ctypes, json, os, re, subprocess, sys, time, traceback
from ctypes import wintypes as w
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROTOCOL = 1
K = ctypes.WinDLL('kernel32', use_last_error=True)
K.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; K.OpenProcess.restype = w.HANDLE
K.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]; K.WaitForSingleObject.restype = w.DWORD
K.CloseHandle.argtypes = [w.HANDLE]
K.CreateMutexW.argtypes = [w.LPVOID, w.BOOL, w.LPCWSTR]; K.CreateMutexW.restype = w.HANDLE

def documents_folder():
    # Windows knows the real Unicode path, including redirected/OneDrive Documents.
    buf = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) != 0:
        raise RuntimeError('Cannot find Documents; run Isaac once to create savedatapath.txt.')
    return Path(buf.value)

def save_folder(game, repentogon=None, notes=None):
    notes = notes if notes is not None else []
    folders = []
    for base in (repentogon or game/'Repentogon', game):
        source = base/'savedatapath.txt'
        try:
            raw = source.read_bytes()
            encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
            try: text = raw.decode(encoding)
            except UnicodeError: text = raw.decode('mbcs')
            match = re.search(r'Save Data Path:\s*([^\r\n]+)', text)
            if not match:
                notes.append('No Save Data Path in '+str(source)); continue
            value = Path(match[1].split('Modding Data Path:', 1)[0].strip())
            if not value.is_absolute() or not value.is_dir():
                notes.append('Ignoring missing/invalid save directory: '+str(value)); continue
            if (value/'log.txt').is_file(): return value
            folders.append(value)
            notes.append('No log.txt yet in '+str(value))
        except (OSError, UnicodeError) as exc:
            notes.append('Cannot read '+str(source)+': '+str(exc))
    fallback = documents_folder()/'My Games/Binding of Isaac Repentance+'
    if (fallback/'log.txt').is_file(): return fallback
    # A new game session can create the log after the supervisor starts.
    return folders[0] if folders else fallback

class Events:
    def __init__(self, path):
        self.path = path
        self.offset = path.stat().st_size if path.exists() else 0
        self.pending = b''
    def poll(self):
        try:
            size = self.path.stat().st_size
            if size < self.offset: self.offset = 0; self.pending = b''
            if size == self.offset: return []
            with self.path.open('rb') as stream:
                stream.seek(self.offset); chunk = stream.read(2*1024*1024); self.offset = stream.tell()
        except OSError: return []
        lines = (self.pending+chunk).split(b'\n'); self.pending = lines.pop()[-65536:]
        result = []
        for line in lines:
            _, found, payload = line.partition(b'[SAMIRA_EXTERNAL] ')
            if not found: continue
            try:
                data = json.loads(payload)
                if isinstance(data, dict) and data.get('version') == 1: result.append(data)
            except (ValueError, UnicodeError): pass
        return result

def stop_renderer(child, stop):
    if not child: return
    stop.touch()
    try: child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # Only our exact child process. Never terminate another Python/game process.
        child.terminate(); child.wait(timeout=5)

def display_arguments(root):
    # The installer writes this per-game preference only while Isaac is closed.
    # Missing/older records retain the package's original presentation default.
    try:
        state=json.loads((root.parent.parent/'installation.json').read_text(encoding='utf-8-sig'))
        mode=state.get('presentation')
        if mode in ('glfw','layered'):return ['--presentation',mode]
    except (OSError,ValueError):pass
    return []

def run(args):
    handle = K.OpenProcess(0x100000, False, args.game_pid) # SYNCHRONIZE, no process memory access
    if not handle: raise RuntimeError('Game process is no longer available.')
    mutex = K.CreateMutexW(None, False, 'Local\\SamiraCompanion-'+str(args.game_pid))
    if ctypes.get_last_error() == 183: K.CloseHandle(handle); K.CloseHandle(mutex); return
    if not mutex: K.CloseHandle(handle); raise ctypes.WinError(ctypes.get_last_error())
    game = Path(args.game_dir).resolve()
    path_notes = []
    folder = save_folder(game, Path(args.repentogon_dir).resolve() if args.repentogon_dir else None, path_notes)
    state = ROOT.parent.parent/'logs'/str(args.game_pid)
    state.mkdir(parents=True, exist_ok=True)
    stop = state/'stop.request'; stop.unlink(missing_ok=True)
    log = (state/'supervisor.log').open('a', encoding='utf-8', buffering=1)
    def note(msg): log.write(time.strftime('%Y-%m-%d %H:%M:%S ')+msg+'\n')
    tail = Events(folder/'log.txt'); child = None; output = None
    last_active = time.monotonic(); retry_at = 0; failures = 0; blocked = None
    try:
        note('Waiting for Samira. Runtime='+str(ROOT))
        for message in path_notes: note(message)
        note('Game log='+str(folder/'log.txt')+'; exists='+str((folder/'log.txt').is_file()))
        while K.WaitForSingleObject(handle, 250) == 258:
            now = time.monotonic()
            if child and child.poll() is not None:
                note('Renderer exited: '+str(child.returncode)); child = None
                if output: output.close(); output = None
                failures += 1; retry_at = now+min(60, 5*failures)
            for event in tail.poll():
                if not event.get('active'): continue
                if event.get('companionProtocol', 1) != PROTOCOL:
                    version = event.get('companionProtocol')
                    if blocked != version: note('Incompatible protocol '+str(version)+'. Update companion; native fallback stays active.')
                    blocked = version
                    if child: stop_renderer(child, stop); child = None
                    if output: output.close(); output = None
                    continue
                blocked = None; last_active = now
                if not child and now >= retry_at and failures < 3:
                    stop.unlink(missing_ok=True)
                    output = (state/'renderer.log').open('ab')
                    command = [str(ROOT/'python/pythonw.exe'), '-I', '-B', str(ROOT/'external/overlay.py'),
                               '--log', str(folder/'log.txt'), '--status-dir', str(game/'data/samira_external_link'),
                               '--stop-file', str(stop), '--owner-pid', str(args.game_pid)]+display_arguments(ROOT)
                    child = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=output,
                                             creationflags=subprocess.CREATE_NO_WINDOW)
                    note('Renderer started pid='+str(child.pid))
            # Pauses and floor loads do not churn processes; release after 90 seconds without Samira packets.
            if child and now-last_active > 90:
                stop_renderer(child, stop); child = None
                if output: output.close(); output = None
                note('Idle: renderer released.')
        note('Game exited; stopping renderer.')
    finally:
        stop_renderer(child, stop)
        if output: output.close()
        log.close(); K.CloseHandle(mutex); K.CloseHandle(handle)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-pid', type=int, required=True)
    parser.add_argument('--game-dir', required=True)
    parser.add_argument('--repentogon-dir')
    try: run(parser.parse_args())
    except Exception:
        folder = ROOT.parent.parent/'logs'
        folder.mkdir(parents=True, exist_ok=True)
        with (folder/'startup-error.log').open('a', encoding='utf-8') as stream: traceback.print_exc(file=stream)
        sys.exit(1)
