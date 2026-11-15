"""Export original Soul Fighter audio selected by Wwise event.

Prepare wwiser v20260808 and vgmstream r2168 in work/asset-research/audio
(wwiser.pyz and vgm/vgmstream-cli.exe). Run with fetch_samira_assets.py dependencies.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import struct
import subprocess
import sys
import wave

from fetch_samira_assets import (
    OUTPUT, RIOT_MANIFEST, SKIN, WAD_FILE, WAD_SHA256, WORK, PatcherManifest,
    PatcherStorage, Wad, download_wad_chunk, fetch_wad, file_hash, load_objects,
    write_bytes, write_json, xxh64_intdigest,
)


DEST = OUTPUT / "audio"
BUILD = WORK / "audio"
RU_ARCHIVE = "DATA/FINAL/Champions/Samira.ru_RU.wad.client"
RU_SHA256 = "dd23c4808f7790489c5d613927e6d0b186e6d502c0225398aef0c2dda598a991"
SFX = {
    "attack": "SamiraBasicAttack_OnCast",
    "attack_hit": "SamiraBasicAttack_OnHit",
    "melee": "SamiraBasicAttackMelee_OnCast",
    "melee_hit": "SamiraBasicAttackMelee_OnHit",
    "q": "SamiraQGun_OnCast",
    "q_hit": "SamiraQGun_OnHit",
    "qmelee": "SamiraQSword_OnCast",
    "qmelee_hit": "SamiraQSword_OnHit",
    "w": "SamiraW_OnCast",
    "w_hit": "SamiraW_hit",
    "block": "SamiraW_hit_block_sml",
    "e": "SamiraE_cast",
    "e_hit": "SamiraE_hit",
    "eq": "SamiraQBufferedSword_OnCast",
    "eq_burst": "SamiraQBufferedSword_buffactivate",
    "eq_hit": "SamiraQBufferedSword_hit",
    "r": "SamiraR_OnCast",
    "r_shot": "SamiraRMissile_OnMissileCast",
    "r_hit": "SamiraRMissile_OnHit",
}
VOICE = {
    "voice_move": "Move2DStandard",
    "voice_attack": "Attack2DGeneral",
    "voice_q": "SamiraQGun_cast3D",
    "voice_qmelee": "SamiraQSword_cast3D",
    "voice_w": "SamiraW_cast3D",
    "voice_e": "SamiraE_cast3D",
    "voice_r": "SamiraR_cast3D",
}


def fetch_russian_wad():
    path = BUILD / "Samira.ru_RU.wad.client"
    if path.is_file() and file_hash(path) == RU_SHA256:
        return path
    storage = PatcherStorage(str(WORK / "cdn"))
    manifest = PatcherManifest(storage.fspath(storage.download_manifest(RIOT_MANIFEST)))
    archive = manifest.files[RU_ARCHIVE]
    partial = path.with_suffix(".partial")
    with ThreadPoolExecutor(max_workers=20) as pool, partial.open("wb") as output:
        for data in pool.map(download_wad_chunk, archive.chunks):
            output.write(data)
    if partial.stat().st_size != archive.size or file_hash(partial) != RU_SHA256:
        raise ValueError("Russian Samira WAD checksum mismatch")
    partial.replace(path)
    return path


def extract_bank_paths(archive, paths):
    wad = Wad(str(archive), {})
    index = {entry.path_hash: entry for entry in wad.files}
    records = {}
    with archive.open("rb") as stream:
        for name in paths:
            path = name.lower()
            entry = index[xxh64_intdigest(path.encode())]
            data = entry.read_data(stream)
            if len(data) != entry.size:
                raise ValueError(f"Incorrect WAD size for {name}")
            file = BUILD / "banks" / Path(path).name
            write_bytes(file, data)
            records[path] = {"sha256": file_hash(file), "size": len(data)}
    return records


def extract_wpk(path):
    data = path.read_bytes()
    magic, version, count = struct.unpack_from("<4sII", data)
    if (magic, version) != (b"r3d2", 1):
        raise ValueError(f"Unsupported WPK header in {path}")
    offsets = struct.unpack_from(f"<{count}I", data, 12)
    for offset in offsets:
        start, size, length = struct.unpack_from("<3I", data, offset)
        name = data[offset + 12:offset + 12 + length * 2].decode("utf-16le")
        if not re.fullmatch(r"\d+\.wem", name) or start + size > len(data):
            raise ValueError(f"Invalid WPK entry in {path}: {name}")
        write_bytes(BUILD / "wem" / name, data[start:start + size])


SOURCE = re.compile(r"^\s*.+[\\/]([\w.-]+\.(?:bnk|wem))\b(.*)$")
BANK_INDEX = re.compile(r"#s(\d+).*?##(\d+)\.wem")


def collect_variants(event):
    files = sorted(
        (path for path in (BUILD / "txtp").glob(event + "*.txtp")
         if path.stem == event or path.stem.startswith(event + " ")),
        key=lambda path: (" {d}" in path.stem, path.stem),
    )
    if not files:
        raise ValueError(f"Missing Wwise event {event}")
    # Keep one switch branch and up to four original variants. Sequential or
    # layered events yield unique source samples from that same authored event.
    variants = []
    for line in files[0].read_text(encoding="utf-8-sig").splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = SOURCE.match(line)
        if not match:
            continue
        name, options = match.groups()
        if name.endswith(".bnk"):
            bank_index = BANK_INDEX.search(options)
            if not bank_index:
                raise ValueError(f"Missing index or media ID for {line}")
            index, media = map(int, bank_index.groups())
            source = BUILD / "banks" / name
        else:
            index, media = None, int(Path(name).stem)
            source = BUILD / "wem" / name
        attempt = (source, index, media)
        if attempt not in variants:
            variants.append(attempt)
    if not variants:
        raise ValueError(f"No source samples for {event}")
    return variants[:4]


def export_events(vgmstream, events):
    records = {}
    for role, event in events.items():
        records[role] = []
        for number, (bank, index, wem) in enumerate(collect_variants(event), 1):
            if not bank.is_file():
                raise FileNotFoundError(bank)
            file = f"{role}-{number}.wav"
            path = DEST / file
            options = ["-s", str(index)] if index else []
            subprocess.run([str(vgmstream), "-i", *options, "-o", str(path), str(bank)],
                           check=True, stdout=subprocess.DEVNULL)
            with wave.open(str(path), "rb") as audio:
                channels, width, rate, frames = audio.getparams()[:4]
                if width != 2 or channels not in (1, 2) or rate <= 0 or frames <= 0:
                    raise ValueError(f"Invalid output for {event}")
            records[role].append({
                "file": file, "event": event, "wem_id": wem, "source_file": bank.name,
                "bank_stream_index": index, "seconds": round(frames / rate, 4),
                "sha256": file_hash(path),
            })
    return records


def main():
    wwiser = BUILD / "wwiser.pyz"
    vgmstream = BUILD / "vgm/vgmstream-cli.exe"
    for tool in (wwiser, vgmstream):
        if not tool.is_file():
            raise FileNotFoundError(tool)
    fetch_wad()
    russian = fetch_russian_wad()
    units = load_objects(SKIN)["Characters/Samira/Skins/Skin30"]["skinAudioProperties"]["bankUnits"]
    catalogs = {unit["name"]: unit for unit in units}
    sound_bank, voice_bank = (catalogs[f"Samira_Skin30_{suffix}"] for suffix in ("SFX", "VO"))
    sfx_files = extract_bank_paths(WAD_FILE, sound_bank["bankPath"])
    # The official localized WAD retains the nominal en_US virtual paths.
    voice_files = extract_bank_paths(russian, voice_bank["bankPath"])
    for pack in (BUILD / "banks").glob("*.wpk"):
        extract_wpk(pack)

    names = [name for bank in (sound_bank, voice_bank) for name in bank["events"]]
    write_bytes(BUILD / "banks/wwnames.txt", ("\n".join(names) + "\n").encode())
    events = {role: f"Play_{category}_SamiraSkin30_{event}"
              for category, group in (("sfx", SFX), ("vo", VOICE)) for role, event in group.items()}
    if missing := set(events.values()) - set(names):
        raise ValueError(f"Events absent from Riot skin BIN: {sorted(missing)}")
    subprocess.run([sys.executable, str(wwiser), "-g", "-gd", "-d", "none",
                    "-go", str(BUILD / "txtp"), "-gw", str(BUILD / "wem"),
                    str(BUILD / "banks/*.bnk")], check=True)
    DEST.mkdir(parents=True, exist_ok=True)
    samples = export_events(vgmstream, events)
    write_json(DEST / "manifest.json", {
        "source": "Riot Games League of Legends, Soul Fighter Samira (Skin30)",
        "riot_manifest": RIOT_MANIFEST,
        "skin_bin": SKIN,
        "sfx": {"archive": "DATA/FINAL/Champions/Samira.wad.client",
                "sha256": WAD_SHA256, "banks": sfx_files},
        "voice": {"archive": RU_ARCHIVE, "sha256": RU_SHA256,
                  "locale": "ru_RU", "banks": voice_files},
        "tools": {
            "wwiser": "https://github.com/bnnm/wwiser/releases/tag/v20260808",
            "vgmstream": "https://github.com/vgmstream/vgmstream/releases/tag/r2168",
        },
        "samples": samples,
    })
    print(f"Exported {sum(map(len, samples.values()))} clips in {len(samples)} event roles")


if __name__ == "__main__":
    main()
