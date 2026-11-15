"""Build the runtime particle pack from the pinned Riot Samira WAD.

Run with the same dependencies and working directory as fetch_samira_assets.py.
The decoded Skin30 property BIN provides the named systems and WAD asset paths.
"""
from collections import deque
from io import BytesIO
import json
from pathlib import Path
import re
import struct

import requests

from fetch_samira_assets import (
    CDRAGON, OUTPUT, RIOT_MANIFEST, SKIN, WAD_FILE, WAD_SHA256,
    Image, TexConverter, Wad, digest, fetch_wad, file_hash,
    load_objects, remap_classes, toc_for, write_json, xxh64_intdigest,
)


DEST = OUTPUT / "vfx"
PREFIX = "Samira_Skin30_"
MANIFEST = "soul-fighter-manifest.json"
SYSTEMS = "soul-fighter-systems.json"
ASSET_PATH = re.compile(r"assets/.+\.(?:tex|dds|png|scb|sco|skn)", re.I)

ROLES = {
    "auto_muzzle": ("BA_Muzzle",),
    "auto_projectile": ("BA_Projectile", "AA_mis_Crit"),
    "auto_impact": ("BA_Tar", "AA_tar_Crit"),
    "auto_melee": ("BA_Melee_One", "BA_Melee_Two", "BA_Melee_Crit_Swipe"),
    "auto_melee_impact": ("BA_Melee_One_Tar", "BA_Melee_two_Tar", "BA_Melee_Crit_Tar"),
    "q_muzzle": ("Q_Muzzle",),
    "q_projectile": ("Q_Projectile",),
    "q_impact": ("Q_Tar",),
    "q_expire": ("Q_Miss_Dissipation",),
    "q_slash": ("Q_Melee_AOE",),
    "q_slash_impact": ("Q_Melee_Tar",),
    "w_slash": ("W_CircleCut",),
    "w_zone": ("W_Zone",),
    "w_blade_trail": ("W_SwordTrail",),
    "w_impact": ("W_tar",),
    "w_block": ("W_Missle_Block", "W_Missile_Block_Beam", "W_Ult_block"),
    "e_dash": ("E_DashTrail", "E_R_Dash_Trail", "E_Air_Trail"),
    "e_impact": ("E_dash_hit",),
    "eq_combo": ("Q_EBufferCast", "E_Q_Buffer_Target"),
    "r_ring": ("R_Range_Indicator_Self",),
    "r_sword": ("R_SwordSpin",),
    "r_muzzle": ("R_Gun_Blue_Muzzle", "R_Gun_Red_Muzzle"),
    "r_projectile": ("R_Mis_Gun_Blue", "R_Mis_Gun_Red", "R_mis"),
    "r_tracer": ("R_Tracer_Flash",),
    "r_impact": ("R_Tar",),
}
MUZZLE_VIEWS = {
    "BA_Mis": ("BA_Muzzle", "BA_Projectile", {"Temp_Mesh8", "Temp_Mesh9"}),
    "Q_Mis": ("Q_Muzzle", "Q_Projectile", {"Temp_Mesh3"}),
}
ICON_ROOT = "assets/characters/samira/hud/"
ICONS = {
    "q": ICON_ROOT + "icons2d/samiraq.dds",
    "w": ICON_ROOT + "icons2d/samiraw.dds",
    "e": ICON_ROOT + "icons2d/samirae.dds",
    "r": ICON_ROOT + "icons2d/samirar1.dds",
    "passive": ICON_ROOT + "icons2d/samirap.dds",
    "avatar": ICON_ROOT + "samira_circle_30.tex",
}
CURSORS = {
    "move": ("hand1", "e77dd46b3e6156b624418f994803401cbc618d4a124099fb82a0d1c316ca1c74"),
    "target": ("singletargetenemy", "c52c39f23eae1e99e2cc23ee60fc92e5304e1a0f477f539798c3ea46c88ec810"),
}
SCB_FORMAT = "https://github.com/LeagueToolkit/LeagueToolkit/tree/main/src/LeagueToolkit/Core/Mesh"


def triangle_vertices(content):
    """Expand the SCB face indices and corner UVs for the companion's GPU input."""
    magic, major, minor = struct.unpack_from("<8sHH", content)
    vertex_count, face_count, flags = struct.unpack_from("<III", content, 140)
    if magic != b"r3d2Mesh" or major not in (2, 3):
        raise ValueError(f"Unsupported SCB header {(magic, major, minor)}")
    vertex_start = 176
    color_stride = 0
    if (major, minor) >= (3, 2):
        color_stride = 4 if struct.unpack_from("<I", content, vertex_start)[0] == 1 else 0
        vertex_start += 4
    face_start = vertex_start + vertex_count * (12 + color_stride) + 12
    face_stride = 100
    face_color_stride = 9 if flags & 1 else 0
    if face_start + face_count * (face_stride + face_color_stride) != len(content):
        raise ValueError("Unexpected SCB data length")
    vertices = tuple(struct.iter_unpack("<3f", content[vertex_start:vertex_start + vertex_count * 12]))
    triangles = []
    for face in range(face_count):
        offset = face_start + face * face_stride
        indices = struct.unpack_from("<3I", content, offset)
        uv = struct.unpack_from("<6f", content, offset + 76)
        for corner, index in enumerate(indices):
            triangles.append((*vertices[index], uv[corner], uv[corner + 3]))
    return triangles


def texture_or_mesh_paths(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from texture_or_mesh_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from texture_or_mesh_paths(item)
    elif isinstance(value, str) and ASSET_PATH.fullmatch(value):
        yield value.lower()


def child_links(system):
    for emitter in system.get("complexEmitterDefinitionData", []):
        yield from emitter.get("childParticleSetDefinition", {}).get("childrenIdentifiers", [])


def child_name(link, resource_map):
    reference = link.get("effect", link.get("effectKey", ""))
    name = resource_map.get(reference, reference).rsplit("/", 1)[-1]
    return name.removeprefix(PREFIX)


def collect_systems(objects):
    definitions = {
        name.rsplit("/", 1)[-1].removeprefix(PREFIX): (name, value)
        for name, value in objects.items()
        if value.get("__type") == "VfxSystemDefinitionData"
    }
    resource_map = objects["Characters/Samira/Skins/Skin30/Resources"]["resourceMap"]
    views = {view for muzzle, projectile, _ in MUZZLE_VIEWS.values() for view in (muzzle, projectile)}
    roots = {name for names in ROLES.values() for name in names} - views
    queue = deque(sorted(roots | MUZZLE_VIEWS.keys()))
    systems, sources, unresolved = {}, {}, set()
    while queue:
        name = queue.popleft()
        if name in systems:
            continue
        source, value = definitions[name]
        system = remap_classes(value)
        systems[name] = system
        sources[name] = {"definition": source}
        for link in child_links(system):
            child = child_name(link, resource_map)
            if child in definitions:
                link["effect"] = child
                queue.append(child)
            else:
                unresolved.add((name, child))
                link["effect"] = child
    for parent, (muzzle, projectile, names) in MUZZLE_VIEWS.items():
        system = systems[parent]
        emitters = system["complexEmitterDefinitionData"]
        muzzle_emitters = [emitter for emitter in emitters if emitter.get("emitterName") in names]
        if {emitter["emitterName"] for emitter in muzzle_emitters} != names:
            raise ValueError(f"Muzzle emitter selection no longer matches {parent}")
        projectile_emitters = [emitter for emitter in emitters if emitter not in muzzle_emitters]
        for view, selected in ((muzzle, muzzle_emitters), (projectile, projectile_emitters)):
            systems[view] = {**system, "complexEmitterDefinitionData": selected}
            sources[view] = {**sources[parent], "emitters": [emitter["emitterName"] for emitter in selected]}
    return systems, sources, sorted(unresolved)


def export_assets(paths):
    wad = Wad(str(WAD_FILE), {})
    by_hash = {entry.path_hash: entry for entry in wad.files}
    entries = {name: by_hash[xxh64_intdigest(name.encode())] for name in sorted(paths)}
    assets, icons, skipped = {}, {}, {}
    icon_names = {path: name for name, path in ICONS.items()}
    with WAD_FILE.open("rb") as stream:
        chunked = [entry for entry in entries.values() if entry.type == 4]
        toc = toc_for(stream, wad.files, chunked) if chunked else None
        for name, entry in entries.items():
            content = entry.read_data(stream, toc)
            if len(content) != entry.size:
                raise ValueError(f"WAD size mismatch: {name}")
            path = Path(name)
            metadata = {"wad_size": len(content), "wad_sha256": digest(content)}
            if path.suffix in (".tex", ".dds", ".png"):
                if name in icon_names:
                    file = Path("icons") / (icon_names[name] + ".png")
                else:
                    file = Path("textures") / path.with_suffix(".png")
                output = DEST / file
                output.parent.mkdir(parents=True, exist_ok=True)
                image_data = TexConverter.tex_to_dds(content) if path.suffix == ".tex" else content
                with Image.open(BytesIO(image_data)) as image:
                    image.convert("RGBA").save(output)
                    metadata["dimensions"] = list(image.size)
            elif path.suffix == ".scb":
                file = Path("meshes") / path.with_suffix(".json")
                triangles = triangle_vertices(content)
                metadata["triangles"] = len(triangles) // 3
                output = DEST / file
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(triangles, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
            else:
                skipped[name] = {**metadata, "reason": "The companion consumes unskinned meshes and textures."}
                continue
            record = {**metadata, "file": file.as_posix(), "sha256": file_hash(output)}
            if name in icon_names:
                icons[icon_names[name]] = {**record, "wad_path": name}
            else:
                assets[name] = record
    return assets, icons, skipped


def export_cursors():
    icons = {}
    for name, (asset, checksum) in CURSORS.items():
        url = CDRAGON + f"assets/ux/cursors/{asset}.png"
        file = f"icons/{name}.png"
        output = DEST / file
        if not output.is_file():
            response = requests.get(url, timeout=25)
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as source:
                image = source.convert("RGBA")
                if digest(image.tobytes()) != checksum:
                    raise ValueError(f"Cursor pixel checksum mismatch: {url}")
                output.parent.mkdir(parents=True, exist_ok=True)
                image.save(output)
        with Image.open(output) as image:
            if digest(image.convert("RGBA").tobytes()) != checksum:
                raise ValueError(f"Cursor pixel checksum mismatch: {output}")
            icons[name] = {
                "file": file, "source_url": url, "sha256": file_hash(output),
                "pixel_sha256": checksum, "dimensions": list(image.size),
            }
    return icons


def main():
    fetch_wad()
    systems, sources, unresolved = collect_systems(load_objects(SKIN))
    paths = set(texture_or_mesh_paths(systems))
    assets, icons, skipped = export_assets(paths.union(ICONS.values()))
    icons.update(export_cursors())
    write_json(DEST / SYSTEMS, systems)
    write_json(DEST / MANIFEST, {
        "source": "Riot Games, League of Legends, Soul Fighter Samira (Skin30)",
        "riot_manifest": RIOT_MANIFEST,
        "wad_path": "DATA/FINAL/Champions/Samira.wad.client",
        "wad_sha256": WAD_SHA256,
        "particle_bin": SKIN,
        "decoded_particle_bin_url": CDRAGON + SKIN + ".json",
        "decoded_particle_bin_sha256": file_hash(OUTPUT / "decoded" / (SKIN + ".json")),
        "mesh_format_reference": SCB_FORMAT,
        "systems_sha256": file_hash(DEST / SYSTEMS),
        "assets": assets,
        "icons": icons,
        "unused_asset_formats": skipped,
        "unresolved_child_links": unresolved,
    })
    write_json(DEST / "catalog.json", {
        "bundle": "soul-fighter",
        "roles": ROLES,
        "icons": {name: entry["file"] for name, entry in icons.items()},
        "systems": {
            name: {**source, "assets": sorted(set(texture_or_mesh_paths(systems[name])))}
            for name, source in sorted(sources.items())
        },
    })
    print(f"Exported {len(systems)} systems and {len(assets)} assets with {len(icons)} HUD icons. "
          f"Skipped {len(skipped)} unsupported asset types, unresolved child links: {unresolved}")


if __name__ == "__main__":
    main()
