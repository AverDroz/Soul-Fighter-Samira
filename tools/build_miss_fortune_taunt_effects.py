"""Build representative T1 Miss Fortune taunt sprites from the supplied VFX."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from build_miss_fortune_effects import DESTINATION, additive_to_rgba, decode, tint, write_atlas
from build_miss_fortune_joke_effects import EFFECTS_BIN, emitter_asset_paths, find_emitter
from build_miss_fortune_recall_effects import project_mesh
from build_miss_fortune_special_effects import WAD_SHA256
from build_miss_fortune_ultimate_effects import ZIP_SHA256, checked_source
from import_miss_fortune_assets import GRAPH_BIN, GRAPH_KEY, SKIN_BIN, load_skin_entries, read_skin_members
from import_yone_assets import archive_hash, read_bin

ATLAS = 'taunt_effects'
STATE = 0x986D8FE5
# Resource, emitter, output bound, projection plane. These are representative
# source particles; runtime timing and positioning are adapted to Isaac.
SOURCES = {
    'TauntRing': (0x829B3A37, 'Arctic_Bands', (80, 80), 'XZ'),
    'TauntFeather': (0x829B3A37, 'Ascended_Feathers', (24, 24), 'XZ'),
    'TauntArrow': (0x6160FBC7, 'Arctic_Arrow', (48, 24), 'XZ'),
    'TauntBlast': (0x72A3A55F, 'blast', (72, 72), None),
}
TIMES = {0x829B3A37: 0, 0x6160FBC7: 15, 0x72A3A55F: 70}
WAD_NAME = 'PBE MissFortune.wad.client'


def build(abilities_zip, wad_path):
    if archive_hash(abilities_zip) != ZIP_SHA256 or archive_hash(wad_path) != WAD_SHA256:
        raise ValueError('Unexpected Skin69 source archive SHA-256')
    art, provenance = {}, {}
    with ZipFile(abilities_zip) as archive:
        hashes = json.loads(archive.read('manifest.json'))['assets']
        graph_bytes = archive.read(GRAPH_BIN)
        graph = read_bin(graph_bytes, GRAPH_KEY)
        events = {}
        for event_id, event in graph.getv('mClipDataMap')[STATE].getv('mEventDataMap').items():
            resource = event.getv(0xF6386280)
            if resource is not None and resource.h in TIMES:
                frame = event.getv(0x250CFBE1, 0)
                if frame != TIMES[resource.h]:
                    raise ValueError('Unexpected taunt event frame')
                events[resource.h] = {'event': f'{event_id.h:08x}', 'start_frame': frame,
                                      'attachment': [f'{link.getv(0xEB880965).h:08x}'
                                                     for link in event.getv(0x60645D6A)]}
        if set(events) != set(TIMES):
            raise ValueError('Missing expected taunt event')
        resolver = load_skin_entries(archive.read(SKIN_BIN))[0x391ED45D].getv(0xD2F58721)
        effects = load_skin_entries(archive.read(EFFECTS_BIN))
        emitters = {name: find_emitter(resolver, effects, resource, (), emitter)
                    for name, (resource, emitter, _, _) in SOURCES.items()}
        paths = {name: emitter_asset_paths(emitter) for name, (emitter, _) in emitters.items()}
        missing = sorted({path for pair in paths.values() for path in pair if path and path not in hashes})
        wad_sources = read_skin_members(wad_path, missing, graph_bytes) if missing else {}
        for name, (resource, emitter_name, maximum, plane) in SOURCES.items():
            emitter, chain = emitters[name]
            texture_path, mesh_path = paths[name]
            sources, data = [], []
            for path in filter(None, (texture_path, mesh_path)):
                member = wad_sources[path] if path in wad_sources else archive.read(path)
                digest = sha256(member).hexdigest() if path in wad_sources else hashes[path]
                record = checked_source(path, member, digest)
                record['archive'] = WAD_NAME if path in wad_sources else abilities_zip.name
                sources.append(record)
                data.append(member)
            image = decode(data[0])
            grid = tuple(map(int, emitter.getv(0x86A84509, (1, 1))))
            if image.width % grid[0] or image.height % grid[1]:
                raise ValueError(f'Invalid texture grid: {name}')
            image = image.crop((0, 0, image.width // grid[0], image.height // grid[1]))
            if mesh_path:
                image, _ = project_mesh(data[1], image, plane, 0, 48)
            elif image.getchannel('A').getextrema() == (255, 255):
                image = additive_to_rgba(image)
            birth = emitter.getv(0x83CDEAA1)
            rgba = birth.getv(0xB4B427AA) if birth else None
            if rgba:
                image = tint(image, (*rgba[:3], 1))
            bounds = image.getchannel('A').getbbox()
            if not bounds:
                raise ValueError(f'No visible source pixels: {name}')
            image = image.crop(bounds)
            image.thumbnail(maximum, Image.Resampling.LANCZOS)
            if not image.getchannel('A').getbbox():
                raise ValueError(f'Empty final sprite: {name}')
            art[name] = image
            lifetime = emitter.getv(0x2A552694)
            provenance[name] = {'sources': sources, 'effect_key': f'{resource:08x}',
                                'effect_chain': chain, 'emitter': emitter_name,
                                'event': events[resource], 'sprite_size': image.size,
                                'particle_lifetime_seconds': lifetime.getv(0xB4B427AA) if lifetime else None,
                                'birth_rgba': rgba, 'sheet_grid': grid, 'projection': plane}
    write_atlas(art, ATLAS, (256, 256), 'TauntRing')
    (DESTINATION / f'{ATLAS}.provenance.json').write_text(json.dumps({
        'archives': {abilities_zip.name: ZIP_SHA256, WAD_NAME: WAD_SHA256},
        'graph_sha256': sha256(graph_bytes).hexdigest(), 'effects_bin_sha256': hashes[EFFECTS_BIN],
        'clip_state': f'{STATE:08x}', 'conversion': 'Representative source TEX and projected SCB; placement adapted to Isaac.',
        'sprites': provenance,
    }, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('abilities_zip', type=Path)
    parser.add_argument('wad', type=Path)
    args = parser.parse_args()
    build(args.abilities_zip, args.wad)
