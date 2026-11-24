"""Convert the original Skin69 Bullet Time projectiles and effects for Isaac."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PIL import Image

from build_miss_fortune_effects import DESTINATION, PARTICLES, SUFFIX, additive_to_rgba, bullet_image, write_atlas
from build_miss_fortune_special_effects import WAD_SHA256
from import_yone_assets import TexConverter, Wad, archive_hash, wad_hash


ATLAS = "ultimate_effects"
ZIP_SHA256 = "602f11876a05c99b310c9e5caa1b21ff19bb9d48cdc10ea6139ae0d5db877e24"
TRAIL_SHA256 = "e28aa38a0928bc1a1b0973600f1737dbdbe96ba6c07b7e6f8d2e658f88efe1dc"
SOURCES = {
    "RCone": ("missfortune_skin69_r_aoe_indicator_projection1", "35f92a49", "AOE_Indicator15"),
    "RBullet": ("missfortune_skin69_q_bullet01", "d2d2c9bc", "bullets"),
    "RTrail": ("missfortune_skin69_trail02", "d2d2c9bc", "ActualTrail"),
    "RMuzzle": ("missfortune_skin40_z_bullet02", "eba2d71b", "Muzzle_Add_Vert1"),
    "RImpact": ("missfortune_skin50_ba_flash_sharp_01", "6b7cadd7", "Basic3"),
}


def asset_path(stem, extension="tex"):
    return f"{PARTICLES}{stem}{SUFFIX}{extension}"


def checked_source(path, data, digest):
    if data is None or sha256(data).hexdigest() != digest:
        raise ValueError(f"Unexpected Skin69 source bytes for {path}")
    return {"path": path, "sha256": digest}


def build(abilities_zip, wad_path):
    if archive_hash(abilities_zip) != ZIP_SHA256 or archive_hash(wad_path) != WAD_SHA256:
        raise ValueError("Unexpected Skin69 source archive SHA-256")

    members = {member.path_hash: member for member in Wad(wad_path, hashes={}).files}
    images, sprite_metadata = {}, {}
    with ZipFile(abilities_zip) as archive, wad_path.open("rb") as stream:
        hashes = json.loads(archive.read("manifest.json"))["assets"]
        for animation, (stem, key, emitter) in SOURCES.items():
            path = asset_path(stem)
            if animation == "RTrail":
                member = members.get(wad_hash(path))
                data = member.read_data(stream) if member is not None else None
                source = checked_source(path, data, TRAIL_SHA256)
                source["archive"] = "PBE MissFortune.wad.client"
            else:
                data = archive.read(path)
                source = checked_source(path, data, hashes[path])
                source["archive"] = "MVP-T1-Miss-Fortune-Skin69-Abilities.zip"

            with Image.open(BytesIO(TexConverter.tex_to_dds(data))) as decoded:
                texture = decoded.convert("RGBA")
            metadata = {
                "sources": [source], "effect_key": key, "emitter": emitter,
                "source_texture_size": texture.size,
            }
            if animation == "RBullet":
                mesh_path = asset_path(stem, "scb")
                mesh = archive.read(mesh_path)
                mesh_source = checked_source(mesh_path, mesh, hashes[mesh_path])
                mesh_source["archive"] = source["archive"]
                metadata["sources"].append(mesh_source)
                metadata["transform"] = "Right-facing side projection of the shared R/Q/AA bullet mesh"
                image = bullet_image(mesh, texture)
            else:
                if animation == "RImpact":
                    texture = additive_to_rgba(texture)
                    metadata["transform"] = "Convert additive RGB to straight RGBA"
                bounds = texture.getchannel("A").getbbox()
                if bounds is None:
                    raise ValueError(f"Skin69 texture is fully transparent: {path}")
                metadata["crop_bounds"] = bounds
                image = texture.crop(bounds)
                if animation == "RCone":
                    image = image.transpose(Image.Transpose.ROTATE_270)
                    metadata["transform"] = "Rotate clockwise 90 degrees to open toward positive X"
                    metadata["authored_projector_scale_xyz"] = [420, 0, 880]
                elif animation == "RTrail":
                    metadata["transform"] = "Use the source horizontal ribbon UV strip"

            metadata["sprite_size"] = image.size
            metadata["pivot"] = [0 if animation == "RCone" else image.width // 2, image.height // 2]
            images[animation] = image
            sprite_metadata[animation] = metadata

    write_atlas(images, ATLAS, (1024, 768), "RBullet")
    animation_path = DESTINATION / f"{ATLAS}.anm2"
    tree = ET.parse(animation_path)
    cone_frame = tree.find("./Animations/Animation[@Name='RCone']/LayerAnimations/LayerAnimation/Frame")
    cone_frame.set("XPivot", "0")
    tree.write(animation_path, encoding="utf-8", xml_declaration=True)
    provenance = {
        "archives": {
            "MVP-T1-Miss-Fortune-Skin69-Abilities.zip": ZIP_SHA256,
            "PBE MissFortune.wad.client": WAD_SHA256,
        },
        "missile_effects": {
            "MissFortuneBulletTime": "285ccd33 -> MissFortune_Skin69_R_mis",
            "MissFortuneBullets": "285ccd33 -> MissFortune_Skin69_R_mis",
            "MissFortuneRShotExtra": "5c7810ca -> MissFortune_Skin69_Q_Mis",
            "MissFortune_Skin69_R_mis/Bullets": "d2d2c9bc -> MissFortune_Skin69_R_MisChild01",
        },
        "conversion": "CDTB TEX to DDS and Pillow to RGBA",
        "crop_format": "Source pixel bounds with exclusive right and bottom",
        "pivot_format": "Sprite-local pixels from top-left. RCone starts left-center and opens right.",
        "sprites": sprite_metadata,
    }
    (DESTINATION / f"{ATLAS}.provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("abilities_zip", type=Path)
    parser.add_argument("wad", type=Path, help="Local PBE MissFortune.wad.client")
    args = parser.parse_args()
    build(args.abilities_zip, args.wad)
