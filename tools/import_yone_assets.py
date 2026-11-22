"""Convert classic Yone's locally installed League assets for the Isaac renderer."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from cdtb import binfile
from cdtb.export import TexConverter
from cdtb.wad import Wad
from PIL import Image
from xxhash import xxh64_intdigest


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "assets/yone-local"
SKIN_BIN = "data/characters/yone/skins/skin0.bin"
GRAPH_BIN = "data/characters/yone/animations/skin0.bin"
SUBCHUNK_TOC = "data/final/champions/yone.wad.subchunktoc"
PORTRAIT = "assets/characters/yone/hud/yone_circle_0.tex"
SKIN_KEY = "Characters/Yone/Skins/Skin0"
GRAPH_KEY = "Characters/Yone/Animations/Skin0"
BASE = "assets/characters/yone/skins/base/"
TEXTURES = tuple(BASE + stem + ".tex" for stem in (
    "yone_base_tx_cm", "yone_base_swords_tx_cm", "yone_base_props_tx_cm",
    "yone_base_recall_tx_cm", "streak_red_tx_cm", "streak_white_tx_cm",
))
# Semantic name, exact base animation graph state, original ANM basename.
# Some graph states are supplied by Riot as unnamed FNV hashes.
ACTIONS = {
    "idle": ("Idle1_Base", "yone_idle01"),
    "run": ("Run_Base", "yone_walk01"),
    "attack": (0x01777011, "yone_attack01"),
    "attack2": (0x169444B0, "yone_attack02"),
    "q": (0x6CA103AF, "yone_spell1_a_01"),
    "q_follow": (0x6DA10542, "yone_spell1_a_02"),
    "q3_in": ("Spell1C_In", "yone_spell1c_in"),
    "q3": ("Spell1C_Dash", "yone_spell1c_dash"),
    "q3_out": ("Spell1C_Out", "yone_spell1c_out"),
    "w": ("Spell2", "yone_spell2"),
    "e": ("Spell3_Spirit", "yone_spell3_spiritin"),
    "e_dash": ("Spell3_Dash", "dusk_spell3_dash"),
    "e_body": ("Spell3_BodyLoop", "yone_spell3_bodyloop"),
    "e_return": ("Spell3_Out", "yone_spell3_out"),
    "e_return_out": ("Spell3_End2", "yone_spell3_end2"),
    "r": ("Spell4", "yone_spell4_in"),
    "r_out": ("Spell4_Out", "yone_spell4_out_notmoving"),
    "joke": ("Joke_In", "yone_joke"),
    "joke_loop": ("Joke_Loop", "yone_joke_loop"),
    "taunt": ("Taunt_In", "yone_taunt"),
    "taunt_loop": ("Taunt_Loop", "yone_taunt_loop"),
    "dance_in": ("Dance_In", "yone_dance_in"),
    "dance": ("Dance_Loop", "yone_dance_loop"),
    "laugh": ("Laugh_In", "yone_laugh"),
    "laugh_loop": ("Laugh_Loop", "yone_laugh_loop"),
    "death": ("Death", "yone_death01"),
}
STUDIO_MODULES = (
    "animation_bindings.py", "client_model.py", "client_paths.py", "equipment.py",
    "equipment-data.json", "equipment-presets.json", "glb.py", "player_settings.py",
    "project.py", "resource-data.json", "resources.py",
    "pyritofile/__init__.py", "pyritofile/anm.py", "pyritofile/ermmm.py",
    "pyritofile/stream.py", "pyritofile/structs.py",
)


def archive_hash(path):
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_converter(work, archive_path):
    lock = json.loads((ROOT / "docs/sources.lock.json").read_bytes())
    release = next(asset for asset in lock["assets"] if asset["name"].startswith("Isaac-LoL-HeroStudio"))
    if archive_path.stat().st_size != release["size_bytes"] or archive_hash(archive_path) != release["sha256"]:
        raise ValueError(f"Expected the repository-pinned HeroStudio release {release['name']}")
    app = lock["studio_inner_directory"] + "/app"
    with ZipFile(archive_path) as archive:
        for module in STUDIO_MODULES:
            archive.extract(f"{app}/{module}", work)
    sys.path.insert(0, str(work / app))
    from client_model import convert

    return convert


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wad_hash(path):
    return xxh64_intdigest(path.lower().encode("ascii"))


def read_wad_member(stream, members, path, toc=None):
    entry = members.get(wad_hash(path))
    if entry is None:
        raise ValueError(f"Missing Yone archive member {path}")
    content = entry.read_data(stream, toc)
    if content is None or len(content) != entry.size:
        raise ValueError(f"Could not read Yone archive member {path}")
    return content


def path_hash(value):
    return value.h if isinstance(value, binfile.BinPathValue) else wad_hash(value)


def read_bin(data, key):
    # CDTB can match the handful of named fields needed here without loading any
    # external hash list. Archive resource paths are checked against their hashes.
    dictionaries = (binfile.hashfile_binentries, binfile.hashfile_binhashes,
                    binfile.hashfile_binfields, binfile.hashfile_bintypes, binfile.hashfile_binpaths)
    old_hashes = [dictionary.hashes for dictionary in dictionaries]
    try:
        for dictionary in dictionaries:
            dictionary.hashes = {}
        contents = binfile.BinFile(BytesIO(data), btype_version=1008)
    finally:
        for dictionary, hashes in zip(dictionaries, old_hashes):
            dictionary.hashes = hashes
    record = next((entry for entry in contents.entries if entry.path == key), None)
    if record is None:
        raise ValueError(f"Missing Yone BIN record {key}")
    return record


def extract_model_inputs(wad_path, project, portrait_path):
    wad = Wad(str(wad_path), {})
    members = {entry.path_hash: entry for entry in wad.files}
    texture_paths = {wad_hash(path): path for path in TEXTURES}
    raw_dir = project / "assets/client"
    decoded_dir = project / "assets/decoded"
    with wad_path.open("rb") as stream:
        toc = read_wad_member(stream, members, SUBCHUNK_TOC)
        skin = read_bin(read_wad_member(stream, members, SKIN_BIN, toc), SKIN_KEY)
        graph = read_bin(read_wad_member(stream, members, GRAPH_BIN, toc), GRAPH_KEY)
        if skin.getv("skinAnimationProperties").getv("animationGraphData") != GRAPH_KEY:
            raise ValueError("Yone skin animation graph has changed")
        properties = skin.getv("skinMeshProperties")
        props = {field: properties.getv(field) for field in (
            "skeleton", "simpleSkin", "initialSubmeshToHide",
        )}
        for field, suffix in (("skeleton", ".skl"), ("simpleSkin", ".skn")):
            expected = BASE + "yone_base" + suffix
            if path_hash(props[field]) != wad_hash(expected):
                raise ValueError(f"Yone {field} has changed")
            props[field] = expected
        props["texture"] = texture_paths[path_hash(properties.getv("texture"))]
        props["materialOverride"] = [
            {"texture": texture_paths[path_hash(override.getv("texture"))],
             "submesh": override.getv("submesh")}
            for override in properties.getv("materialOverride", []) if "texture" in override
        ]
        graph_states = graph.getv("mClipDataMap")
        selected = {}
        graph_output = {}
        for action, (state, stem) in ACTIONS.items():
            state_id = binfile.compute_binhash(state) if isinstance(state, str) else state
            state_path = state if isinstance(state, str) else f"{{{state:08x}}}"
            node = graph_states.get(state_id)
            source = BASE + "animations/" + stem + ".anm"
            resource = node.getv("mAnimationResourceData") if node is not None else None
            if resource is None or path_hash(resource.getv("mAnimationFilePath")) != wad_hash(source):
                raise ValueError(f"Yone graph state {state_path} no longer references {source}")
            selected[action] = (state_path, source, node)
            graph_output[state_path] = {
                "~class": "AtomicClipData",
                "mAnimationResourceData": {"mAnimationFilePath": source},
            }
        geometry = {props["skeleton"], props["simpleSkin"]}
        for source in sorted(geometry | {source for _, source, _ in selected.values()}):
            target = raw_dir / source
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read_wad_member(stream, members, source, toc))
        textures = {props["texture"]} | {override["texture"] for override in props["materialOverride"]}
        for source in sorted(textures):
            target = (decoded_dir / source).with_suffix(".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(BytesIO(TexConverter.tex_to_dds(read_wad_member(stream, members, source, toc)))) as image:
                image.convert("RGBA").save(target)
        if wad_hash(PORTRAIT) in members:
            with Image.open(BytesIO(TexConverter.tex_to_dds(read_wad_member(stream, members, PORTRAIT, toc)))) as source:
                portrait = source.convert("RGBA")
                portrait.thumbnail((128, 128), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (144, 144))
            canvas.alpha_composite(portrait, ((144 - portrait.width) // 2, (144 - portrait.height) // 2))
            canvas.save(portrait_path)
    write_json((decoded_dir / SKIN_BIN).with_suffix(".json"), {"objects": {SKIN_KEY: {
        "skinMeshProperties": props,
        "skinAnimationProperties": {"animationGraphData": GRAPH_KEY},
    }}})
    write_json((decoded_dir / GRAPH_BIN).with_suffix(".json"), {
        "objects": {GRAPH_KEY: {"mClipDataMap": graph_output}},
    })
    return selected


def rig_events(node, materials, joints):
    names = {binfile.compute_binhash(name): name for name in (*materials, *joints)}

    def resolve(value):
        return names.get(binfile.key_to_hash(value))

    events = []
    for event in node.getv("mEventDataMap", {}).values():
        if event.type == "JointSnapEventData":
            kind = "JointSnapEventData"
            fields = ("mJointNameToOverride", "mJointNameToSnapTo")
            payload = {field: resolve(event.getv(field)) for field in fields}
            if any(value not in joints for value in payload.values()):
                raise ValueError(f"Yone animation refers to unknown joint {event}")
        elif event.type == "SubmeshVisibilityEventData":
            kind = "SubmeshVisibilityEventData"
            payload = {}
            for field in ("mShowSubmeshList", "mHideSubmeshList"):
                changed = [resolve(value) for value in event.getv(field, [])]
                payload[field] = [name for name in changed if name in materials]
            if not any(payload.values()):
                continue
        else:
            continue
        for field in ("mStartFrame", "mEndFrame"):
            if field in event:
                payload[field] = event.getv(field)
        events.append({"__type": kind, **payload})
    return events


def prepare_outputs(project, model, selected, hidden_materials, destination):
    report = json.loads((project / "assets/preview/conversion.json").read_bytes())
    if report["failures"]:
        raise ValueError(f"HeroStudio animation conversion failed for {report['failures']}")
    blob = model.read_bytes()
    json_length = struct.unpack_from("<I", blob, 12)[0]
    gltf = json.loads(blob[20:20 + json_length])
    binary_chunk = blob[20 + json_length:]
    source_clips = {clip["name"]: clip for clip in gltf["animations"]}
    gltf["asset"]["copyright"] = "Yone model, textures, and animations © Riot Games."
    joints = {node.get("name") for node in gltf["nodes"]}
    materials = [material["name"] for material in gltf["materials"]]
    states = {}
    durations = {}
    animations = []
    for action, (state, source, node) in selected.items():
        converted = report["animation_sources"].get(source)
        if converted not in source_clips:
            raise ValueError(f"HeroStudio did not convert {action}: {source}")
        clip = source_clips[converted]
        duration = max(gltf["accessors"][sampler["input"]]["max"][0] for sampler in clip["samplers"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"Invalid duration for {action}: {duration}")
        durations[action] = duration
        animations.append({**clip, "name": action})
        states[state] = {"clip": action, "source_anm": source, "events": rig_events(node, materials, joints)}
    gltf["animations"] = animations
    document = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    document += b" " * (-len(document) % 4)
    header = struct.pack("<4sIIII", b"glTF", 2, 20 + len(document) + len(binary_chunk), len(document), 0x4E4F534A)
    (destination / "yone.glb").write_bytes(header + document + binary_chunk)
    write_json(destination / "actions.json", durations)
    write_json(destination / "rig-events.json", {
        "source": "Installed League of Legends Yone.wad.client, classic skin",
        "frames_per_second": 30,
        "hidden_materials": hidden_materials,
        "states": states,
    })
    return durations


def import_yone(wad_path, archive_path):
    with TemporaryDirectory(prefix=".yone-import-", dir=DESTINATION.parent) as temporary:
        stage = Path(temporary)
        convert = load_converter(stage, archive_path)
        project = stage / "project"
        selected = extract_model_inputs(wad_path, project, stage / "yone-portrait.png")
        profile = {"client_import": {"champion": "yone", "skin_id": 0}}
        model = project / convert(project, profile)
        durations = prepare_outputs(project, model, selected, profile["hidden_materials"], stage)
        DESTINATION.mkdir(exist_ok=True)
        for name in ("actions.json", "rig-events.json", "yone.glb"):
            (stage / name).replace(DESTINATION / name)
        portrait = stage / "yone-portrait.png"
        if portrait.is_file():
            portrait.replace(DESTINATION / portrait.name)
    return durations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wad", required=True, type=Path, help="Installed Yone.wad.client")
    parser.add_argument("--herostudio-archive", required=True, type=Path,
                        help="HeroStudio release ZIP pinned in docs/sources.lock.json")
    args = parser.parse_args()
    try:
        durations = import_yone(args.wad, args.herostudio_archive)
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        parser.exit(1, f"Yone import failed: {exc}\n")
    print(f"Imported {len(durations)} Yone clips to {DESTINATION}")


if __name__ == "__main__":
    main()
