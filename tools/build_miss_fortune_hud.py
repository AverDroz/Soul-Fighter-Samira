"""Build Isaac HUD sprites from the supplied Skin69 ZIP and local PBE WADs."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from cdtb.export import TexConverter
from cdtb.wad import Wad
from PIL import Image
from xxhash import xxh64_intdigest


DESTINATION = Path(__file__).resolve().parents[1] / 'src/samira-testroom/mod/resources/gfx/mf'
HUD = 'assets/characters/missfortune/hud/'
PORTRAIT = HUD + 'missfortune_circle_69.skins_missfortune_skin69.tex'
ICON = HUD + 'icons2d/missfortune_{}.dds'
RUNE_PREFIX = 'assets/perks/styles/'
RUNE_PATHS = {
    'conqueror': 'precision/conqueror/conqueror.tex',
    'lethal_tempo': 'precision/lethaltempo/lethaltempotemp.tex',
    'electrocute': 'domination/electrocute/electrocute.tex',
    'press_the_attack': 'precision/presstheattack/presstheattack.tex',
    'arcane_comet': 'sorcery/arcanecomet/arcanecomet.tex',
    'first_strike': 'inspiration/firststrike/firststrike.tex',
}
CELL = 64


def load_art(abilities_path, wad_path):
    with ZipFile(abilities_path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        if manifest['skin_id'] != 21069:
            raise ValueError('Expected the Skin69 abilities archive')
        shipped = {}
        for path in (PORTRAIT, ICON.format('w')):
            data = archive.read(path)
            if sha256(data).hexdigest() != manifest['assets'][path]:
                raise ValueError(f'Unexpected Skin69 data for {path}')
            shipped[path] = data

    wad = Wad(str(wad_path), {})
    members = {entry.path_hash: entry for entry in wad.files}
    art = {'Portrait': TexConverter.tex_to_dds(shipped[PORTRAIT])}
    with wad_path.open('rb') as file:
        for key in 'qwer':
            path = ICON.format(key)
            entry = members[xxh64_intdigest(path.encode('ascii'))]
            data = entry.read_data(file)
            if data is None or len(data) != entry.size:
                raise ValueError(f'Could not read {path} from the local PBE WAD')
            if key == 'w' and data != shipped[path]:
                raise ValueError('The local W icon differs from the supplied Skin69 artwork')
            art[key.upper()] = data
    return art


def load_runes(wad_path):
    wad = Wad(str(wad_path), {})
    members = {entry.path_hash: entry for entry in wad.files}
    toc_entry = members[xxh64_intdigest(b'data/final/global.wad.subchunktoc')]
    art = {}
    with wad_path.open('rb') as file:
        toc = toc_entry.read_data(file)
        for name, relative_path in RUNE_PATHS.items():
            path = RUNE_PREFIX + relative_path
            entry = members[xxh64_intdigest(path.encode('ascii'))]
            data = entry.read_data(file, toc)
            if data is None or len(data) != entry.size:
                raise ValueError(f'Could not read {path} from the local PBE Global WAD')
            art[name] = TexConverter.tex_to_dds(data)
    return art


def build(art, destination):
    actor = ET.Element('AnimatedActor')
    ET.SubElement(actor, 'Info', CreatedBy='Samira in Isaac', Version='1', Fps='30')
    content = ET.SubElement(actor, 'Content')
    ET.SubElement(ET.SubElement(content, 'Spritesheets'), 'Spritesheet', Id='0', Path='hud_icons.png')
    ET.SubElement(ET.SubElement(content, 'Layers'), 'Layer', Id='0', Name='Icon', SpritesheetId='0')
    ET.SubElement(content, 'Nulls')
    ET.SubElement(content, 'Events')
    animations = ET.SubElement(actor, 'Animations', DefaultAnimation='Portrait')
    atlas = Image.new('RGBA', (CELL * len(art), CELL))
    frame = dict(XPosition='0', YPosition='0', XScale='100', YScale='100', Rotation='0',
                 RedTint='255', GreenTint='255', BlueTint='255', AlphaTint='255',
                 RedOffset='0', GreenOffset='0', BlueOffset='0', Delay='1', Visible='true', Interpolated='false')
    for index, (name, source) in enumerate(art.items()):
        x = index * CELL
        with Image.open(BytesIO(source)) as image:
            atlas.paste(image.convert('RGBA').resize((CELL, CELL), Image.Resampling.LANCZOS), (x, 0))
        animation = ET.SubElement(animations, 'Animation', Name=name, FrameNum='1', Loop='false')
        ET.SubElement(ET.SubElement(animation, 'RootAnimation'), 'Frame', **frame)
        layers = ET.SubElement(animation, 'LayerAnimations')
        layer = ET.SubElement(layers, 'LayerAnimation', LayerId='0', Visible='true')
        ET.SubElement(layer, 'Frame', **frame, XPivot='0', YPivot='0', XCrop=str(x), YCrop='0',
                      Width=str(CELL), Height=str(CELL))
        ET.SubElement(animation, 'NullAnimations')
        ET.SubElement(animation, 'Triggers')
    atlas.save(destination / 'hud_icons.png')
    ET.indent(actor, space='  ')
    ET.ElementTree(actor).write(destination / 'hud_icons.anm2', encoding='utf-8', xml_declaration=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--abilities', type=Path, required=True)
    parser.add_argument('--wad', type=Path, required=True, help='Local PBE MissFortune.wad.client')
    parser.add_argument('--global-wad', type=Path, required=True, help='Local PBE Global.wad.client')
    args = parser.parse_args()
    build(load_art(args.abilities, args.wad) | load_runes(args.global_wad), DESTINATION)
