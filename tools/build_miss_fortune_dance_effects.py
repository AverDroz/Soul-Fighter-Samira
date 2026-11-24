"""Convert the active Skin69 Dance particle emitters to sprites for Isaac."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageChops

from build_miss_fortune_effects import DESTINATION, additive_to_rgba, decode, tint, write_atlas
from build_miss_fortune_joke_effects import EFFECTS_BIN, emitter_asset_paths, find_emitter
from build_miss_fortune_recall_effects import project_mesh
from build_miss_fortune_ultimate_effects import ZIP_SHA256, checked_source
from import_miss_fortune_assets import GRAPH_BIN, GRAPH_KEY, SKIN_BIN, load_skin_entries
from import_yone_assets import archive_hash, read_bin

ATLAS = "dance_effects"
STATE = 0xF815289C
ROOT_EFFECT = 0xC7C11035
SOURCES = {
    "DanceLogoGold": (0x2636A78F, "Temp_GroundGlow_Constant9", (112, 52)),
    "DanceLogoRed": (0x2636A78F, "Temp_GroundGlow_Constant11", (112, 52)),
    "DanceHalo": (0xDCDC0BAA, "heal_spark", (80, 80)),
    "DanceFlash": (0x2436A469, "Flash2", (48, 48)),
    "DanceFeather": (0x2536A5FC, "Ascended_Feathers", (24, 24)),
    "DanceSpark": (0x2636A78F, "lotus_leaves", (32, 32)),
}


def build(path):
    if archive_hash(path) != ZIP_SHA256:
        raise ValueError("Unexpected Skin69 ability archive")
    art, provenance = {}, {}
    with ZipFile(path) as archive:
        hashes = json.loads(archive.read("manifest.json"))["assets"]
        graph_bytes = archive.read(GRAPH_BIN)
        graph = read_bin(graph_bytes, GRAPH_KEY)
        group = graph.getv("mClipDataMap")[STATE]
        events = group.getv("mEventDataMap")
        cue = next(event for event in events.values()
                   if event.getv(0xF6386280) and event.getv(0xF6386280).h == ROOT_EFFECT)
        first = cue.getv(0x250CFBE1, 0)
        attachment = [link.getv(0xEB880965).h for link in cue.getv(0x60645D6A)]
        children = [link.h for link in group.getv(0x078CAFD9)]
        if first != 0 or attachment != [0x96B05E9E] or children != [0x981CAAD3, 0x589C6CA2]:
            raise ValueError("Unexpected Dance clip group")

        resolver = load_skin_entries(archive.read(SKIN_BIN))[0x391ED45D].getv(0xD2F58721)
        effects = load_skin_entries(archive.read(EFFECTS_BIN))
        for name, (child, emitter_name, maximum_size) in SOURCES.items():
            emitter, chain = find_emitter(resolver, effects, ROOT_EFFECT, (child,), emitter_name)
            sources, data = [], []
            for asset in filter(None, emitter_asset_paths(emitter)):
                member = archive.read(asset)
                sources.append(checked_source(asset, member, hashes[asset]))
                data.append(member)
            image = decode(data[0])
            columns, rows = map(int, emitter.getv(0x86A84509, (1, 1)))
            if image.width % columns or image.height % rows:
                raise ValueError(f"Invalid Dance tile grid for {name}")
            image = image.crop((0, 0, image.width // columns, image.height // rows))
            if len(data) == 2:
                image, _ = project_mesh(data[1], image, "XZ", 0, 48)
            elif image.getchannel("A").getextrema() == (255, 255):
                image = additive_to_rgba(image)
            birth = emitter.getv("birthColor")
            birth_rgba = birth.getv(0xB4B427AA) if birth else None
            if birth_rgba:
                image = tint(image, (*birth_rgba[:3], 1))
            if not image.getchannel("A").getbbox():
                raise ValueError(f"No visible source pixels for {name}")
            art[name] = image
            lifetime = emitter.getv("particleLifetime")
            color_curve = emitter.getv("color")
            curve = color_curve.getv(0xBC037DE7) if color_curve else None
            provenance[name] = {
                "sources": sources, "effect_chain": chain, "resource": f"{child:08x}",
                "emitter": emitter_name, "birth_rgba": birth_rgba,
                "particle_lifetime_seconds": lifetime.getv(0xB4B427AA) if lifetime else None,
                "alpha_curve": list(zip(curve.getv(0x5D68EEB5), (item[3] for item in curve.getv(0x34474C3B))))
                if curve else None,
                "sheet_grid": [columns, rows],
            }
            if not name.startswith("DanceLogo"):
                art[name] = image.crop(image.getchannel("A").getbbox())
                art[name].thumbnail(maximum_size, Image.Resampling.LANCZOS)

    gold, red = art["DanceLogoGold"], art["DanceLogoRed"]
    if gold.size != red.size:
        raise ValueError("Dance logo layers must share their projection")
    crop = ImageChops.lighter(gold.getchannel("A"), red.getchannel("A")).getbbox()
    for name in ("DanceLogoGold", "DanceLogoRed"):
        art[name] = art[name].crop(crop).resize(SOURCES[name][2], Image.Resampling.LANCZOS)
    for name, image in art.items():
        provenance[name]["sprite_size"] = image.size
    write_atlas(art, ATLAS, (320, 192), "DanceLogoGold")
    metadata = {
        "archive": path.name, "sha256": ZIP_SHA256, "graph_sha256": sha256(graph_bytes).hexdigest(),
        "clip_group": f"{STATE:08x}", "clips": ["Dance_In", "Dance"], "start_frame": first,
        "attachment": "C_BUFFBONE_GLB_LAYOUT_LOC",
        "conversion": "Original TEX and feather SCB with source tint. Particle layout adapted to Isaac.",
        "sprites": provenance,
    }
    (DESTINATION / f"{ATLAS}.provenance.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("abilities_zip", type=Path)
    build(parser.parse_args().abilities_zip)
