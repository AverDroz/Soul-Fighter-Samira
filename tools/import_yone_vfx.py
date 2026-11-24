"""Decode the supplied classic Yone archive textures for the local companion."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from cdtb.export import TexConverter
from PIL import Image


DESTINATION = Path(__file__).resolve().parents[1] / "assets/yone-local/vfx"
PARTICLES = "assets/characters/yone/skins/base/particles/"
TEXTURES = {
    "q_slash": ("yone_base_slash_horizontal.tex", False, False),
    "q3_wind": ("yone_base_wind_horizontal.tex", False, False),
    "w_sweep": ("yone_base_w_groundswipe_01.tex", True, True),
    "w_shield": ("yone_base_w_shield.tex", False, False),
    "e_flash": ("yone_base_e_dash_sub.tex", False, False),
    "e_mark": ("yone_base_e_mark.tex", False, False),
    "e_timer": ("yone_base_e_timer_sumi-e.tex", False, False),
    "r_ground": ("yone_base_r_ground.tex", True, False),
}


def convert(archive, output):
    with ZipFile(archive) as source:
        inventory = json.loads(source.read("manifest.json"))["files"]
        images = {}
        manifest = {"source": archive.name, "copyright": "Riot Games", "files": {}}
        for name, (filename, rotate, tint_mask) in TEXTURES.items():
            member = PARTICLES + filename
            data = source.read(member)
            digest = sha256(data).hexdigest()
            if digest != inventory[member]:
                raise ValueError(f"Archive checksum mismatch for {member}")
            with Image.open(BytesIO(TexConverter.tex_to_dds(data))) as decoded:
                image = decoded.convert("RGBA")
            if rotate:
                image = image.transpose(Image.Transpose.ROTATE_270)
            if tint_mask:
                mask = Image.new("RGBA", image.size, "white")
                mask.putalpha(image.getchannel("A"))
                image = mask
            png = BytesIO()
            image.save(png, format="PNG", optimize=True)
            name += ".png"
            images[name] = png.getvalue()
            manifest["files"][name] = {
                "member": member,
                "sourceSha256": digest,
                "pngSha256": sha256(images[name]).hexdigest(),
                "clockwiseRotation": 90 if rotate else 0,
                "alphaMask": tint_mask,
            }
    output.mkdir(parents=True, exist_ok=True)
    for name, image in images.items():
        (output / name).write_bytes(image)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=DESTINATION)
    args = parser.parse_args()
    convert(args.archive, args.output)
