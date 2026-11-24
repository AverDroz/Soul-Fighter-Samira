"""Validate the playable roster, character menu art and the original Yone HUD art."""
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
player_names = [p.get('name') for p in players.findall('player')]
miss_fortune = 'Miss Fortune'
assert player_names == ['Samira', 'Yone', miss_fortune], player_names
miss_fortune_player = players.find(f'player[@name="{miss_fortune}"]')
assert miss_fortune_player.get('hp') == '6'
for attribute, filename, size in (
    ('nameimage', 'mf-name.png', (112, 32)),
    ('portrait', 'mf-portrait.png', (144, 144)),
):
    assert miss_fortune_player.get(attribute) == filename
    path = ROOT / 'resources' / players.get(attribute + 'root') / filename
    with Image.open(path) as image:
        assert image.size == size and image.convert('RGBA').getchannel('A').getbbox(), path

yone_crops = []
miss_fortune_crops = []
for filename in ('characterportraits.anm2', 'charactermenu.anm2'):
    actor = ET.parse(GFX / filename).getroot()
    sheets = {s.get('Id'): s.get('Path') for s in actor.findall('./Content/Spritesheets/Spritesheet')}
    layers = {l.get('Id'): l.get('SpritesheetId') for l in actor.findall('./Content/Layers/Layer')}
    animations = actor.findall('./Animations/Animation')
    assert [a.get('Name') for a in animations] == player_names, filename
    expected_layers = ['0'] if filename == 'characterportraits.anm2' else ['0', '1', '2', '3', '4']
    for animation in animations:
        assert animation.find('./RootAnimation/Frame') is not None, (filename, animation.get('Name'))
        tracks = [layer.get('LayerId') for layer in animation.findall('./LayerAnimations/LayerAnimation')]
        assert tracks == expected_layers, (filename, animation.get('Name'), tracks, expected_layers)
    assert list(layers) == expected_layers, (filename, list(layers), expected_layers)
    for animation in animations:
        for layer in animation.findall('./LayerAnimations/LayerAnimation'):
            path = GFX / sheets[layers[layer.get('LayerId')]]
            assert path.is_file(), path
            with Image.open(path) as image:
                frames = layer.findall('Frame')
                assert frames, (filename, animation.get('Name'), layer.get('LayerId'))
                for frame in frames:
                    x, y = int(frame.get('XCrop')), int(frame.get('YCrop'))
                    w, h = int(frame.get('Width')), int(frame.get('Height'))
                    assert 0 <= x < x + w <= image.width and 0 <= y < y + h <= image.height, (filename, path, frame.attrib)
                    crop = image.crop((x, y, x + w, y + h)).convert('RGBA')
                    assert crop.getchannel('A').getbbox(), (filename, animation.get('Name'), layer.get('LayerId'))
    by_name = {a.get('Name'): a for a in animations}
    art_layers = ['0'] if filename == 'characterportraits.anm2' else ['3', '4']
    for layer_id in art_layers:
        query = f'./LayerAnimations/LayerAnimation[@LayerId="{layer_id}"]/Frame'
        samira, yone, miss_fortune_frame = (by_name[name].find(query) for name in player_names)
        assert int(yone.get('YCrop')) >= int(samira.get('YCrop')) + int(samira.get('Height')), (filename, layer_id)
        assert int(miss_fortune_frame.get('YCrop')) >= int(yone.get('YCrop')) + int(yone.get('Height')), (filename, layer_id)
        if filename == 'characterportraits.anm2' or layer_id == '4':
            path = GFX / sheets[layers[layer_id]]
            with Image.open(path) as image:
                rgba = image.convert('RGBA')
                for frame, crops in ((yone, yone_crops), (miss_fortune_frame, miss_fortune_crops)):
                    x, y, w, h = (int(frame.get(k)) for k in ('XCrop', 'YCrop', 'Width', 'Height'))
                    crop = rgba.crop((x, y, x + w, y + h))
                    assert crop.getbbox(), (filename, frame.attrib)
                    crops.append(crop.tobytes())
assert yone_crops[0] == yone_crops[1], 'roster and selection use different body art'
assert miss_fortune_crops[0] == miss_fortune_crops[1], 'Miss Fortune roster and selection use different body art'
assert miss_fortune_crops[0] != yone_crops[0], 'Miss Fortune shares the Yone menu body'
with Image.open(ROOT / 'resources/gfx/samira/mf-portrait.png') as image:
    assert image.convert('RGBA').tobytes() != miss_fortune_crops[0], 'portrait replaced the Miss Fortune menu body'

fallback = ROOT / 'resources/gfx/mf'
actor = ET.parse(fallback / 'fallback.anm2').getroot()
assert actor.find('./Animations').get('DefaultAnimation') == 'Idle0'
assert actor.find('./Content/Spritesheets/Spritesheet').get('Path') == 'fallback.png'
animations = actor.findall('./Animations/Animation')
expected_names = [f'{motion}{direction}' for motion in ('Idle', 'Walk') for direction in range(8)]
assert [a.get('Name') for a in animations] == expected_names
with Image.open(fallback / 'fallback.png') as image:
    rgba = image.convert('RGBA')
    assert rgba.size == (512, 320)
    idle_crops = []
    for index, animation in enumerate(animations):
        frames = animation.findall('./LayerAnimations/LayerAnimation[@LayerId="0"]/Frame')
        moving = index >= 8
        frame_count = 4 if moving else 1
        assert len(frames) == int(animation.get('FrameNum')) == frame_count
        motion_crops = []
        for frame_index, frame in enumerate(frames):
            x, y, w, h, px, py = (int(frame.get(k)) for k in ('XCrop', 'YCrop', 'Width', 'Height', 'XPivot', 'YPivot'))
            assert (x, y, w, h, px, py) == (64 * (index % 8), 64 * (frame_index + moving), 64, 64, 32, 50)
            crop = rgba.crop((x, y, x + w, y + h))
            assert crop.getchannel('A').getbbox(), animation.get('Name')
            motion_crops.append(crop.tobytes())
        assert len(set(motion_crops)) == frame_count, animation.get('Name')
        if not moving:
            idle_crops.extend(motion_crops)
    assert len(set(idle_crops)) == 8
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
print('PASS Samira, Yone and Miss Fortune roster, menu art, Miss Fortune fallback and six Yone ability icons')
