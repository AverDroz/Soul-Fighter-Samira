"""Bake native Isaac shop sprites from the two supplied League asset archives."""

import argparse
from contextlib import ExitStack
from io import BytesIO
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import moderngl
import numpy as np
from PIL import Image, ImageChops

from import_miss_fortune_assets import Glb
from import_yone_assets import archive_hash, load_converter, read_bin, write_json


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src/samira-testroom/mod/resources/gfx/league_shop"
sys.path.insert(0, str(ROOT / "src/samira/external"))
from model import GPURenderer, Model


SHOPKEEPERS = {
    "south": ("sru_storekeeper_idle_normal1", 0),
    "north": ("sru_storekeepernorth_idle1", 0),
}
FRAME = 96
FPS = 30
ATLAS = "png/assets/ux/itemshop/itemshop_texture_atlas.png"
HUD_ICON = "png/assets/ux/lol/itemshophud-default.png"
UI_PARTS = {
    "Panel": (ATLAS, (110, 340, 770, 860), (320, 252)),
    "Coin": (ATLAS, (1, 1, 35, 31), (16, 15)),
    "Shop": (HUD_ICON, (0, 0, 32, 32), (18, 18)),
}


def attributes(**values):
    return {name: str(value) for name, value in values.items()}


def write_actor(path, animations):
    actor = ET.Element("AnimatedActor")
    ET.SubElement(actor, "Info", attributes(Version=1, Fps=FPS))
    content = ET.SubElement(actor, "Content")
    sheets = ET.SubElement(content, "Spritesheets")
    ET.SubElement(sheets, "Spritesheet", attributes(Path=path.with_suffix(".png").name, Id=0))
    layers = ET.SubElement(content, "Layers")
    ET.SubElement(layers, "Layer", attributes(Name="Sprite", Id=0, SpritesheetId=0))
    ET.SubElement(content, "Nulls")
    ET.SubElement(content, "Events")
    clips = ET.SubElement(actor, "Animations", DefaultAnimation=next(iter(animations)))
    frame_props = attributes(
        XPosition=0, YPosition=0, XScale=100, YScale=100, Visible="true",
        RedTint=255, GreenTint=255, BlueTint=255, AlphaTint=255,
        RedOffset=0, GreenOffset=0, BlueOffset=0, Rotation=0, Interpolated="false",
    )
    for name, (loop, frames) in animations.items():
        duration = sum(frame[-1] for frame in frames)
        clip = ET.SubElement(clips, "Animation", attributes(
            Name=name, FrameNum=duration, Loop=str(loop).lower(),
        ))
        root = ET.SubElement(clip, "RootAnimation")
        ET.SubElement(root, "Frame", frame_props, Delay=str(duration))
        layers = ET.SubElement(clip, "LayerAnimations")
        layer = ET.SubElement(layers, "LayerAnimation", LayerId="0", Visible="true")
        for x, y, w, h, px, py, delay in frames:
            ET.SubElement(layer, "Frame", frame_props, **attributes(
                Delay=delay, XCrop=x, YCrop=y, Width=w, Height=h, XPivot=px, YPivot=py,
            ))
        ET.SubElement(clip, "NullAnimations")
        ET.SubElement(clip, "Triggers")
    ET.indent(actor, space="    ")
    ET.ElementTree(actor).write(path, encoding="utf-8", xml_declaration=True)


def copy_member(archive, name, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(archive.read(name))


def convert_keeper(archive, project, convert, side, clip):
    champion = "sru_storekeeper" + side
    key = f"characters/{champion}/skins/skin0"
    skin_bin = f"data/{key}.bin"
    record = read_bin(archive.read(skin_bin), key)
    skin = record.getv("skinMeshProperties")
    properties = {field: str(skin.getv(field)).lower() for field in ("simpleSkin", "skeleton", "texture")}
    if skin.getv("initialSubmeshToHide") or skin.getv("materialOverride"):
        raise ValueError(f"Skin {key} has unsupported material overrides")
    base = Path(properties["simpleSkin"]).parent.as_posix()
    animation = f"{base}/animations/{clip}.anm"
    texture = str(Path(properties["texture"]).with_suffix(".png").as_posix())
    for name in (properties["simpleSkin"], properties["skeleton"], animation):
        copy_member(archive, name, project / "assets/client" / name)
    copy_member(archive, f"png/{texture}", project / "assets/decoded" / texture)
    write_json(project / "assets/decoded" / f"data/{key}.json", {
        "objects": {key: {"skinMeshProperties": properties}},
    })
    glb_path = project / convert(project, {"client_import": {"champion": champion, "skin_id": 0}})
    glb = Glb(glb_path)
    selected = next(item for item in glb.document["animations"] if item["name"] == clip)
    selected["name"] = "idle"
    glb.save(glb_path)
    return Model(glb_path, hero="shopkeeper"), {
        "skin": skin_bin, "mesh": properties["simpleSkin"], "skeleton": properties["skeleton"],
        "texture": f"png/{texture}", "animation": animation,
    }


def render_sprite(context, framebuffer, renderer, angle, phase, origin):
    framebuffer.use()
    framebuffer.clear(0, 0, 0, 0)
    renderer.draw("idle", phase, origin, framebuffer.size, math.radians(angle), .1, detached=True)
    if context.error != "GL_NO_ERROR":
        raise RuntimeError("Could not render the original shopkeeper model")
    width, height = framebuffer.size
    data = np.frombuffer(framebuffer.read(components=4), np.uint8).reshape(height, width, 4)[::-1].copy()
    alpha = data[:, :, 3:4].astype(np.float32)
    data[:, :, :3] = np.clip(data[:, :, :3].astype(np.float32) * 255 / np.maximum(alpha, 1), 0, 255)
    return Image.fromarray(data, "RGBA")


def bake_keeper(context, model, angle, path, preview):
    size = FRAME * 4, FRAME * 4
    with ExitStack() as stack:
        color = context.texture(size, 4)
        stack.callback(color.release)
        depth = context.depth_renderbuffer(size)
        stack.callback(depth.release)
        framebuffer = context.framebuffer([color], depth)
        stack.callback(framebuffer.release)
        renderer = GPURenderer(context, model)
        try:
            renderer.view = math.cos(math.radians(35)), math.sin(math.radians(35))
            model.pixel_scale = .25
            probe_origin = (size[0] // 2, size[1] // 2)
            if preview:
                from PIL import ImageDraw

                sheet = Image.new("RGBA", (FRAME * 8, FRAME), "#39322e")
                draw = ImageDraw.Draw(sheet)
                for i in range(8):
                    probe = render_sprite(context, framebuffer, renderer, i * 45, .25, probe_origin)
                    tile = probe.crop(probe.getbbox())
                    tile.thumbnail((FRAME - 4, FRAME - 18))
                    sheet.alpha_composite(tile, (i * FRAME + (FRAME - tile.width) // 2, 2))
                    draw.text((i * FRAME + 4, FRAME - 14), str(i * 45))
                sheet.save(preview)
            count = max(2, round(model.durations["idle"] * FPS))
            poses = [(frame, min(3, count - frame)) for frame in range(0, count, 3)]
            box = None
            for frame, _ in poses:
                probe = render_sprite(context, framebuffer, renderer, angle, frame / count, probe_origin)
                bounds = probe.getbbox()
                if bounds is None or 0 in bounds[:2] or any(a == b for a, b in zip(bounds[2:], size)):
                    raise ValueError("Shopkeeper pose falls outside the capture viewport")
                if box is None:
                    box = bounds
                else:
                    box = (*map(min, box[:2], bounds[:2]), *map(max, box[2:], bounds[2:]))
            left, top, right, bottom = box
            scale = min(82 / (right - left), 78 / (bottom - top))
            model.pixel_scale *= scale
            # Establish an invariant ground anchor using the union of idle poses.
            pivot = FRAME // 2, FRAME - 4
            origin = ((pivot[0] - ((left + right) / 2 - probe_origin[0]) * scale) * 4,
                      (pivot[1] - (bottom - probe_origin[1]) * scale) * 4)
            model.pixel_scale *= 4
            sheet = Image.new("RGBA", (FRAME * 8, FRAME * math.ceil(len(poses) / 8)))
            frames = []
            for i, (frame, delay) in enumerate(poses):
                sprite = render_sprite(context, framebuffer, renderer, angle, frame / count, origin)
                sprite = sprite.resize((FRAME, FRAME), Image.Resampling.LANCZOS)
                if not sprite.getbbox():
                    raise ValueError("Shopkeeper baked to an empty sprite")
                x, y = i % 8 * FRAME, i // 8 * FRAME
                sheet.paste(sprite, (x, y))
                frames.append((x, y, FRAME, FRAME, *pivot, delay))
            if not ImageChops.difference(sheet.crop((0, 0, FRAME, FRAME)),
                                         sheet.crop((FRAME, 0, FRAME * 2, FRAME))).getbbox(alpha_only=False):
                raise ValueError("Shopkeeper idle frames are identical")
        finally:
            renderer.close()
    sheet.save(path.with_suffix(".png"))
    write_actor(path, {"Idle": (True, frames)})
    return {"frame_count": len(frames), "duration_ticks": count, "yaw_degrees": angle,
            "frame_size": [FRAME, FRAME], "ground_pivot": list(pivot)}


def bake_ui(archive, path):
    sheet = Image.new("RGBA", (320, 272))
    animations = {}
    placements = {"Panel": (0, 0), "Coin": (0, 254), "Shop": (18, 254)}
    for name, (source, crop, size) in UI_PARTS.items():
        with Image.open(BytesIO(archive.read(source))) as image:
            tile = image.convert("RGBA").crop(crop).resize(size, Image.Resampling.LANCZOS)
        x, y = placements[name]
        w, h = size
        sheet.paste(tile, (x, y))
        animations[name] = (False, [(x, y, w, h, w // 2, h // 2, 1)])
    sheet.save(path.with_suffix(".png"))
    write_actor(path, animations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shopkeepers", type=Path, required=True)
    parser.add_argument("--visuals", type=Path, required=True)
    parser.add_argument("--herostudio-archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=DEST)
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()
    provenance = {
        "archives": {item.name: archive_hash(item) for item in
                     (args.shopkeepers, args.visuals, args.herostudio_archive)},
        "shopkeepers": {},
        "UI": {name: {"source": source, "crop": crop, "size": size}
               for name, (source, crop, size) in UI_PARTS.items()},
    }
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="league-shop-", dir=ROOT.parent) as temporary:
        work = Path(temporary)
        convert = load_converter(work, args.herostudio_archive)
        staged = work / "shop"
        staged.mkdir()
        with ZipFile(args.shopkeepers) as shopkeepers:
            with moderngl.create_standalone_context(require=330) as context:
                for side, (clip, angle) in SHOPKEEPERS.items():
                    model, source = convert_keeper(shopkeepers, work / side, convert, side, clip)
                    preview = args.preview_dir / f"{side}-angles.png" if args.preview_dir else None
                    timing = bake_keeper(context, model, angle, staged / f"shopkeeper_{side}.anm2", preview)
                    provenance["shopkeepers"][side] = {**source, **timing}
        with ZipFile(args.visuals) as visuals:
            bake_ui(visuals, staged / "shop_ui.anm2")
        write_json(staged / "sources.json", provenance)
        args.destination.mkdir(parents=True, exist_ok=True)
        for path in staged.iterdir():
            path.replace(args.destination / path.name)


if __name__ == "__main__":
    main()
