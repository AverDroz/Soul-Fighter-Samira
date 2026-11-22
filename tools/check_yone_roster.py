"""Validate the shared layer layout and texture crops in both character menus."""
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'src/samira-testroom/mod'
GFX = ROOT / 'content/gfx'
players = ET.parse(ROOT / 'content/players.xml').getroot()
assert {'Samira', 'Yone'} <= {p.get('name') for p in players.findall('player')}
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
for path in (ROOT / 'resources/gfx/samira/yone-portrait.png', Path(__file__).resolve().parents[1] / 'assets/yone-local/yone-portrait.png'):
    if path.exists():
        with Image.open(path) as image:
            assert image.size == (144, 144), path
print('PASS Yone roster animation names, layers, spritesheets and crop bounds')
