"""Validate both character menus and the original Yone HUD art."""
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = Path(sys.argv[1]) if len(sys.argv) > 1 else None
ROOT = PACKAGE / 'samira_testroom' if PACKAGE else PROJECT / 'src/samira-testroom/mod'
PROVENANCE = PACKAGE / 'provenance' if PACKAGE else PROJECT / 'docs'
GFX = ROOT / 'content/gfx'
players = ET.parse(ROOT / 'content/players.xml').getroot()
assert {'Samira', 'Yone'} <= {p.get('name') for p in players.findall('player')}
yone_crops = []
for filename in ('characterportraits.anm2', 'charactermenu.anm2'):
    actor = ET.parse(GFX / filename).getroot()
    sheets = {s.get('Id'): s.get('Path') for s in actor.findall('./Content/Spritesheets/Spritesheet')}
    layers = {l.get('Id'): l.get('SpritesheetId') for l in actor.findall('./Content/Layers/Layer')}
    animations = actor.findall('./Animations/Animation')
    assert {'Samira', 'Yone'} <= {a.get('Name') for a in animations}
    expected_layers = ['0'] if filename == 'characterportraits.anm2' else ['0', '1', '2', '3', '4']
    for animation in animations:
        tracks = [layer.get('LayerId') for layer in animation.findall('./LayerAnimations/LayerAnimation')]
        assert tracks == expected_layers, (filename, animation.get('Name'), tracks, expected_layers)
    assert list(layers) == expected_layers, (filename, list(layers), expected_layers)
    for animation in animations:
        for layer in animation.findall('./LayerAnimations/LayerAnimation'):
            path = GFX / sheets[layers[layer.get('LayerId')]]
            assert path.is_file(), path
            with Image.open(path) as image:
                for frame in layer.findall('Frame'):
                    x, y = int(frame.get('XCrop')), int(frame.get('YCrop'))
                    w, h = int(frame.get('Width')), int(frame.get('Height'))
                    assert w > 0 and h > 0 and x + w <= image.width and y + h <= image.height, (filename, path, frame.attrib)
    by_name = {a.get('Name'): a for a in animations}
    art_layers = ['0'] if filename == 'characterportraits.anm2' else ['3', '4']
    for layer_id in art_layers:
        query = f'./LayerAnimations/LayerAnimation[@LayerId="{layer_id}"]/Frame'
        samira, yone = (by_name[name].find(query) for name in ('Samira', 'Yone'))
        assert int(yone.get('YCrop')) >= int(samira.get('YCrop')) + int(samira.get('Height')), (filename, layer_id)
        if filename == 'characterportraits.anm2' or layer_id == '4':
            path = GFX / sheets[layers[layer_id]]
            x, y, w, h = (int(yone.get(k)) for k in ('XCrop', 'YCrop', 'Width', 'Height'))
            with Image.open(path) as image:
                yone_crops.append(image.convert('RGBA').crop((x, y, x + w, y + h)).tobytes())
assert yone_crops[0] == yone_crops[1], 'roster and selection use different body art'
for path in (ROOT / 'resources/gfx/samira/yone-portrait.png', PROJECT / 'assets/yone-local/yone-portrait.png'):
    if path.exists():
        with Image.open(path) as image:
            assert image.size == (144, 144), path
            assert image.convert('RGBA').tobytes() != yone_crops[0], 'boss portrait replaced the menu body'

icons = ROOT / 'resources/gfx/yone'
lock = json.loads((PROVENANCE / 'yone-ability-icons.lock.json').read_text(encoding='utf-8'))
tile = lock['tile_size']
names = ('Q', 'Q3', 'W', 'E', 'E2', 'R')
assert tuple(lock['icons']) == names
assert hashlib.sha256((icons / 'ability_icons.png').read_bytes()).hexdigest() == lock['atlas_sha256']
with Image.open(icons / 'ability_icons.png') as image:
    assert image.size == (tile * len(names), tile)
actor = ET.parse(icons / 'ability_icons.anm2').getroot()
sheet = actor.find('./Content/Spritesheets/Spritesheet')
assert sheet.attrib == {'Id': '0', 'Path': 'ability_icons.png'}
animations = actor.findall('./Animations/Animation')
assert [animation.get('Name') for animation in animations] == list(names)
for index, animation in enumerate(animations):
    frame = animation.find('./LayerAnimations/LayerAnimation[@LayerId="0"]/Frame')
    assert tuple(int(frame.get(k)) for k in ('XCrop', 'YCrop', 'Width', 'Height')) == (tile * index, 0, tile, tile)
print('PASS Yone roster, full-body menu art and six native ability icons')
