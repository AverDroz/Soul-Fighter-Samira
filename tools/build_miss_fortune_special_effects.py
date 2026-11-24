"""Import three original Skin69 particle textures from the verified PBE WAD."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from build_miss_fortune_effects import DESTINATION, PARTICLES, SUFFIX, write_atlas
from import_yone_assets import TexConverter, Wad, archive_hash, wad_hash


WAD_SHA256 = "ec155cda0e61f3cea58d2fb775746b0143d5c12b9d9da80b60618889f4b4d362"
SOURCES = {
    "HomeguardGlow": (
        "udyr_base_vgu_awaken_glow",
        "86f854b46438453832b37a304d0bd9c9e656ca74cf196ea9c0f31055f4d3baaa",
        "MissFortune_Skin69_Emote_Homeguard_Trail01", "glowFast",
        "C_BUFFBONE_GLB_CENTER_LOC", 0.5,
    ),
    "HomeguardTrail": (
        "missfortune_skin69_trail",
        "8782d2e0ee70ab90a7064c266c8598672502a4d16c75abed453557615a6b54ee",
        "MissFortune_Skin69_Emote_Homeguard_Trail01", "trail3",
        "C_BUFFBONE_GLB_CENTER_LOC", 0.6,
    ),
    "PentakillSignature": (
        "cassiopeia_skin38_cirlcle_01",
        "6ce600a5c83b9e3bc60659e2a6f5471d67c7e07557aa3790cfe11ef02871494a",
        "MissFortune_Skin69_Emote_Pentakill", "SignatureAdd",
        "C_BUFFBONE_GLB_LAYOUT_LOC", 2.0,
    ),
}


def build(wad_path):
    if archive_hash(wad_path) != WAD_SHA256:
        raise ValueError("Unexpected PBE MissFortune WAD SHA-256")
    members = {member.path_hash: member for member in Wad(wad_path, hashes={}).files}
    images = {}
    sprites = {}
    with wad_path.open("rb") as stream:
        for animation, source in SOURCES.items():
            stem, digest, effect, emitter, bone, lifetime = source
            path = f"{PARTICLES}{stem}{SUFFIX}tex"
            member = members.get(wad_hash(path))
            data = member.read_data(stream) if member is not None else None
            if data is None or sha256(data).hexdigest() != digest:
                raise ValueError(f"Unexpected Skin69 source bytes for {path}")

            with Image.open(BytesIO(TexConverter.tex_to_dds(data))) as decoded:
                image = decoded.convert("RGBA")
            bounds = image.getchannel("A").getbbox()
            if bounds is None:
                raise ValueError(f"Skin69 texture is fully transparent: {path}")
            crop = image.crop(bounds)
            images[animation] = crop
            sprites[animation] = {
                "texture": path,
                "sha256": digest,
                "texture_size": image.size,
                "crop_bounds": bounds,
                "pivot": [crop.width // 2, crop.height // 2],
                "effect": effect,
                "emitter": emitter,
                "attachment_bone": bone,
                "particle_lifetime_seconds": lifetime,
            }

    write_atlas(images, "special_effects", (512, 256), "HomeguardGlow")
    provenance = {
        "archive": "PBE MissFortune.wad.client",
        "archive_sha256": WAD_SHA256,
        "crop_format": "Left, top, right, bottom in source pixels, with exclusive right and bottom",
        "pivot_format": "Centered in each crop, measured from its top-left in pixels",
        "conversion": "CDTB TEX to DDS, decoded to RGBA with Pillow and cropped to nonzero alpha",
        "sprites": sprites,
    }
    (DESTINATION / "special_effects.provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wad", type=Path, help="Local PBE MissFortune.wad.client")
    build(parser.parse_args().wad)
