"""Rebuild the Skin69 GLB in a fresh work directory using HeroStudio 0.2.33."""
import argparse
import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from cdtb import binfile
from cdtb.export import TexConverter
from PIL import Image
from xxhash import xxh64_intdigest

HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def verified_member(archive, name, hashes):
    data = archive.read(name)
    if hashlib.sha256(data).hexdigest() != hashes.get(name.lower()):
        raise ValueError(f"Unexpected source bytes for {name}")
    return data


def build(work, studio_app):
    if work.exists() and any(work.iterdir()):
        raise ValueError("Choose an empty output directory")
    sys.path.insert(0, str(studio_app.resolve()))
    from client_model import convert

    manifest = json.loads((HERE / "source-manifest.json").read_bytes())
    with ZipFile(HERE / "source/Skin69-abilities.zip") as source:
        for name in manifest["assets"]:
            data = verified_member(source, name, manifest["assets"])
            if name.endswith((".anm", ".skn", ".skl")):
                dest = work / "assets/client" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            elif name.endswith(".tex"):
                dest = (work / "assets/decoded" / name).with_suffix(".png")
                dest.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(BytesIO(TexConverter.tex_to_dds(data))) as texture:
                    texture.save(dest)

        # Resolve only the model fields read by HeroStudio. Other hashes retain their IDs.
        for table in (binfile.hashfile_binentries, binfile.hashfile_binhashes,
                      binfile.hashfile_binfields, binfile.hashfile_bintypes, binfile.hashfile_binpaths):
            table.hashes = {}
        fields = ("skinMeshProperties simpleSkin skeleton texture initialSubmeshToHide materialOverride "
                  "submesh Material samplerValues TextureName texturePath skinAnimationProperties animationGraphData")
        for name in fields.split():
            binfile.hashfile_binfields.hashes[binfile.compute_binhash(name)] = name
        for name in ("Characters/MissFortune/Skins/Skin69", "Characters/MissFortune/Animations/Skin69"):
            binfile.hashfile_binentries.hashes[binfile.compute_binhash(name)] = name
        for name in manifest["assets"]:
            binfile.hashfile_binpaths.hashes[xxh64_intdigest(name.encode())] = name
        for name in manifest["roots"][:2]:
            objects = binfile.BinFile(BytesIO(source.read(name))).to_serializable()
            objects.pop("__linked", None)
            write_json((work / "assets/decoded" / name).with_suffix(".json"), {"objects": objects})

    supplement = json.loads((HERE / "source/supplement-checksums.json").read_bytes())
    with ZipFile(HERE / "source/skin69-supplement.zip") as archive:
        for name in supplement:
            dest = work / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(verified_member(archive, name, supplement))
    profile = {"client_import": {"champion": "missfortune", "skin_id": 69}}
    model = work / convert(work, profile)
    report = json.loads((model.parent / "conversion.json").read_bytes())
    if report["failures"] or report["animations"] != 52:
        raise ValueError(f"Incomplete conversion: {report['animations']} clips, {report['failures']}")
    write_json(work / "profile.json", profile)
    print(model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--studio-app", required=True, type=Path)
    args = parser.parse_args()
    build(args.work.resolve(), args.studio_app)
