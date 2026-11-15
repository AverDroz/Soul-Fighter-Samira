"""Check Isaac native XML and registered audio before packaging a playable mod.

Run on the finished mod directory, not the source-only reference snapshot.
Only Python's standard library is required.
"""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def check(mod):
    mod = Path(mod).resolve()
    if not (mod / 'main.lua').is_file():
        raise ValueError(f'Not a finished mod directory: {mod}')
    for path in (mod / 'content').glob('*.xml'):
        ET.parse(path)
    items = mod / 'content/items.xml'
    if items.exists():
        root = ET.parse(items).getroot()
        # Isaac dereferences the version attribute before loading any Lua.
        # Well-formed XML alone is insufficient, even for null-only items.
        if root.tag != 'items' or root.get('version') != '1' or not root.get('gfxroot', '').strip():
            raise ValueError(f'{items}: items requires version="1" and a nonempty gfxroot')
    # Character-menu assets live in content/gfx, not resources/gfx.
    # XML syntax alone does not catch portraits/names referencing absent images.
    for path in (mod / 'content').rglob('*.anm2'):
        root = ET.parse(path).getroot()
        for sheet in root.findall('Content/Spritesheets/Spritesheet'):
            relative = sheet.get('Path', '')
            target = mod / 'resources' / relative if relative.startswith('gfx/') else path.parent / relative
            if not relative or not target.is_file():
                raise ValueError(f'{path}: missing character-menu spritesheet: {target}')
    players = mod / 'content/players.xml'
    if players.exists():
        root = ET.parse(players).getroot()
        for player in root.findall('player'):
            for attr, prefix in (('portrait','portraitroot'),('nameimage','nameimageroot'),('skin','root')):
                if player.get(attr):
                    target = mod / 'resources' / root.get(prefix,root.get('root','')) / player.get(attr)
                    if not target.is_file():
                        raise ValueError(f'{players}: missing player {attr}: {target}')
    for filename, tag, child, leaf in (
        ('music.xml', 'music', 'track', None),
        ('sounds.xml', 'sounds', 'sound', 'sample'),
    ):
        path = mod / 'content' / filename
        if not path.exists():
            continue  # Optional config: remove it when the hero does not use it.
        root = ET.parse(path).getroot()
        if root.tag != tag or not root.get('root', '').strip():
            raise ValueError(f'{path}: missing {tag} root attribute; remove unused config instead of writing <{tag} />')
        names = set()
        for entry in root.findall(child):
            name = entry.get('name')
            if not name or name in names:
                raise ValueError(f'{path}: missing or duplicate {child} name: {name}')
            names.add(name)
            assets = entry.findall(leaf) if leaf else [entry]
            if not assets:
                raise ValueError(f'{path}: no samples for {name}')
            for asset in assets:
                relative = asset.get('path', '')
                target = mod / 'resources' / root.get('root') / relative
                if not relative or not target.is_file():
                    raise ValueError(f'{path}: missing asset for {name}: {target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mod', type=Path)
    check(parser.parse_args().mod)
    print('PASS: native resource XML and registered audio paths')
