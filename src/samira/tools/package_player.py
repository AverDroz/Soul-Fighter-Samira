"""Build a player ZIP whose only top-level entry is the actual Isaac mod folder."""
import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile


def check_package(archive,mod_name):
    with zipfile.ZipFile(archive) as z:
        names=set(z.namelist())
        if not names or any(not n.startswith(mod_name+'/') for n in names):
            raise ValueError('ZIP must contain only the actual mod folder; no release wrapper or loose README files.')
        for name in ('main.lua','INSTALL.txt','CONSOLE-COMMANDS.txt'):
            if mod_name+'/'+name not in names:raise ValueError('Missing player file: '+name)
        if not any(n.startswith(mod_name+'/') and n.count('/')==1 and '-Companion' in Path(n).stem and n.endswith('.zip') for n in names):
            raise ValueError('Companion ZIP must be inside the actual mod folder.')
        if z.testzip() is not None:raise ValueError('Corrupt player ZIP.')


def package(mod,mod_name,companion,install,commands,output):
    mod=Path(mod).resolve();output=Path(output).resolve();companion=Path(companion).resolve()
    if not mod_name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in mod_name):
        raise ValueError('Use the real lowercase mod folder name, such as yasuo_isaac.')
    if output.exists():raise ValueError('Use a fresh archive name.')
    if not (mod/'main.lua').is_file():raise ValueError('Select the mod directory containing main.lua.')
    if '-Companion' not in companion.stem or companion.suffix.lower()!='.zip':raise ValueError('Select the complete Hero-Companion.zip.')
    from check_native_resources import check
    check(mod)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hero-player-') as tmp:
        root=Path(tmp);target=root/mod_name
        shutil.copytree(mod,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.log','*.zip','.git'))
        shutil.copy2(install,target/'INSTALL.txt');shutil.copy2(commands,target/'CONSOLE-COMMANDS.txt')
        shutil.copy2(companion,target/companion.name)
        check(target)
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(target.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(root).as_posix(),compress_type=zipfile.ZIP_STORED if p.suffix=='.zip' else zipfile.ZIP_DEFLATED)
    check_package(output,mod_name)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for flag in ('mod','mod-name','companion','install','commands','output'):p.add_argument('--'+flag,required=True)
    a=p.parse_args();print(package(a.mod,a.mod_name,a.companion,a.install,a.commands,a.output))
