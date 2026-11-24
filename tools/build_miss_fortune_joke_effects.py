"""Build representative sprites from the original Skin69 Joke VFX emitters."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops

from build_miss_fortune_effects import DESTINATION, write_atlas
from build_miss_fortune_recall_effects import project_mesh
from build_miss_fortune_special_effects import WAD_SHA256
from build_miss_fortune_ultimate_effects import ZIP_SHA256, additive_to_rgba, checked_source
from import_miss_fortune_assets import GRAPH_BIN, GRAPH_KEY, SKIN_BIN, load_skin_entries, read_skin_members
from import_yone_assets import TexConverter, archive_hash, read_bin


ATLAS = "joke_effects"
EFFECTS_BIN = (
    "data/characters/missfortune/missfortune_multi_skins_skin69_skins_skin70_"
    "skins_skin71_skins_skin72_skins_skin73_skins_skin74_skins_skin75.bin"
)
ARCHIVE_NAME = "MVP-T1-Miss-Fortune-Skin69-Abilities.zip"
WAD_NAME = "PBE MissFortune.wad.client"
ATTACHMENT = 0x96B05E9E
SOURCES = {
    "JokeIntroFlash": (0x9FDB4C4D, (), "Flash5", (48, 64)),
    "JokeIntroRing": (0x9FDB4C4D, (0x69603B42,), "Alaha", (84, 84)),
    "JokeSpamBeam": (0x686039AF, (0x19D52E01,), "skyBeam5", (36, 112)),
    "JokeSpamGold": (0x6760381C, (), "heal_spark", (36, 48)),
    "JokeLoopLogo": (0x66603689, (0x18D52C6E,), "Temp_GroundGlow_Constant", (112, 112)),
    "JokeLoopConfetti": (0x66603689, (0x1AD52F94,), "petals rain", (24, 24)),
    "JokeLoopBeam": (0x66603689, (0x1AD52F94,), "skyBeam3", (36, 112)),
}
CLIPS = {
    "Joke_In": (0xE5575908, {0x9FDB4C4D, 0x686039AF, 0x6760381C}),
    "Joke_Spam": (0x93F45FA2, {0x686039AF, 0x6760381C}),
    "Joke_Loop": (0xFD5D4579, {0x66603689}),
}


def animation_events(graph):
    events = {}
    clips = graph.getv("mClipDataMap")
    for name, (state, expected) in CLIPS.items():
        seen = set()
        for event_id, event in clips[state].getv("mEventDataMap").items():
            resource = event.getv(0xF6386280)
            if resource is None or resource.h not in expected:
                continue
            joints = tuple(link.getv(0xEB880965).h for link in event.getv(0x60645D6A))
            if joints != (ATTACHMENT,):
                raise ValueError(f"Unexpected attachment for {name} event {event_id}")
            seen.add(resource.h)
            events.setdefault(resource.h, []).append({
                "clip": name,
                "clip_state": f"{state:08x}",
                "event": f"{event_id.h:08x}",
                "start_frame": event.getv(0x250CFBE1, 0),
                "end_frame": event.getv(0xB725173E),
                "attachment_bone": "C_BUFFBONE_GLB_LAYOUT_LOC",
            })
        if seen != expected:
            raise ValueError(f"Unexpected particle events in {name}")
    return events


def find_emitter(resolver, effects, resource, children, name):
    effect = effects[resolver[resource].h]
    chain = [effect.getv(0xECF1C6BC)]
    for child in children:
        links = []
        for emitter in effect.getv(0x868EB76A):
            system = emitter.getv(0xA03664C8)
            if system:
                links.extend(item.getv(0x9B0300F3).h for item in system.getv(0x663F55E6))
        if child not in links:
            raise ValueError(f"Missing child {child:08x} for {chain[-1]}")
        effect = effects[resolver[child].h]
        chain.append(effect.getv(0xECF1C6BC))
    emitter = next(item for item in effect.getv(0x868EB76A) if item.getv(0x3D25B8CE) == name)
    return emitter, chain


def emitter_asset_paths(emitter):
    texture = emitter.getv(0x3C6468F4).lower()
    mesh_data = emitter.getv(0x007B14F6)
    resource = mesh_data.getv(0x0D89732D) if mesh_data else None
    mesh = resource.getv(0xD467E8C0).lower() if resource else None
    return texture, mesh


def build(abilities_zip, wad_path):
    if archive_hash(abilities_zip) != ZIP_SHA256 or archive_hash(wad_path) != WAD_SHA256:
        raise ValueError("Unexpected Skin69 source archive SHA-256")
    sprites, images = {}, {}
    with ZipFile(abilities_zip) as archive:
        manifest = json.loads(archive.read("manifest.json"))["assets"]
        graph_bytes = archive.read(GRAPH_BIN)
        graph = read_bin(graph_bytes, GRAPH_KEY)
        events = animation_events(graph)
        resolver = load_skin_entries(archive.read(SKIN_BIN))[0x391ED45D].getv(0xD2F58721)
        effects = load_skin_entries(archive.read(EFFECTS_BIN))
        emitters = {name: find_emitter(resolver, effects, resource, children, emitter)
                    for name, (resource, children, emitter, _) in SOURCES.items()}
        paths = {name: emitter_asset_paths(emitter) for name, (emitter, _) in emitters.items()}
        missing = sorted({path for pair in paths.values() for path in pair
                          if path and path not in manifest})
        wad_sources = read_skin_members(wad_path, missing, graph_bytes)
        for name, (resource, _, emitter_name, maximum_size) in SOURCES.items():
            emitter, chain = emitters[name]
            texture_path, mesh_path = paths[name]
            sources = []
            for path in filter(None, (texture_path, mesh_path)):
                data = wad_sources[path] if path in wad_sources else archive.read(path)
                digest = sha256(data).hexdigest() if path in wad_sources else manifest[path]
                source = checked_source(path, data, digest)
                source["archive"] = WAD_NAME if path in wad_sources else ARCHIVE_NAME
                sources.append((data, source))

            with Image.open(BytesIO(TexConverter.tex_to_dds(sources[0][0]))) as decoded:
                texture = decoded.convert("RGBA")
            source_size = texture.size
            columns, rows = map(int, emitter.getv(0x86A84509, (1, 1)))
            if texture.width % columns or texture.height % rows:
                raise ValueError(f"Invalid emitter sheet dimensions for {name}")
            texture = texture.crop((0, 0, texture.width // columns, texture.height // rows))
            if mesh_path:
                image, _ = project_mesh(sources[1][0], texture, "XZ", 0, 48)
            else:
                image = texture
                if image.getchannel("A").getextrema() == (255, 255):
                    image = additive_to_rgba(image)
            color = emitter.getv(0x83CDEAA1)
            tint = color.getv(0xB4B427AA) if color else None
            if tint:
                rgb = tuple(round(channel * 255) for channel in tint[:3])
                image = ImageChops.multiply(image, Image.new("RGBA", image.size, (*rgb, 255)))
            bounds = image.getchannel("A").getbbox()
            if bounds is None:
                raise ValueError(f"No visible pixels in {name}")
            image = image.crop(bounds)
            image.thumbnail(maximum_size, Image.Resampling.LANCZOS)
            images[name] = image

            lifetime = emitter.getv(0x2A552694)
            offset = emitter.getv(0x563D4A22)
            sprites[name] = {
                "sources": [source for _, source in sources],
                "effect_key": f"{resource:08x}",
                "effect_chain": chain,
                "emitter": emitter_name,
                "events": events[resource],
                "particle_lifetime_seconds": lifetime.getv(0xB4B427AA) if lifetime else None,
                "emitter_delay_seconds": emitter.getv(0x2431D42C),
                "emitter_offset": offset.getv(0xB4B427AA) if offset else None,
                "emitter_base_color": tint,
                "sheet_grid": [columns, rows],
                "sheet_frame": 0,
                "source_texture_size": source_size,
                "projection": "XZ, looking down onto the confetti mesh" if mesh_path else None,
                "crop_bounds": bounds,
                "sprite_size": image.size,
            }

    write_atlas(images, ATLAS, (512, 256), "JokeIntroFlash")
    provenance = {
        "archives": {ARCHIVE_NAME: ZIP_SHA256, WAD_NAME: WAD_SHA256},
        "graph_sha256": sha256(graph_bytes).hexdigest(),
        "effects_bin_sha256": manifest[EFFECTS_BIN],
        "conversion": "Representative sprites decoded from source TEX or projected from source SCB",
        "sprites": sprites,
    }
    (DESTINATION / f"{ATLAS}.provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("abilities_zip", type=Path)
    parser.add_argument("wad", type=Path)
    args = parser.parse_args()
    build(args.abilities_zip, args.wad)
