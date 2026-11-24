"""Build Isaac's Strut sprites from the original Skin69 Gun2025 effects."""

import argparse
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from build_miss_fortune_effects import DESTINATION, TexConverter, write_atlas
from build_miss_fortune_ultimate_effects import (
    ZIP_SHA256, additive_to_rgba, asset_path, checked_source,
)
from import_yone_assets import archive_hash


ATLAS = "strut_effects"
ARCHIVE = "MVP-T1-Miss-Fortune-Skin69-Abilities.zip"
GEAR_BIN = (
    "data/characters/missfortune/missfortune_multi_skins_skin69_skins_skin70_"
    "skins_skin71_skins_skin72_skins_skin73_skins_skin74_skins_skin75.bin"
)
GROUND = "MissFortune_Skin69_W_Max00 (7f0ed6f7)"
GUNS = "MissFortune_Skin69_W_Buf_RWeapon00 (f6610439), LWeapon00 (ce40f9f3)"

# These emitters sample a single texture or a scrolling ribbon without a flipbook.
# Representative tint and peak opacity are recorded for the caller's lifetime curve.
SPRITES = {
    "Feather": ("missfortune_skin69_feather01", GROUND, "Ascended_Feathers",
                (0.92, 0.72, 0.40, 0.60), (38, 44), "Project feather texture as a camera-facing sprite"),
    "GroundWisp": ("zoe_skin20_wisps_white_01", GROUND, "Trail5",
                   (0.953, 0.717, 0.238, 0.70), (128, 64), "Horizontal source strip. Flatten Y at render time"),
    "GunTrail": ("missfortune_skin69_trail", GUNS, "Trail1 / Trail2",
                 (0.932, 0.654, 0.260, 0.60), (128, 32), "Horizontal source strip. Flatten Y at render time"),
    "GunSpark": ("missfortune_skin50_ba_flash_sharp_01", GUNS, "Basic",
                 (0.718, 0.046, 0.0, 0.502), (32, 32), "Convert additive RGB to straight RGBA"),
    "Activation": ("missfortune_base_clone_glow", GROUND, "Flash_Glow_CameraFace",
                   (0.864, 0.126, 0.184, 0.60), (48, 48), "Place near the torso. Fade in and out over 0.8 seconds"),
}


def build(abilities_zip):
    if archive_hash(abilities_zip) != ZIP_SHA256:
        raise ValueError("Unexpected Skin69 abilities ZIP SHA-256")
    sprites, metadata = {}, {}
    with ZipFile(abilities_zip) as archive:
        hashes = json.loads(archive.read("manifest.json"))["assets"]
        gear = checked_source(GEAR_BIN, archive.read(GEAR_BIN), hashes[GEAR_BIN])
        for animation, (stem, effect, emitter, tint, size, transform) in SPRITES.items():
            path = asset_path(stem)
            data = archive.read(path)
            source = checked_source(path, data, hashes[path])
            with Image.open(BytesIO(TexConverter.tex_to_dds(data))) as decoded:
                image = decoded.convert("RGBA")
            source_size = image.size
            if animation == "GunSpark":
                image = additive_to_rgba(image)
            bounds = image.getchannel("A").getbbox()
            if bounds is None:
                raise ValueError(f"Skin69 texture is fully transparent: {path}")
            sprites[animation] = image.crop(bounds).resize(size, Image.Resampling.LANCZOS)
            metadata[animation] = {
                "source": source,
                "effect": effect,
                "emitter": emitter,
                "source_texture_size": source_size,
                "crop_bounds": bounds,
                "sprite_size": size,
                "pivot": [size[0] // 2, size[1] // 2],
                "runtime_tint_and_peak_alpha": tint,
                "transform": transform,
            }

    write_atlas(sprites, ATLAS, (256, 128), "Feather")
    provenance = {
        "archive": ARCHIVE,
        "archive_sha256": ZIP_SHA256,
        "gun2025_effect_definitions": gear,
        "conversion": "CDTB TEX to DDS and Pillow to RGBA, alpha crop and resize",
        "crop_format": "Source pixel bounds with exclusive right and bottom",
        "pivot_format": "Sprite-local pixels from top-left",
        "sprites": metadata,
    }
    (DESTINATION / f"{ATLAS}.provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("abilities_zip", type=Path)
    build(parser.parse_args().abilities_zip)
