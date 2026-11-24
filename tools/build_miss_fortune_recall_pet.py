"""Bake the original Skin69 Recall pet for Isaac's native sprite renderer."""

import argparse
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import moderngl
import numpy as np
from PIL import Image

from build_miss_fortune_native_actions import (
    DEST, DIRECTIONS, GLB, ORIGIN, PAGE_SIZE, SUPERSAMPLE, VIEWPORT,
    GPURenderer, Model, YONE_VIEW, add_animation, new_document, pack_clip,
)
from import_miss_fortune_assets import (
    GRAPH_BIN, GRAPH_KEY, ROOT, SKIN_BIN, SKIN_ID, SKIN_KEY, Glb, TexConverter,
    animation_record, archive_hash, binfile, checked_asset, load_converter,
    load_skin_entries, read_bin, write_json,
)


CLIP = "recall_cinematic"
STATE = 0x5A81BDB0
EFFECT = 0x7236F3F5
NAME = "recall_pet"
ANIMATION = "RecallDog"
FPS = 30


def prepare_pet(project, archive, detached):
    supplied = json.loads(archive.read("manifest.json"))
    if supplied["skin_id"] != SKIN_ID or supplied != json.loads(detached.read_bytes()):
        raise ValueError("The provided Skin69 abilities manifests differ")
    hashes = supplied["assets"]

    def checked_read(path):
        data = archive.read(path)
        if sha256(data).hexdigest() != hashes[path]:
            raise ValueError(f"Manifest hash mismatch for {path}")
        return data

    graph = read_bin(checked_read(GRAPH_BIN), GRAPH_KEY).getv("mClipDataMap")
    _, source, recall = animation_record(graph, STATE)
    event, = (item for item in recall.getv("mEventDataMap").values()
              if item.type == "ParticleEventData" and item.getv("mEffectKey").h == EFFECT)
    attachment, = event.getv(0x60645D6A)
    socket = "C_BUFFBONE_GLB_LAYOUT_LOC"
    if attachment.getv("mBoneName").h != binfile.compute_binhash(socket):
        raise ValueError("Recall pet attachment does not match the Skin69 layout socket")
    skin = read_bin(checked_read(SKIN_BIN), SKIN_KEY)
    entries = {}
    for path in hashes:
        if path.endswith(".bin"):
            entries.update(load_skin_entries(checked_read(path)))
    resolver = entries[skin.getv("mResourceResolver").h].getv("resourceMap")
    effect = entries[resolver[EFFECT].h]
    emitter, = (item for item in effect.getv("complexEmitterDefinitionData")
                if item.getv(0x3D25B8CE) == "Temp_Mesh")
    skinned = emitter.getv("primitive").getv("mMesh")
    mesh = checked_asset(skinned.getv("mMeshName").lower())
    skinning = checked_asset(skinned.getv(0x90595A15).lower())
    animation = checked_asset(skinned.getv(0xFBD16FB5).lower())
    texture = checked_asset(emitter.getv("texture").lower())
    raw = project / "assets/client"
    decoded = project / "assets/decoded"
    for path in (mesh, skinning, animation):
        outfile = raw / path
        outfile.parent.mkdir(parents=True, exist_ok=True)
        outfile.write_bytes(checked_read(path))
    png = (decoded / texture).with_suffix(".png")
    png.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(TexConverter.tex_to_dds(checked_read(texture)))) as image:
        image.convert("RGBA").save(png)
    write_json((decoded / SKIN_BIN).with_suffix(".json"), {"objects": {SKIN_KEY: {
        "skinMeshProperties": {"simpleSkin": mesh, "skeleton": skinning, "texture": texture},
        "skinAnimationProperties": {"animationGraphData": GRAPH_KEY},
    }}})
    write_json((decoded / GRAPH_BIN).with_suffix(".json"), {"objects": {GRAPH_KEY: {"pet": animation}}})
    return {
        "source_graph_state": f"{STATE:08x}", "source_graph_animation": source,
        "effect_name": effect.getv("particleName"), "effect_key": f"{EFFECT:08x}",
        "anchor_bone": socket, "start_frame": int(event.getv("mStartFrame")),
        "emitter_lifetime_seconds": emitter.getv("particleLifetime").getv(0xB4B427AA),
        "emitter_scale": emitter.getv("birthScale0").getv(0xB4B427AA),
        "emitter_rotation_degrees": emitter.getv("birthRotation0").getv(0xB4B427AA),
        "source_assets": {path: hashes[path] for path in (SKIN_BIN, GRAPH_BIN, mesh, skinning, animation, texture)},
    }


def emitter_transform(data):
    pitch, yaw, roll = data["emitter_rotation_degrees"]
    if pitch or roll:
        raise ValueError("Unsupported Recall pet emitter rotation")
    angle = math.radians(yaw)
    cosine, sine = math.cos(angle), math.sin(angle)
    result = np.array(((cosine, 0, sine, 0), (0, 1, 0, 0),
                       (-sine, 0, cosine, 0), (0, 0, 0, 1)), dtype=np.float32)
    result[:, :3] *= data["emitter_scale"]
    return result


def crop_pose(buffer):
    pixels = np.frombuffer(buffer.read(components=4), np.uint8).reshape(VIEWPORT[1], VIEWPORT[0], 4)[::-1]
    box = Image.fromarray(pixels[:, :, 3]).getbbox()
    if not box or not (0 < box[0] < box[2] < VIEWPORT[0] and 0 < box[1] < box[3] < VIEWPORT[1]):
        raise ValueError(f"Empty or clipped Recall pet pose: {box}")
    x, y, right, bottom = box
    left = math.floor((x - ORIGIN[0]) / SUPERSAMPLE) - 1
    top = math.floor((y - ORIGIN[1]) / SUPERSAMPLE) - 1
    right = math.ceil((right - ORIGIN[0]) / SUPERSAMPLE) + 1
    bottom = math.ceil((bottom - ORIGIN[1]) / SUPERSAMPLE) + 1
    x0, y0, x1, y1 = (round(origin + value * SUPERSAMPLE)
                      for origin, value in zip((*ORIGIN, *ORIGIN), (left, top, right, bottom), strict=True))
    rgba = pixels[y0:y1, x0:x1].copy()
    alpha = rgba[:, :, 3:4].astype(np.float32)
    rgba[:, :, :3] = np.clip(rgba[:, :, :3].astype(np.float32) * 255 / np.maximum(alpha, 1), 0, 255)
    return Image.fromarray(rgba).resize((right - left, bottom - top), Image.Resampling.LANCZOS), (left, top)


def bake(pet_path, model_path, data):
    recall = Model(model_path, hero="mf")
    model = Model(pet_path, hero="mf")
    frame_count = round(FPS * model.durations["idle"]) + 1
    total = FPS * recall.durations[CLIP]
    end_frame = data["start_frame"] + frame_count - 1
    if not math.isclose(total, end_frame, abs_tol=1e-4):
        raise ValueError(f"Recall pet ends at frame {end_frame}, Recall ends at {total}")
    data.update(fps=FPS, frame_count=frame_count, animation_seconds=(frame_count - 1) / FPS,
                end_frame=end_frame, direction_count=DIRECTIONS)
    target_joint = recall.node_names[data["anchor_bone"]]
    emitter = emitter_transform(data)
    placements = []
    for index in range(frame_count):
        phase = (index + data["start_frame"]) / total
        pose = recall.anchor_motion(recall.sample(CLIP, phase), CLIP)
        anchor = recall.world_matrices(pose, CLIP, phase)[target_joint]
        placements.append(anchor @ emitter)

    frames = []
    with moderngl.create_standalone_context(require=330) as context:
        surface = context.simple_framebuffer(VIEWPORT, components=4)
        actor = GPURenderer(context, model)
        actor.view = YONE_VIEW
        actor.model.pixel_scale = .9
        try:
            for direction in range(DIRECTIONS):
                yaw = math.tau * direction / DIRECTIONS
                poses = []
                for index, placement in enumerate(placements):
                    surface.use()
                    surface.clear(0, 0, 0, 0)
                    actor.draw("idle", index / (frame_count - 1), ORIGIN, VIEWPORT, yaw, 0,
                               clip="idle", detached=True, model_transform=placement)
                    if context.error != "GL_NO_ERROR":
                        raise ValueError(f"GPU error at Recall pet direction {direction}, frame {index}")
                    poses.append(crop_pose(surface))
                frames.append(poses)
        finally:
            actor.close()
            surface.release()
    return frames


def write_atlas(stage, poses, data):
    # Put tight, zero-pivot crops on the page. Layer X/Y positions preserve the
    # original root trajectory without packing empty space back to the anchor.
    samples = [[(image, (0, 0)) for image, _ in direction] for direction in poses]
    layout = pack_clip(samples, [])
    if layout is None:
        raise ValueError(f"Recall pet atlas exceeds a {PAGE_SIZE}-pixel page")
    shelves, crops = layout
    page = Image.new("RGBA", (max(shelf[2] for shelf in shelves), sum(shelf[1] for shelf in shelves)))
    root, sheets, layers, animations = new_document()
    animations.set("DefaultAnimation", ANIMATION)
    ET.SubElement(sheets, "Spritesheet", Path=f"{NAME}.png", Id="0")
    ET.SubElement(layers, "Layer", Name="Pet", Id="0", SpritesheetId="0")
    for direction, (frames, locations, offsets) in enumerate(zip(samples, crops, poses, strict=True)):
        add_animation(animations, ANIMATION, direction, False, 0, frames, locations)
        for element, (image, offset), location in zip(
            animations[-1].findall("LayerAnimations/LayerAnimation/Frame"), offsets, locations, strict=True,
        ):
            element.set("XPosition", str(offset[0]))
            element.set("YPosition", str(offset[1]))
            page.paste(image, location)
    default = deepcopy(animations[0])
    default.set("Name", ANIMATION)
    animations.insert(0, default)
    page.save(stage / f"{NAME}.png")
    ET.indent(root)
    ET.ElementTree(root).write(stage / f"{NAME}.anm2", encoding="utf-8", xml_declaration=True)
    data.update(atlas_size=page.size, frame_pivot=[0, 0], animation=ANIMATION,
                directions=[f"{ANIMATION}{direction}" for direction in range(DIRECTIONS)],
                offsets="Per-frame XPosition and YPosition relative to the Miss Fortune scene anchor",
                output_sha256={f"{NAME}.{ext}": archive_hash(stage / f"{NAME}.{ext}") for ext in ("anm2", "png")})
    write_json(stage / f"{NAME}.provenance.json", data)


def build(abilities, manifest, studio, model):
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix=".mf-pet-", dir=work) as temporary:
        stage = Path(temporary)
        project = stage / "project"
        convert = load_converter(stage, studio)
        with ZipFile(abilities) as archive:
            data = prepare_pet(project, archive, manifest)
        profile = {"client_import": {"champion": "missfortune", "skin_id": 69}}
        converted = Glb(project / convert(project, profile))
        animation, = converted.document["animations"]
        animation["name"] = "idle"
        converted.document["asset"]["copyright"] = "Skin69 Recall pet model, texture and animation © Riot Games."
        pet = stage / "pet.glb"
        converted.save(pet)
        data.update(abilities_archive=abilities.name, abilities_archive_sha256=archive_hash(abilities),
                    attachment_model_sha256=archive_hash(model), copyright="Riot Games")
        write_atlas(stage, bake(pet, model, data), data)
        DEST.mkdir(parents=True, exist_ok=True)
        for ext in ("png", "anm2", "provenance.json"):
            filename = f"{NAME}.{ext}"
            (stage / filename).replace(DEST / filename)
        print(f"Baked {data['frame_count']} Recall pet frames x {DIRECTIONS} directions to {DEST}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abilities", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--herostudio-archive", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=GLB)
    args = parser.parse_args()
    build(args.abilities, args.manifest, args.herostudio_archive, args.model)
