"""Convert the three weapon effects referenced by Skin69 Recall_Real."""

import argparse
from io import BytesIO
import json
from pathlib import Path
from struct import pack_into, unpack_from
from zipfile import ZipFile

from PIL import Image

from build_miss_fortune_effects import DESTINATION, PARTICLES, SUFFIX, write_atlas
from build_miss_fortune_recall_effects import project_mesh
from build_miss_fortune_special_effects import WAD_SHA256
from build_miss_fortune_ultimate_effects import ZIP_SHA256, checked_source
from import_yone_assets import TexConverter, Wad, archive_hash, wad_hash


ATLAS = 'recall_props'
PROPS = {
    'RecallSpear': ('missfortune_skin69_emote_spear_avatar', 'a251a2b8', 'VFX_buffbone02', 9),
    'RecallArrow': ('missfortune_skin69_arrow', 'a77ceb02', 'VFX_buffbone03', 57),
    'RecallBalloon': ('missfortune_balloon', '7e9e4977', 'VFX_buffbone04', 103),
    'RecallWaterTrail': ('missfortune_skin69_watertrailloop', '7e9e4977', 'VFX_buffbone04', 103),
}
EXTRA_TEXTURE_HASHES = {
    'missfortune_skin69_emote_spear_avatar': '9ab70e9334976827b651c79bf92146559e916d4bb4f8d0ba11d52d03b98d289d',
    'missfortune_balloon': '481965d54f63cad1898d13e0b2700f00f39f6b802b22b629c1c967a36861a50c',
}


def balloon_faces(mesh):
    # The source SCB has a standard 100-byte face table followed by 3,624 bytes.
    if (unpack_from('<III', mesh, 140) != (202, 400, 5)
            or unpack_from('<I', mesh, 176) != (0,) or len(mesh) != 46240):
        raise ValueError('Unexpected Skin69 balloon SCB')
    geometry = bytearray(mesh[:42616])
    pack_into('<I', geometry, 148, 2)
    return bytes(geometry)


def build(abilities_zip, wad_path):
    if archive_hash(abilities_zip) != ZIP_SHA256 or archive_hash(wad_path) != WAD_SHA256:
        raise ValueError('Unexpected Skin69 Recall archives')
    members = {member.path_hash: member for member in Wad(wad_path, hashes={}).files}
    images, entries = {}, {}
    with ZipFile(abilities_zip) as archive, wad_path.open('rb') as stream:
        hashes = json.loads(archive.read('manifest.json'))['assets']
        for animation, (texture_name, key, bone, frame) in PROPS.items():
            path = f'{PARTICLES}{texture_name}{SUFFIX}tex'
            if texture_name in EXTRA_TEXTURE_HASHES:
                member = members.get(wad_hash(path))
                data = member.read_data(stream) if member else None
                source = checked_source(path, data, EXTRA_TEXTURE_HASHES[texture_name])
                source['archive'] = 'PBE MissFortune.wad.client'
            else:
                data = archive.read(path)
                source = checked_source(path, data, hashes[path])
                source['archive'] = 'MVP-T1-Miss-Fortune-Skin69-Abilities.zip'
            entry = {'event_key': key, 'attachment': bone, 'start_frame': frame, 'sources': [source]}
            with Image.open(BytesIO(TexConverter.tex_to_dds(data))) as decoded:
                image = decoded.convert('RGBA')
            mesh_name = {'RecallSpear': 'missfortune_skin69_emote_spear',
                         'RecallBalloon': 'missfortune_balloon'}.get(animation)
            if mesh_name:
                mesh_path = f'{PARTICLES}{mesh_name}{SUFFIX}scb'
                mesh = archive.read(mesh_path)
                mesh_source = checked_source(mesh_path, mesh, hashes[mesh_path])
                mesh_source['archive'] = 'MVP-T1-Miss-Fortune-Skin69-Abilities.zip'
                entry['sources'].append(mesh_source)
                yaw = -90 if animation == 'RecallSpear' else 90
                projected = balloon_faces(mesh) if animation == 'RecallBalloon' else mesh
                image, _ = project_mesh(projected, image, 'XY', yaw, 96)
                entry['projection_yaw_degrees'] = yaw
            bounds = image.getchannel('A').getbbox()
            if not bounds:
                raise ValueError(f'Empty Recall source {animation}')
            image = image.crop(bounds)
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            images[animation] = image
            entry['sprite_size'] = image.size
            entries[animation] = entry
    write_atlas(images, ATLAS, (512, 256), 'RecallSpear')
    (DESTINATION / f'{ATLAS}.provenance.json').write_text(json.dumps({
        'animation': 'Recall_Real', 'state': '5a81bdb0', 'fps': 30,
        'archives': {'MVP-T1-Miss-Fortune-Skin69-Abilities.zip': ZIP_SHA256,
                     'PBE MissFortune.wad.client': WAD_SHA256},
        'sprites': entries,
    }, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('abilities_zip', type=Path)
    parser.add_argument('wad', type=Path)
    args = parser.parse_args()
    build(args.abilities_zip, args.wad)
