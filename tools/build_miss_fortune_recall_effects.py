"""Import original Skin69 Recall_Real stage, rune, logo, and beam sprites."""

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
from struct import unpack_from
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
from PIL import Image

from build_miss_fortune_effects import DESTINATION, PARTICLES, SUFFIX, write_atlas
from build_miss_fortune_special_effects import WAD_SHA256
from build_miss_fortune_ultimate_effects import ZIP_SHA256, checked_source
from import_yone_assets import TexConverter, Wad, archive_hash, wad_hash


ATLAS = "recall_effects"
SKIN = PARTICLES.removesuffix("particles/")
FLOOR_MESH = f"{PARTICLES}missfortune_skin69_recall_floor02{SUFFIX}scb"
ROAD_MASK = f"{PARTICLES}missfortune_skin69_recall_mask{SUFFIX}tex"
BEAM_SHA256 = "ab7591572f1e3637955a1002bfdb11f7f8db04df23a4cbf9e6f7e005c77eb16c"
SOURCES = {
    "RecallFloor": (
        f"{SKIN}missfortune_skin69_recallfloor_tx_cm{SUFFIX}tex",
        "9f4df132", "Dark8", 0, 9.0,
    ),
    "RecallRune": (
        f"{PARTICLES}missfortune_skin69_emote_ring01{SUFFIX}tex",
        "9f4df132", "Temp_GroundGlow_Constant1", 0, 5.0,
    ),
    "RecallLogo": (
        f"{PARTICLES}missfortune_skin69_t1_logo2026{SUFFIX}tex",
        "b2190176", "AOE_Indicator", 130, 5.0,
    ),
    "RecallFlourish": (
        f"{PARTICLES}varus_skin69_lightbeam{SUFFIX}tex",
        "b2190176", "skyBeam", 130, 5.0,
    ),
    "RecallRoad": (
        f"{SKIN}missfortune_skin69_recallfloor_tx_cm{SUFFIX}tex",
        "4454b697", "Dark3", 0, 8.0,
    ),
    "RecallTrophyFMVP": (
        f"{SKIN}missfortune_skin69_trophy_fmvp_tx_cm{SUFFIX}tex",
        "93ebb66e", "Temp_Mesh", 138, 5.0,
    ),
    "RecallTrophy2024": (
        f"{SKIN}missfortune_skin69_trophy_tx_cm{SUFFIX}tex",
        "872cce47", "Temp_Mesh", 230, 2.0,
    ),
    "RecallTrophy2025": (
        f"{SKIN}missfortune_skin69_trophy_2025_tx_cm{SUFFIX}tex",
        "862cccb4", "Temp_Mesh", 230, 2.0,
    ),
}
PROJECTIONS = {
    "RecallFloor": (FLOOR_MESH, "XZ", 180, 478),
    "RecallRoad": (f"{PARTICLES}missfortune_skin69_recall_floor01{SUFFIX}scb", "XZ", 180, 280),
    "RecallTrophyFMVP": (f"{PARTICLES}missfortune_skin69_fmvp_trophy_2025{SUFFIX}scb", "XY", 160, None),
    "RecallTrophy2024": (f"{PARTICLES}missfortune_skin69_trophy_2024{SUFFIX}scb", "XY", 0, None),
    "RecallTrophy2025": (f"{PARTICLES}missfortune_skin69_trophy_2025{SUFFIX}scb", "XY", 0, None),
}
ATTACHMENTS = {
    "RecallRoad": "VFX_buffbone01",
    "RecallTrophyFMVP": "Miss_FMVP_Trophy_2025",
    "RecallTrophy2024": "Miss_Trophy_2024",
    "RecallTrophy2025": "Miss_Trophy_2025",
}


def project_mesh(mesh, texture, plane, yaw, width):
    if mesh[:12] != b"r3d2Mesh\x03\x00\x02\x00":
        raise ValueError("Expected a Skin69 v3.2 SCB stage")
    vertex_count, face_count, flags = unpack_from("<III", mesh, 140)
    vertex_colors, = unpack_from("<I", mesh, 176)
    face_start = 192 + vertex_count * (12 + 4 * vertex_colors)
    face_colors = 9 * face_count if flags & 1 else 0
    # The Dance feather's exported mesh has a 24-byte footer after the face colors.
    footer = 24 if flags & 4 else 0
    if flags not in (2, 5) or vertex_colors not in (0, 1) or len(mesh) != face_start + 100 * face_count + face_colors + footer:
        raise ValueError("Unexpected Skin69 Recall SCB layout")

    vertices = np.array([unpack_from("<3f", mesh, 180 + index * 12)
                         for index in range(vertex_count)])
    if plane == "XZ":
        projected = vertices[:, [0, 2]] * [-1.2, -1.0]
        z = vertices[:, 1]
    else:
        angle = math.radians(yaw)
        x = vertices[:, 0] * 1.2
        y, z = vertices[:, 1], vertices[:, 2]
        projected = np.column_stack((x * math.cos(angle) + z * math.sin(angle), -y))
        z = z * math.cos(angle) - x * math.sin(angle)
    minimum = projected.min(axis=0)
    span = np.ptp(projected, axis=0)
    density = 1.0 if width is None else width / span[0]
    width, height = np.ceil(span * density).astype(int) + 2
    screen = (projected - minimum) * density + 1
    pivot = tuple(np.rint(-minimum * density + 1).astype(int).tolist())
    rows, columns = np.mgrid[:height, :width]
    sample_points = np.column_stack((columns.ravel() + .5, rows.ravel() + .5))
    depth = np.full((height, width), -np.inf)
    pixels = np.zeros((height, width, 4), np.uint8)
    texels = np.asarray(texture)
    for index in range(face_count):
        offset = face_start + index * 100
        corners = list(unpack_from("<3I", mesh, offset))
        uv = np.array(unpack_from("<6f", mesh, offset + 76)).reshape(2, 3)
        a, b, c = screen[corners]
        basis = np.column_stack((a - c, b - c))
        if abs(np.linalg.det(basis)) < 1e-8:
            continue
        u, v = ((sample_points - c) @ np.linalg.inv(basis).T).T.reshape(2, height, width)
        weights = np.stack((u, v, 1 - u - v), axis=-1)
        height_at_pixel = weights @ z[corners]
        mask = (weights >= 0).all(axis=-1) & (height_at_pixel > depth)
        coordinates = weights[mask] @ uv.T
        pixels[mask] = texels[
            (coordinates[:, 1] * texture.height).astype(int) % texture.height,
            (coordinates[:, 0] * texture.width).astype(int) % texture.width,
        ]
        depth[mask] = height_at_pixel[mask]
    return Image.fromarray(pixels), pivot


def build(abilities_zip, wad_path):
    if archive_hash(abilities_zip) != ZIP_SHA256 or archive_hash(wad_path) != WAD_SHA256:
        raise ValueError("Unexpected Skin69 source archive SHA-256")
    members = {member.path_hash: member for member in Wad(wad_path, hashes={}).files}
    images, sprites = {}, {}
    with ZipFile(abilities_zip) as archive, wad_path.open("rb") as stream:
        hashes = json.loads(archive.read("manifest.json"))["assets"]
        for animation, (path, effect_key, emitter, start_frame, lifetime) in SOURCES.items():
            if animation == "RecallFlourish":
                member = members.get(wad_hash(path))
                data = member.read_data(stream) if member is not None else None
                source = checked_source(path, data, BEAM_SHA256)
                source["archive"] = "PBE MissFortune.wad.client"
            else:
                data = archive.read(path)
                source = checked_source(path, data, hashes[path])
                source["archive"] = "MVP-T1-Miss-Fortune-Skin69-Abilities.zip"
            with Image.open(BytesIO(TexConverter.tex_to_dds(data))) as decoded:
                texture = decoded.convert("RGBA")
            metadata = {
                "sources": [source], "effect_key": effect_key, "emitter": emitter,
                "attachment_bone": ATTACHMENTS.get(animation, "C_BUFFBONE_GLB_LAYOUT_LOC"),
                "start_frame": start_frame,
                "particle_lifetime_seconds": lifetime, "source_texture_size": texture.size,
            }
            if animation in PROJECTIONS:
                mesh_path, plane, yaw, width = PROJECTIONS[animation]
                mesh = archive.read(mesh_path)
                mesh_source = checked_source(mesh_path, mesh, hashes[mesh_path])
                mesh_source["archive"] = source["archive"]
                metadata["sources"].append(mesh_source)
                metadata["projection"] = {"plane": plane, "yaw_degrees": yaw, "x_scale": 1.2}
                image, pivot = project_mesh(mesh, texture, plane, yaw, width)
                projected_bounds = image.getchannel("A").getbbox()
                if projected_bounds is None:
                    raise ValueError("Skin69 stage projection is fully transparent")
                image = image.crop(projected_bounds)
                pivot = (pivot[0] - projected_bounds[0], pivot[1] - projected_bounds[1])
                metadata["projection_crop_bounds"] = projected_bounds
                if animation == "RecallRoad":
                    mask = checked_source(ROAD_MASK, archive.read(ROAD_MASK), hashes[ROAD_MASK])
                    mask["archive"] = source["archive"]
                    metadata["animated_shader_dependency"] = mask
                if animation == "RecallTrophy2024":
                    metadata["additional_event"] = {
                        "effect_key": "16640a89", "attachment_bone": "Miss_Trophy_2023",
                        "start_frame": start_frame,
                    }
            else:
                bounds = texture.getchannel("A").getbbox()
                if bounds is None:
                    raise ValueError(f"Skin69 texture is fully transparent: {path}")
                image = texture.crop(bounds)
                pivot = (image.width // 2, image.height // 2)
                metadata["crop_bounds"] = bounds
            if image.getchannel("A").getbbox() is None:
                raise ValueError(f"Skin69 sprite is fully transparent: {animation}")
            metadata["sprite_size"] = image.size
            metadata["pivot"] = pivot
            images[animation] = image
            sprites[animation] = metadata

    write_atlas(images, ATLAS, (512, 256), "RecallFloor")
    animation_path = DESTINATION / f"{ATLAS}.anm2"
    tree = ET.parse(animation_path)
    for animation in PROJECTIONS:
        frame = tree.find(f"./Animations/Animation[@Name='{animation}']/LayerAnimations/LayerAnimation/Frame")
        x, y = sprites[animation]["pivot"]
        frame.set("XPivot", str(x))
        frame.set("YPivot", str(y))
    tree.write(animation_path, encoding="utf-8", xml_declaration=True)
    provenance = {
        "archives": {
            "MVP-T1-Miss-Fortune-Skin69-Abilities.zip": ZIP_SHA256,
            "PBE MissFortune.wad.client": WAD_SHA256,
        },
        "animation": {"name": "Recall_Real", "state": "5a81bdb0", "fps": 30},
        "conversion": "CDTB TEX to DDS and Pillow to RGBA",
        "crop_format": "Source pixel bounds with exclusive right and bottom",
        "pivot_format": "Sprite-local pixels from top-left. Mesh projections preserve their original origins.",
        "sprites": sprites,
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
