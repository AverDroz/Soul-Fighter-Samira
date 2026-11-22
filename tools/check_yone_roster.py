"""Validate the two character-selection ANM2 files and all texture crops."""
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
    for animation in animations:
        for layer in animation.findall('./LayerAnimations/LayerAnimation'):
            path = GFX / sheets[layers[layer.get('LayerId')]]
            assert path.is_file(), path
            with Image.open(path) as image:
                for frame in layer.findall('Frame'):
                    x, y = int(frame.get('XCrop')), int(frame.get('YCrop'))
                    w, h = int(frame.get('Width')), int(frame.get('Height'))
                    assert w > 0 and h > 0 and x + w <= image.width and y + h <= image.height, (filename, path, frame.attrib)
    yone = next(a for a in animations if a.get('Name') == 'Yone')
    used = {sheets[layers[l.get('LayerId')]] for l in yone.findall('./LayerAnimations/LayerAnimation')}
    assert 'yone_menu_model.png' in used
    if filename == 'charactermenu.anm2':
        assert {'yone_menu_name.png', 'samira_menu_paper.png'} <= used
for path in (ROOT / 'resources/gfx/samira/yone-portrait.png', Path(__file__).resolve().parents[1] / 'assets/yone-local/yone-portrait.png'):
    if path.exists():
        with Image.open(path) as image:
            assert image.size == (144, 144), path
print('PASS Yone roster animation names, layers, spritesheets and crop bounds')
