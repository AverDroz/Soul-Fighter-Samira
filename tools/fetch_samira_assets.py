"""Extract Skin30 from Riot's Samira WAD and convert it with HeroStudio.

Run from the repository root. Uses cdtb, Pillow, NumPy, requests and the
bundled HeroStudio. Downloads only the pinned Samira champion archive.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest, sha256
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import sys
from time import sleep

import requests
from cdtb.export import TexConverter
from cdtb.patcher import PatcherManifest, PatcherStorage
from cdtb.tools import zstd_decompress
from cdtb.wad import MalformedSubchunkError, Wad
from PIL import Image
from xxhash import xxh64_intdigest

ROOT = Path.cwd()
WORK = ROOT / "work/asset-research"
OUTPUT = ROOT / "assets/samira-soul-fighter"
STUDIO = WORK / "studio"
WAD_FILE = WORK / "Samira.wad.client"
CDRAGON = "https://raw.communitydragon.org/16.22/game/"
RIOT_MANIFEST = "https://lol.dyn.riotcdn.net/channels/public/releases/6EDAD6B3C9806CB9.manifest"
KHADA = "https://cdn.modelviewer.lol/lol/models/samira/360030/model-compressed.wasm?c=1"
WAD_SHA256 = "46de520169a641ea2b871aab56a56af09e754258f778d55042feb52a83474142"
SKIN = "data/characters/samira/skins/skin30.bin"
GRAPH = "data/characters/samira/animations/skin30.bin"
PREFIX = "assets/characters/samira/skins/skin30/"


def write_bytes(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_json(path, data):
    write_bytes(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode())


def digest(content):
    return sha256(content).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def download_wad_chunk(chunk):
    base = PatcherStorage.URL_BASE
    bundle = f"{base}channels/public/bundles/{chunk.bundle.bundle_id:016X}.bundle"
    start = chunk.offset
    end = start + chunk.size - 1
    headers = {"Range": f"bytes={start}-{end}"}
    for attempt in range(4):
        try:
            with requests.get(bundle, headers=headers, timeout=25, stream=True) as response:
                response.raise_for_status()
                if response.status_code != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/"):
                    raise ValueError(f"Invalid CDN range response for {bundle} {headers}")
                data = zstd_decompress(response.content)
                if len(data) != chunk.target_size:
                    raise ValueError(f"Invalid decompressed size for {bundle} {headers}")
                return data
        except (requests.RequestException, ValueError):
            if attempt == 3:
                raise
            sleep(attempt + 1)


def fetch_wad():
    if WAD_FILE.is_file() and file_hash(WAD_FILE) == WAD_SHA256:
        return
    WORK.mkdir(parents=True, exist_ok=True)
    storage = PatcherStorage(str(WORK / "cdn"))
    manifest_path = storage.download_manifest(RIOT_MANIFEST)
    manifest = PatcherManifest(storage.fspath(manifest_path))
    champion = manifest.files["DATA/FINAL/Champions/Samira.wad.client"]
    partial = WAD_FILE.with_suffix(".partial")
    with ThreadPoolExecutor(max_workers=20) as pool, partial.open("wb") as output:
        for index, data in enumerate(pool.map(download_wad_chunk, champion.chunks), start=1):
            output.write(data)
            if index % 200 == 0:
                print(f"{index}/{len(champion.chunks)} archive chunks", flush=True)
    if partial.stat().st_size != champion.size or file_hash(partial) != WAD_SHA256:
        raise ValueError("Downloaded WAD does not match the pinned SHA256")
    partial.replace(WAD_FILE)


def load_objects(asset):
    output = OUTPUT / "decoded" / (asset + ".json")
    if not output.is_file():
        response = requests.get(CDRAGON + asset + ".json", timeout=30)
        response.raise_for_status()
        write_bytes(output, response.content)
    objects = json.loads(output.read_bytes())
    return {name: value for name, value in objects.items() if name != "__linked"}


def remap_classes(value):
    if isinstance(value, dict):
        return {("~class" if key == "__type" else key): remap_classes(child)
                for key, child in value.items()}
    if isinstance(value, list):
        return [remap_classes(child) for child in value]
    return value


def gather_paths(skin, graph):
    skin_record = skin["Characters/Samira/Skins/Skin30"]["skinMeshProperties"]
    wanted = {SKIN, GRAPH, skin_record["skeleton"].lower(), skin_record["simpleSkin"].lower()}
    wanted.update(x.lower() for x in re.findall(r'assets/[^" ]+\.anm', json.dumps(graph), re.I))
    wanted.update(x.lower() for x in re.findall(re.escape(PREFIX) + r'[^"/ ]+_tx_cm\.tex', json.dumps(skin), re.I))
    return wanted


def toc_for(stream, entries, textures):
    # The archive stores its subchunk table as one WAD member. Validate an
    # unknown member against all wanted chunked textures' xxh3 checksums.
    count = max(e.first_subchunk_index + e.subchunk_count for e in textures)
    candidates = [e for e in entries if e.size >= 16 * count and e.size % 16 == 0
                  and e.type in (0, 3)]
    for entry in sorted(candidates, key=lambda e: e.size):
        toc = entry.read_data(stream)
        try:
            for texture in textures:
                texture.read_data(stream, toc)
        except MalformedSubchunkError:
            continue
        return toc
    raise ValueError("Could not find the WAD subchunk table")


def extract(wanted):
    wad = Wad(str(WAD_FILE), {})
    by_hash = {entry.path_hash: entry for entry in wad.files}
    entries = {name: by_hash[xxh64_intdigest(name.encode())] for name in sorted(wanted)}
    hashes = {}
    with WAD_FILE.open("rb") as stream:
        toc = toc_for(stream, wad.files, [e for e in entries.values() if e.type == 4])
        for name, entry in entries.items():
            content = entry.read_data(stream, toc)
            if len(content) != entry.size:
                raise ValueError(f"WAD size mismatch: {name}")
            write_bytes(OUTPUT / "original" / name, content)
            hashes[name] = {"size": len(content), "sha256": digest(content)}
            suffix = Path(name).suffix
            if suffix in (".anm", ".skl", ".skn"):
                write_bytes(STUDIO / "assets/client" / name, content)
            elif suffix == ".tex":
                png = (STUDIO / "assets/decoded" / name).with_suffix(".png")
                png.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(BytesIO(TexConverter.tex_to_dds(content))) as image:
                    image.save(png)
    return hashes


def convert(skin, graph):
    sys.path.insert(0, str(ROOT / "vendor/herostudio/Hero-Studio-0.2.33/app"))
    from client_model import convert as studio_convert

    for original, objects in ((SKIN, skin), (GRAPH, graph)):
        target = (STUDIO / "assets/decoded" / original).with_suffix(".json")
        write_json(target, {"objects": remap_classes(objects)})
    profile = {"client_import": {"champion": "samira", "skin_id": 30}}
    result = studio_convert(STUDIO, profile)
    report = json.loads((STUDIO / "assets/preview/conversion.json").read_bytes())
    if report["failures"]:
        raise ValueError(f"Failed ANM conversion: {report['failures']}")
    model = OUTPUT / "soul-fighter-samira.glb"
    shutil.copy2(STUDIO / result, model)
    return model, report, profile


def write_rig_events(graph, report):
    graph_key = "Characters/Samira/Animations/Skin30"
    clips = graph[graph_key]["mClipDataMap"]
    states = {}
    for state, node in clips.items():
        asset = node.get("mAnimationResourceData", {}).get("mAnimationFilePath", "").lower()
        if asset not in report["animation_sources"]:
            continue
        events = [dict(event, name=name) for name, event in node.get("mEventDataMap", {}).items()
                  if event["__type"] in ("JointSnapEventData", "SubmeshVisibilityEventData")]
        states[state] = {"clip": report["animation_sources"][asset], "events": events}
    target = OUTPUT / "rig-events.json"
    write_json(target, {"source": CDRAGON + GRAPH + ".json", "frames_per_second": 30,
                        "states": states})
    return {"file": target.name, "sha256": file_hash(target)}


def main():
    fetch_wad()
    skin, graph = load_objects(SKIN), load_objects(GRAPH)
    inventory = extract(gather_paths(skin, graph))
    model, report, profile = convert(skin, graph)
    expected_clips = sum(name.endswith(".anm") for name in inventory)
    if report["animations"] != expected_clips:
        raise ValueError(f"Converted {report['animations']} of {expected_clips} animations")
    rig_events = write_rig_events(graph, report)
    khada = OUTPUT / "khada.glb"
    reference = {"url": KHADA}
    if khada.is_file():
        reference.update(file=khada.name, sha256=file_hash(khada))
    write_json(OUTPUT / "manifest.json", {
        "name": "Soul Fighter Samira",
        "champion_id": 360,
        "skin_id": 30,
        "full_skin_id": 360030,
        "copyright": "League of Legends character, artwork and animations © Riot Games.",
        "patch": "16.22.8348910",
        "riot_manifest": RIOT_MANIFEST,
        "wad_client_path": "DATA/FINAL/Champions/Samira.wad.client",
        "wad_sha256": file_hash(WAD_FILE),
        "path_metadata_source": CDRAGON,
        "original_files": inventory,
        "original_file_counts": Counter(Path(name).suffix for name in inventory),
        "converted_model": {
            "file": model.name, "sha256": file_hash(model), "converter": "HeroStudio 0.2.33",
            "default_hidden_materials": profile["hidden_materials"],
            **report,
        },
        "rig_events": rig_events,
        "khada_reference": reference,
    })
    print(model, model.stat().st_size, report["animations"], profile["hidden_materials"])


if __name__ == "__main__":
    main()

