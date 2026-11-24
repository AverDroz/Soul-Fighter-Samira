"""Import the provided MVP T1 Miss Fortune model and animation sources."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path, PurePosixPath
import struct
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np

from import_yone_assets import (
    ROOT, Image, TexConverter, Wad, archive_hash, binfile, load_converter, path_hash,
    read_bin, read_wad_member, rig_events, wad_hash, write_json,
)


DESTINATION = ROOT / "assets/mf-local"
SKIN_BIN = "data/characters/missfortune/skins/skin69.bin"
GRAPH_BIN = "data/characters/missfortune/animations/skin69.bin"
SKIN_KEY = "Characters/MissFortune/Skins/Skin69"
GRAPH_KEY = "Characters/MissFortune/Animations/Skin69"
SUBCHUNK_TOC = "data/final/champions/missfortune.wad.subchunktoc"
PORTRAIT = "assets/characters/missfortune/hud/missfortune_circle_69.skins_missfortune_skin69.tex"
SKIN_ID = 21069
TAUNT_DOLL = "taunt-doll/doll.glb"
TAUNT_LOOP_EFFECT = 0x5338AA86

GUN_PAIR = ("A_Gun25", "A_Gun25_Gem")
BODY_SUBMESHES = {"Body", "Head", "Hair", "Fur", "Headdress", *GUN_PAIR}
HOMEGUARD_SUBMESHES = {"Throne", "C_Gun25", "C_Gun25_Gem", "C_Gun24"}
RECALL_SUBMESHES = {"C_Gun23", "C_Gun23_Wings", "B_Gun24"}
STAGED_SUBMESHES = HOMEGUARD_SUBMESHES | RECALL_SUBMESHES
CLIP_SUBMESHES = {
    "homeguard_in": HOMEGUARD_SUBMESHES,
    "homeguard": HOMEGUARD_SUBMESHES,
    "homeguard_out": HOMEGUARD_SUBMESHES,
    "homeguard_out_run": HOMEGUARD_SUBMESHES,
    "recall_cinematic": RECALL_SUBMESHES,
}

# State ID and ANM basename to verify in the source graph.
CLIPS = {
    "idle": (0xDFE2E631, "idle02"),
    "run": (0xF112F5B2, "run"),
    "run_in": (0x059C45F2, "run_in"),
    "attack": (0x3EE785B1, "attack1"),
    "attack2": (0xF0462CF0, "attack2"),
    "attack_out": (0x9F54849B, "attack1_to_idle"),
    "attack2_out": (0x730E2516, "attack2_to_idle"),
    "attack_run": (0x2F52C472, "attack1_to__run"),
    "attack_strut": (0xBF4AF0C0, "attack1_to__run2"),
    "q_in": (0xDBDA692E, "spell1_in"),
    "q": ("Spell1", "spell1"),
    "q_run": (0x36DCD151, "spell1_torun"),
    "w": ("Run2_In", "run2_in"),
    "e": ("Spell3", "spell3"),
    "e_out": (0xF9CFED98, "spell3_toidle"),
    "e_run": (0xA968C147, "spell3_torun"),
    "r_in": ("Spell4_Windup", "spell4_windup"),
    "r_out": (0x3279C7AC, "spell4_toidle"),
    "r_run": (0x7AF345AE, "spell4_torun"),
    "joke": (0x93F45FA2, "jokespam"),
    "joke_loop": (0xFD5D4579, "jokeloop"),
    "taunt": ("Taunt_In", "taunt_in"),
    "taunt_loop": ("Taunt_Loop", "taunt_loop"),
    "dance": (0x981CAAD3, "dance_in"),
    "laugh": ("Laugh", "laugh"),
    "recall": (0xA432C30D, "channel_in"),
    "recall_loop": (0x21C252A4, "channel_loop"),
    "recall_out": (0xA8DBE66B, "recall_winddown"),
    "homeguard_in": (0x326695AD, "homeguard_in"),
    "homeguard": (0x52314779, "homeguard"),
    "homeguard_out": (0x0BD31C4D, "homeguard_torun02"),
    "pentakill": (0xFF637EC5, "pentakill_in"),
    "death": ("Death", "death"),
    "respawn": (0x9F77283F, "respawn"),
}

SUPPLEMENTAL_CLIPS = {
    "base_idle": 0x6C2B2EE6,
    "idle_in": 0xB781551B,
    "joke_in": 0xE5575908,
    "strut_run_loop": "Run2",
    "attack2_run": 0x556CE909,
    "attack2_strut": 0xB57327E1,
    "crit": 0x644E4E20,
    "crit_out": 0x462B0526,
    "q_out": 0xADC4ECBE,
    "r_sustained": "Spell4_Loop",
    "dance_loop": 0x589C6CA2,
    "recall_cinematic": 0x5A81BDB0,
    "taunt_spam": 0x986D8FE5,
    "pentakill_bonus": 0xD788ACBD,
    "homeguard_out_run": 0x6C4296AD,
}


def verify_archives(model, abilities, detached_manifest):
    manifest = json.loads(abilities.read("manifest.json"))
    model_descriptor = json.loads(model.read("model.json"))
    if manifest != json.loads(detached_manifest.read_bytes()):
        raise ValueError("The abilities archive manifest differs from the detached manifest")
    if manifest["skin_id"] != SKIN_ID or model_descriptor["skin_id"] != SKIN_ID:
        raise ValueError(f"Expected Miss Fortune skin {SKIN_ID} in both archives")
    expected = manifest["assets"]
    if len(abilities.namelist()) != len(expected) + 1 or set(abilities.namelist()) != {*expected, "manifest.json"}:
        raise ValueError("The abilities archive membership differs from the manifest")
    for name, digest in expected.items():
        if sha256(abilities.read(name)).hexdigest() != digest:
            raise ValueError(f"Manifest hash mismatch for {name}")
    model_paths = {}
    for name in model.namelist():
        key = name.lower()
        if key in model_paths:
            raise ValueError(f"Duplicate model archive member {name}")
        if key in expected and sha256(model.read(name)).hexdigest() != expected[key]:
            raise ValueError(f"Shared assets differ across archives for {name}")
        model_paths[key] = name
    return model_descriptor, model_paths


def load_skin_entries(data):
    # This buffer has known field names but no downloaded hash dictionaries.
    dictionaries = tuple(getattr(binfile, f"hashfile_bin{name}")
                         for name in ("entries", "hashes", "fields", "types", "paths"))
    previous = tuple(dictionary.hashes for dictionary in dictionaries)
    try:
        for dictionary in dictionaries:
            dictionary.hashes = {}
        parsed = binfile.BinFile(BytesIO(data), btype_version=1008)
    finally:
        for dictionary, hashes in zip(dictionaries, previous):
            dictionary.hashes = hashes
    return {record.path.h: record for record in parsed.entries}


def animation_record(states, state):
    state_id = binfile.compute_binhash(state) if isinstance(state, str) else state
    node = states[state_id]
    source = node.getv("mAnimationResourceData").getv("mAnimationFilePath").lower()
    return state_id, source, node


def material_inputs(properties, entries):
    result = []
    submeshes = BODY_SUBMESHES | STAGED_SUBMESHES
    for override in properties.getv("materialOverride"):
        slot = override.getv("submesh")
        if slot not in submeshes:
            continue
        direct = override.getv("texture")
        if direct:
            texture = direct
        else:
            material = entries[override.getv("Material").h]
            texture = next(sample.getv("texturePath") for sample in material.getv("samplerValues")
                           if sample.getv("TextureName").lower() in ("diffuse_texture", "diffuse_color"))
        result.append({"submesh": slot, "texture": texture.lower()})
    if {item["submesh"] for item in result} != submeshes:
        raise ValueError("The source skin no longer defines the expected visible materials")
    return result


def checked_asset(source):
    path = PurePosixPath(source)
    if not source.startswith("assets/") or path.as_posix() != source or (
        ".." in path.parts or ":" in source or "\\" in source
    ):
        raise ValueError(f"Invalid asset path: {source!r}")
    return source


def prepare_taunt_doll(project, abilities, skin, entries, states):
    spam_state, spam_body, spam = animation_record(states, "Taunt_Spam")
    event = spam.getv("mEventDataMap")[0xBAEBA899]
    if event.type != "ParticleEventData":
        raise ValueError("Skin69 taunt doll no longer starts with a particle event")
    spam_effect = event.getv("mEffectKey").h
    attachment, = event.getv(0x60645D6A)
    joint = "C_BUFFBONE_GLB_LAYOUT_LOC"
    if attachment.getv("mBoneName").h != binfile.compute_binhash(joint):
        raise ValueError("Skin69 taunt doll attachment has changed")

    resolver = entries[skin.getv("mResourceResolver").h].getv("resourceMap")
    clips, props, effects = {}, {}, {}
    for action, effect in (("spam", spam_effect), ("loop", TAUNT_LOOP_EFFECT)):
        record = entries[resolver[effect].h]
        emitter = next(item for item in record.getv("complexEmitterDefinitionData")
                       if item.getv(0x3D25B8CE) == "Temp_Mesh")
        mesh = emitter.getv("primitive").getv("mMesh")
        material = entries[emitter.getv(0x4B901DB3).getv(0xD2E4D060).h]
        texture = next(sample.getv("texturePath") for sample in material.getv("samplerValues")
                       if sample.getv("TextureName").lower() == "diffuse_texture")
        current = {
            "simpleSkin": checked_asset(mesh.getv("mMeshName").lower()),
            "skeleton": checked_asset(mesh.getv(0x90595A15).lower()),
            "texture": checked_asset(texture.lower()),
        }
        if props and props != current:
            raise ValueError("Skin69 taunt doll clips point to different rigs or textures")
        props = current
        clips[action] = checked_asset(mesh.getv("mAnimationName").lower())
        effects[action] = {
            "effect_key": f"{effect:08x}", "entry": f"{record.path.h:08x}",
            "rotation_degrees": emitter.getv("birthRotation0").getv(0xB4B427AA),
            "scale": emitter.getv("birthScale0").getv(0xB4B427AA),
            "source_anm": clips[action],
        }

    raw = project / "assets/client"
    decoded = project / "assets/decoded"
    for source in (props["simpleSkin"], props["skeleton"], *clips.values()):
        target = raw / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(abilities.read(source))
    target = (decoded / props["texture"]).with_suffix(".png")
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(TexConverter.tex_to_dds(abilities.read(props["texture"])))) as image:
        image.convert("RGBA").save(target)
    write_json((decoded / SKIN_BIN).with_suffix(".json"), {"objects": {SKIN_KEY: {
        "skinMeshProperties": props,
        "skinAnimationProperties": {"animationGraphData": GRAPH_KEY},
    }}})
    write_json((decoded / GRAPH_BIN).with_suffix(".json"), {"objects": {GRAPH_KEY: clips}})
    return {
        "sources": props,
        "authored_event": {
            "body_state": f"{spam_state:08x}", "body_anm": spam_body,
            "frame": event.getv("mStartFrame", 0), "joint": joint,
        },
        "effects": effects,
    }


def read_skin_members(wad_path, wanted, supplied_graph):
    if wad_path is None or not wanted:
        return {}
    wad = Wad(str(wad_path), {})
    members = {entry.path_hash: entry for entry in wad.files}
    with wad_path.open("rb") as stream:
        toc = (read_wad_member(stream, members, SUBCHUNK_TOC)
               if wad_hash(SUBCHUNK_TOC) in members else None)
        if read_wad_member(stream, members, GRAPH_BIN, toc) != supplied_graph:
            raise ValueError("The PBE WAD and provided archives contain different Skin69 animation graphs")
        return {path: read_wad_member(stream, members, path, toc) for path in wanted}


def prepare_inputs(project, doll_project, model, abilities, detached_manifest, animation_wad):
    descriptor, model_paths = verify_archives(model, abilities, detached_manifest)
    skin = read_bin(abilities.read(SKIN_BIN), SKIN_KEY)
    graph_bytes = abilities.read(GRAPH_BIN)
    graph = read_bin(graph_bytes, GRAPH_KEY)
    if skin.getv("skinAnimationProperties").getv("animationGraphData") != GRAPH_KEY:
        raise ValueError("The skin points to an unexpected animation graph")
    properties = skin.getv("skinMeshProperties")
    props = {"initialSubmeshToHide": properties.getv("initialSubmeshToHide")}
    if props["initialSubmeshToHide"].split() != descriptor["hidden_submeshes"]:
        raise ValueError("The model's default visibility differs from the skin BIN")
    raw_dir = project / "assets/client"
    decoded_dir = project / "assets/decoded"
    for field, key in (("simpleSkin", "mesh"), ("skeleton", "skeleton"), ("texture", "texture")):
        source = descriptor[key].lower()
        if path_hash(properties.getv(field)) != wad_hash(source):
            raise ValueError(f"The model's {field} differs from the skin BIN")
        props[field] = source

    entries = {}
    for name in abilities.namelist():
        if name.endswith(".bin"):
            entries.update(load_skin_entries(abilities.read(name)))
    states = graph.getv("mClipDataMap")
    doll_data = prepare_taunt_doll(doll_project, abilities, skin, entries, states)
    write_json(doll_project / "rig-events.json", doll_data)
    props["materialOverride"] = material_inputs(properties, entries)
    selected = {action: animation_record(states, state) for action, (state, _) in CLIPS.items()}
    for action, (_, source, _) in selected.items():
        if Path(source).name.split(".")[0] != CLIPS[action][1]:
            raise ValueError(f"Unexpected graph source for {action}: {source}")
    supplement = {action: animation_record(states, state) for action, state in SUPPLEMENTAL_CLIPS.items()}
    ability_members = set(abilities.namelist())
    zip_members = model_paths.keys() | ability_members
    staged_textures = {item["texture"] for item in props["materialOverride"]
                       if item["submesh"] in STAGED_SUBMESHES}
    supplemental_sources = {source for _, source, _ in supplement.values()} | staged_textures
    wad_data = read_skin_members(animation_wad, sorted(supplemental_sources - zip_members), graph_bytes)
    available = zip_members | wad_data.keys()
    missing_materials = {item["submesh"]: item["texture"] for item in props["materialOverride"]
                         if item["submesh"] in STAGED_SUBMESHES and item["texture"] not in available}
    props["materialOverride"] = [item for item in props["materialOverride"]
                                 if item["submesh"] not in missing_materials]

    def asset_bytes(source):
        if source in wad_data:
            return wad_data[source]
        if source in model_paths:
            return model.read(model_paths[source])
        return abilities.read(source)

    textures = {props["texture"], *(item["texture"] for item in props["materialOverride"])}
    for source in map(checked_asset, sorted(textures | {PORTRAIT})):
        filename = project / "mf-portrait.png" if source == PORTRAIT else (decoded_dir / source).with_suffix(".png")
        filename.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(BytesIO(TexConverter.tex_to_dds(asset_bytes(source)))) as image:
            image.convert("RGBA").save(filename)

    missing = {}
    for action, record in supplement.items():
        state_id, source, _ = record
        if source in available:
            selected["r" if action == "r_sustained" else action] = record
        else:
            missing[action] = {"state": f"{state_id:08x}", "source_anm": source}

    sources = {props["simpleSkin"], props["skeleton"], *(source for _, source, _ in selected.values())}
    for source in map(checked_asset, sorted(sources)):
        path = raw_dir / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(asset_bytes(source))
    write_json((decoded_dir / SKIN_BIN).with_suffix(".json"), {"objects": {SKIN_KEY: {
        "skinMeshProperties": props,
        "skinAnimationProperties": {"animationGraphData": GRAPH_KEY},
    }}})
    write_json((decoded_dir / GRAPH_BIN).with_suffix(".json"), {
        "objects": {GRAPH_KEY: {"mClipDataMap": {
            f"{{{state:08x}}}": {"mAnimationResourceData": {"mAnimationFilePath": source}}
            for state, source, _ in selected.values()
        }}},
    })
    return selected, missing, missing_materials, props, states, {
        name: sha256(data).hexdigest() for name, data in wad_data.items()
    }


class Glb:
    def __init__(self, path):
        blob = path.read_bytes()
        magic, version, size, json_size, json_type = struct.unpack_from("<4sIIII", blob)
        binary_size, binary_type = struct.unpack_from("<II", blob, 20 + json_size)
        if (magic, version, size, json_type, binary_type) != (
            b"glTF", 2, len(blob), 0x4E4F534A, 0x004E4942,
        ) or binary_size != len(blob) - 28 - json_size:
            raise ValueError("HeroStudio produced an invalid GLB container")
        self.document = json.loads(blob[20:20 + json_size])
        self.binary = bytearray(blob[28 + json_size:])

    def accessor(self, index):
        access = self.document["accessors"][index]
        view = self.document["bufferViews"][access["bufferView"]]
        dtype = {5126: "<f4", 5123: "<u2", 5125: "<u4"}[access["componentType"]]
        columns = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[access["type"]]
        offset = view.get("byteOffset", 0) + access.get("byteOffset", 0)
        return np.frombuffer(self.binary, dtype, access["count"] * columns, offset).copy().reshape(-1, columns)

    def replace_accessor(self, index, values):
        access = self.document["accessors"][index]
        view = self.document["bufferViews"][access["bufferView"]]
        data = values.tobytes()
        if len(data) > view["byteLength"]:
            raise ValueError("The compacted data exceeds its original buffer view")
        start = view.get("byteOffset", 0)
        self.binary[start:start + len(data)] = data
        view["byteLength"] = len(data)
        access["count"] = len(values)
        if "min" in access:
            access["min"] = values.min(axis=0).tolist()
            access["max"] = values.max(axis=0).tolist()

    def append_accessor(self, template, values):
        document = self.document
        self.binary.extend(b"\0" * (-len(self.binary) % 4))
        data = values.tobytes()
        view = len(document["bufferViews"])
        document["bufferViews"].append({
            "buffer": 0, "byteOffset": len(self.binary), "byteLength": len(data),
        })
        self.binary.extend(data)
        index = len(document["accessors"])
        access = {**document["accessors"][template], "bufferView": view, "count": len(values)}
        if "min" in access:
            access["min"] = values.min(axis=0).tolist()
            access["max"] = values.max(axis=0).tolist()
        document["accessors"].append(access)
        return index

    def save(self, path):
        self.binary.extend(b"\0" * (-len(self.binary) % 4))
        self.document["buffers"][0]["byteLength"] = len(self.binary)
        document = json.dumps(self.document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        document += b" " * (-len(document) % 4)
        header = struct.pack("<4sIIII", b"glTF", 2, 28 + len(document) + len(self.binary),
                             len(document), 0x4E4F534A)
        with path.open("wb") as stream:
            stream.write(header)
            stream.write(document)
            stream.write(struct.pack("<II", len(self.binary), 0x004E4942))
            stream.write(self.binary)


def compact_draw_mesh(glb, materials):
    document = glb.document
    mesh = document["meshes"][0]
    mesh["primitives"] = [primitive for primitive in mesh["primitives"]
                          if document["materials"][primitive["material"]]["name"] in materials]
    # Keep only vertices and skin palette entries used by the visible mesh.
    # Retain the full skeleton hierarchy and authored animation channels.
    primitives = mesh["primitives"]
    ranges = {item["indices"]: glb.accessor(item["indices"]) for item in primitives}
    active = np.unique(np.concatenate(tuple(ranges.values())))
    attributes = primitives[0]["attributes"]
    index_map = np.zeros(int(active[-1]) + 1, dtype="<u4")
    index_map[active] = np.arange(len(active), dtype="<u4")
    for index, values in ranges.items():
        glb.replace_accessor(index, index_map[values])
    joint_index = attributes["JOINTS_0"]
    joints = glb.accessor(joint_index)[active]
    weights = glb.accessor(attributes["WEIGHTS_0"])[active]
    active_joints = np.unique(joints[weights > 0])
    if len(active_joints) > 192:
        raise ValueError(f"The visible mesh exceeds the renderer's joint limit: {len(active_joints)}")
    skin = document["skins"][0]
    inverse_index = skin["inverseBindMatrices"]
    skin["joints"] = [skin["joints"][index] for index in active_joints]
    glb.replace_accessor(inverse_index, glb.accessor(inverse_index)[active_joints])
    compact_joints = np.zeros_like(joints)
    compact_joints[weights > 0] = np.searchsorted(active_joints, joints[weights > 0])
    glb.replace_accessor(joint_index, compact_joints)
    for attribute, index in attributes.items():
        if attribute != "JOINTS_0":
            glb.replace_accessor(index, glb.accessor(index)[active])
    return len(active), len(active_joints)


def held_terminal_pose(glb, animation):
    source = animation["samplers"]
    time = glb.append_accessor(source[0]["input"], np.array([[0.0], [1.0]], dtype="<f4"))
    samplers = []
    for sampler in source:
        pose = glb.accessor(sampler["output"])[-1:]
        value = glb.append_accessor(sampler["output"], np.repeat(pose, 2, axis=0))
        samplers.append({"input": time, "output": value, "interpolation": "STEP"})
    return {"name": "r", "samplers": samplers, "channels": animation["channels"]}


def save_outputs(project, converted, selected, missing, missing_materials, props, states, provenance, wad_source):
    report = json.loads((project / "assets/preview/conversion.json").read_bytes())
    if report["failures"]:
        raise ValueError(f"HeroStudio animation conversion failed: {report['failures']}")
    glb = Glb(converted)
    document = glb.document
    document["asset"]["copyright"] = "MVP T1 Miss Fortune model, textures and animations © Riot Games."
    hidden = STAGED_SUBMESHES - missing_materials.keys()
    materials = BODY_SUBMESHES | hidden
    available_materials = {material["name"] for material in document["materials"]}
    if not materials <= available_materials:
        raise ValueError(f"Missing visible geometry: {sorted(materials - available_materials)}")
    vertices, palette = compact_draw_mesh(glb, materials)
    joints = {node["name"] for node in document["nodes"]}
    available = {clip["name"]: clip for clip in document["animations"]}
    animations, durations, graph = {}, {}, {}
    for action, (state, source, node) in selected.items():
        original = available[report["animation_sources"][source]]
        duration = max(document["accessors"][item["input"]]["max"][0] for item in original["samplers"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"Invalid duration for {action}: {duration}")
        animations[action] = {**original, "name": action}
        durations[action] = duration
        clip_materials = BODY_SUBMESHES | hidden.intersection(CLIP_SUBMESHES.get(action, ()))
        events = rig_events(node, clip_materials, joints)
        if action == "recall_cinematic":
            # The game's skin defaults hide the combat pair. Restore that default
            # for Recall, then let the final authored show event reveal the pair.
            events.insert(0, {"__type": "SubmeshVisibilityEventData", "mHideSubmeshList": GUN_PAIR})
        for event in events:
            if "C_Gun25" in event.get("mShowSubmeshList", ()):
                # The adapter's combat gun pair replaces the original default hidden
                # pair. Drop it only while the authored Homeguard pair is visible.
                event["mHideSubmeshList"].extend(GUN_PAIR)
        graph[f"{state:08x}"] = {
            "clip": action, "source_anm": source, "events": events,
        }
    if "r" not in animations:
        animations["r"] = held_terminal_pose(glb, animations["r_in"])
        durations["r"] = 1.0
        graph["r_preview"] = {
            "clip": "r", "source_anm": selected["r_in"][1],
            "mode": "hold_terminal_pose", "missing_source_anm": missing["r_sustained"]["source_anm"],
            "events": [],
        }
    document["animations"] = list(animations.values())
    glb.save(project / "mf.glb")
    write_json(project / "actions.json", durations)
    supplemental = {}
    if wad_source is not None:
        for kind, suffix in (("animation", ".anm"), ("material", ".tex")):
            entries = {path: digest for path, digest in wad_source["entries"].items() if path.endswith(suffix)}
            if entries:
                supplemental[f"supplemental_{kind}_source"] = {**wad_source, "entries": entries}
    write_json(project / "rig-events.json", {
        "source": "User-provided MVP T1 Miss Fortune Skin69 ZIP archives",
        "sources": provenance,
        "supplemental_animation_source": None,
        **supplemental,
        "frames_per_second": 30,
        "motion_root": "Root",
        "hidden_materials": sorted(hidden),
        "skin_default_hidden": props["initialSubmeshToHide"].split(),
        "gun_pair": GUN_PAIR,
        "materials": {item["submesh"]: item["texture"] for item in props["materialOverride"]},
        "states": graph,
        "missing_source_clips": missing,
        "missing_source_materials": missing_materials,
        "strut": {
            "graph_buff": "MissFortuneStrutMax",
            "entry": "w",
            "movement_fallback": "run",
            "spell2_graph_reference": animation_record(states, "Spell2")[1],
        },
    })
    return vertices, palette, durations


def save_taunt_doll(project, converted, provenance):
    report = json.loads((project / "assets/preview/conversion.json").read_bytes())
    if report["failures"]:
        raise ValueError(f"HeroStudio taunt doll conversion failed: {report['failures']}")
    glb = Glb(converted)
    glb.document["asset"]["copyright"] = "MVP T1 Miss Fortune taunt doll © Riot Games."
    rig_path = project / "rig-events.json"
    rig = json.loads(rig_path.read_bytes())
    animations = {clip["name"]: clip for clip in glb.document["animations"]}
    for action, effect in rig["effects"].items():
        original = animations[report["animation_sources"][effect["source_anm"]]]
        # Model's idle alias is the original taunt loop of the prop.
        original["name"] = "idle" if action == "loop" else action
        effect["clip"] = original["name"]
    rig["archives"] = provenance
    write_json(rig_path, rig)
    glb.save(project / "doll.glb")


def import_miss_fortune(model_path, abilities_path, manifest_path, studio_path, animation_wad=None):
    with TemporaryDirectory(prefix=".mf-import-", dir=DESTINATION.parent) as temporary:
        work = Path(temporary)
        project = work / "project"
        doll_project = work / "doll"
        convert = load_converter(work, studio_path)
        with ZipFile(model_path) as model, ZipFile(abilities_path) as abilities:
            selected, missing, missing_materials, props, states, wad_members = prepare_inputs(
                project, doll_project, model, abilities, manifest_path, animation_wad,
            )
        profile = {"client_import": {"champion": "missfortune", "skin_id": 69}}
        converted = project / convert(project, profile)
        doll_converted = doll_project / convert(doll_project, profile)
        provenance = {path.name: archive_hash(path) for path in (model_path, abilities_path, manifest_path)}
        wad_source = ({"file": animation_wad.name, "sha256": archive_hash(animation_wad), "entries": wad_members}
                      if wad_members else None)
        result = save_outputs(project, converted, selected, missing, missing_materials, props, states,
                              provenance, wad_source)
        save_taunt_doll(doll_project, doll_converted, provenance)
        DESTINATION.mkdir(exist_ok=True)
        for name in ("actions.json", "rig-events.json", "mf-portrait.png", "mf.glb"):
            (project / name).replace(DESTINATION / name)
        doll_destination = (DESTINATION / TAUNT_DOLL).parent
        doll_destination.mkdir(exist_ok=True)
        for name in ("doll.glb", "rig-events.json"):
            (doll_project / name).replace(doll_destination / name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--abilities", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--herostudio-archive", type=Path, required=True)
    parser.add_argument("--animation-wad", type=Path, help="Local PBE Miss Fortune WAD for supplemental clips and textures.")
    args = parser.parse_args()
    try:
        vertices, palette, durations = import_miss_fortune(
            args.model, args.abilities, args.manifest, args.herostudio_archive, args.animation_wad,
        )
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.exit(1, f"Miss Fortune import failed: {exc}\n")
    print(f"Imported {len(durations)} clips, {vertices} vertices and {palette} skin joints to {DESTINATION}")


if __name__ == "__main__":
    main()
