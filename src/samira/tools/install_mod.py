"""Explicit game path, scoped backup and copy; no renderer installation or launch."""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def install(game):
    from check_native_resources import check
    check(ROOT/'mod')
    info=json.loads((ROOT/'hero.json').read_text());sys.path.insert(0,str(ROOT/'companion'))
    import installer
    game=installer.game_root(game);installer.ensure_closed(game)
    target=game/'mods'/info['mod_directory'];target_resolved=target.resolve()
    if target.is_symlink() or target_resolved.parent!=(game/'mods').resolve():raise ValueError('Mod destination escaped the mods folder.')
    import xml.etree.ElementTree as ET
    metadata=ET.parse(ROOT/'mod/metadata.xml')
    if metadata.findtext('directory')!=info['mod_directory']:raise ValueError('Project metadata and hero.json disagree.')
    if target.exists():
        if not (target/'metadata.xml').is_file() or ET.parse(target/'metadata.xml').findtext('directory')!=info['mod_directory']:
            raise ValueError('Existing destination is not this hero mod.')
    backup=ROOT/'backups'/time.strftime('%Y%m%d-%H%M%S')
    files=[p for p in (ROOT/'mod').rglob('*') if p.is_file()]
    for source in files:
        rel=source.relative_to(ROOT/'mod');dest=target/rel
        if not dest.resolve().is_relative_to(target_resolved):raise ValueError('Destination symlink escapes the mod.')
        if dest.exists() and digest(source)!=digest(dest):
            old=backup/rel;old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,old)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        if digest(source)!=digest(dest):raise ValueError('Copy verification failed: '+str(rel))
    print('Installed and verified',len(files),'files to',target)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--game',required=True);a=p.parse_args();install(a.game)
