"""Bake source-backed Recall muzzle and balloon impact sprites."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops
from build_miss_fortune_effects import DESTINATION, additive_to_rgba, decode, write_atlas
from build_miss_fortune_joke_effects import EFFECTS_BIN, emitter_asset_paths, find_emitter
from build_miss_fortune_special_effects import WAD_SHA256
from build_miss_fortune_ultimate_effects import ZIP_SHA256, checked_source
from import_miss_fortune_assets import GRAPH_BIN, GRAPH_KEY, SKIN_BIN, load_skin_entries, read_skin_members
from import_yone_assets import archive_hash, read_bin

ATLAS = 'recall_bursts'
# event ID, frame, end, resource, attachment hashes
EVENTS = {
    0x22f715a2: (35, None, 0xef004200, (0x66d9d819, 0xa2879217)),
    0x9df6f669: (68, None, 0xf20046b9, (0xb7f08acc,)),
    0xffc387a5: (105, 126, 0x726a7806, (0xb7f08acc,)),
    0xfcc382ec: (110, 126, 0x726a7806, (0xbaf08f85,)),
    0x01f193ca: (105, 130, 0x6dd45aa5, (0x36396677,)),
    0x0e40a60a: (130, None, 0x87e8fe07, (0x36396677,)),
}
SOURCES = {
    'RecallMuzzle': (0xef004200, 'Muzzle_Add_Vert', (48, 64)),
    'RecallShotSpark': (0xef004200, 'Sparks_FORWARD', (48, 48)),
    'RecallBalloonHit': (0x6dd45aa5, 'CenterFlare1', (64, 64)),
    'RecallBalloonSplash': (0x87e8fe07, 'sparks4', (64, 64)),
    'RecallBalloonDroplet': (0x87e8fe07, 'sparks3', (48, 48)),
}

def build(abilities_zip, wad):
    if archive_hash(abilities_zip) != ZIP_SHA256 or archive_hash(wad) != WAD_SHA256:
        raise ValueError('Unexpected Skin69 source archive SHA-256')
    images, sprites = {}, {}
    with ZipFile(abilities_zip) as archive:
        manifest = json.loads(archive.read('manifest.json'))['assets']
        graph_bytes = archive.read(GRAPH_BIN)
        graph = read_bin(graph_bytes, GRAPH_KEY).getv('mClipDataMap')[0x5a81bdb0]
        graph_events = {k.h: v for k, v in graph.getv('mEventDataMap').items()}
        for event_id, (start, end, key, attachments) in EVENTS.items():
            event = graph_events[event_id]
            observed = (event.getv('mStartFrame', 0), event.getv('mEndFrame'),
                        event.getv('mEffectKey').h,
                        tuple(link.getv(0xeb880965).h for link in event.getv(0x60645d6a)))
            if observed != (start, end, key, attachments):
                raise ValueError(f'Unexpected Recall event {event_id:08x}: {observed}')
        resolver = load_skin_entries(archive.read(SKIN_BIN))[0x391ed45d].getv(0xd2f58721)
        effects = load_skin_entries(archive.read(EFFECTS_BIN))
        entries = {name: find_emitter(resolver, effects, key, (), emitter)
                   for name, (key, emitter, _) in SOURCES.items()}
        # All three gunshot variants must really share the two selected assets.
        for emitter_name in ('Muzzle_Add_Vert', 'Sparks_FORWARD'):
            paths = [emitter_asset_paths(find_emitter(resolver, effects, key, (), emitter_name)[0])
                     for key in (0xef004200, 0xf20046b9, 0x726a7806)]
            if len(set(paths)) != 1:
                raise ValueError('Gunshot textures differ between source effects')
        paths = {name: emitter_asset_paths(entry[0])[0] for name, entry in entries.items()}
        missing = sorted({path for path in paths.values() if path not in manifest})
        wad_sources = read_skin_members(wad, missing, graph_bytes) if missing else {}
        for name, (key, emitter_name, maximum) in SOURCES.items():
            emitter, chain = entries[name]
            path = paths[name]
            data = wad_sources[path] if path in wad_sources else archive.read(path)
            digest = sha256(data).hexdigest() if path in wad_sources else manifest[path]
            source = checked_source(path, data, digest)
            source['archive'] = 'PBE MissFortune.wad.client' if path in wad_sources else 'MVP-T1-Miss-Fortune-Skin69-Abilities.zip'
            texture = decode(data)
            source_size = texture.size
            columns, rows = map(int, emitter.getv(0x86a84509, (1, 1)))
            if texture.width % columns or texture.height % rows:
                raise ValueError(f'Invalid sheet for {name}')
            texture = texture.crop((0, 0, texture.width // columns, texture.height // rows))
            if texture.getchannel('A').getextrema() == (255, 255):
                texture = additive_to_rgba(texture)
            birth = emitter.getv('birthColor')
            rgba = birth.getv(0xb4b427aa) if birth else None
            if rgba:
                texture = ImageChops.multiply(texture, Image.new('RGBA', texture.size,
                                               tuple(round(c*255) for c in rgba)))
            bounds = texture.getchannel('A').getbbox()
            if not bounds:
                raise ValueError(f'Empty sprite: {name}')
            image = texture.crop(bounds)
            image.thumbnail(maximum, Image.Resampling.LANCZOS)
            images[name] = image
            lifetime = emitter.getv('particleLifetime')
            sprites[name] = {'sources': [source], 'effect_key': f'{key:08x}',
                'effect_chain': chain, 'emitter': emitter_name,
                'events': [f'{eid:08x}' for eid, (_, _, resource, _) in EVENTS.items()
                           if resource == key or (name in ('RecallMuzzle','RecallShotSpark') and resource in (0xf20046b9, 0x726a7806))],
                'particle_lifetime_seconds': lifetime.getv(0xb4b427aa) if lifetime else None,
                'birth_rgba': rgba, 'sheet_grid': [columns, rows], 'sheet_frame': 0,
                'source_texture_size': source_size, 'crop_bounds': bounds, 'sprite_size': image.size}
    write_atlas(images, ATLAS, (512, 256), 'RecallMuzzle')
    provenance = {'archives': {'MVP-T1-Miss-Fortune-Skin69-Abilities.zip': ZIP_SHA256,
                    'PBE MissFortune.wad.client': WAD_SHA256},
                  'animation': {'name':'Recall_Real','state':'5a81bdb0','fps':30},
                  'graph_sha256': sha256(graph_bytes).hexdigest(), 'sprites': sprites}
    (DESTINATION / f'{ATLAS}.provenance.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('abilities_zip', type=Path)
    parser.add_argument('wad', type=Path)
    args = parser.parse_args()
    build(args.abilities_zip, args.wad)
