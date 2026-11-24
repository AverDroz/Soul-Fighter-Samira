"""Convert local MVP T1 Miss Fortune Wwise banks to native Isaac PCM samples."""

import argparse
from hashlib import sha256
from pathlib import Path
from shutil import copyfile
import re
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import wave
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from cdtb.wad import Wad

from import_yone_assets import archive_hash, wad_hash, write_json
from import_yone_emote_audio import extract_wem, WWISER_SHA256, VGMSTREAM_SHA256


PROJECT = Path(__file__).resolve().parents[1]
MOD = PROJECT / "src/samira-testroom/mod"
RESOURCE_DIR = MOD / "resources/sfx/samira-items"
LOCK = PROJECT / "docs/miss-fortune-audio.lock.json"

# Pin the same numbered Wwise switch branch for W and both R layers.
SKIN_SWITCH = "[2731286056=1307359308]"
SFX = "Play_sfx_MissFortuneSkin69_"
VOICE = "Play_vo_MissFortuneSkin69_"
SOUNDS = {
    "Attack": (SFX + "MissFortuneBasicAttack_OnCast",),
    "Q": (SFX + "MissFortuneRicochetShot_OnCast",),
    "Q Hit": (SFX + "MissFortuneRicochetShot_OnHit",),
    "Q Voice": (VOICE + "MissFortuneRicochetShot_cast3D",),
    "W": (SFX + "MissFortuneViciousStrikes_OnCast",),
    "E": (SFX + "MissFortuneScattershot_OnCast",),
    "E Rain": (SFX + "MissFortuneScattershot_ground_buffactivate",),
    "E Voice": (VOICE + "MissFortuneScatterShot_cast3D",),
    "R": (SFX + "MissFortuneBulletTime_OnCast",),
    "R Barrage": (SFX + "MissFortuneBulletTime_Loop",),
    "R Wave": (SFX + "MissFortuneRShotExtra_OnMissileLaunch",),
    "R Voice": (VOICE + "MissFortuneBulletTime_cast3D",),
    "Dance": (SFX + "Dance3D_buffactivate",),
    "Joke": (SFX + "Joke3D_buffactivate", VOICE + "Joke3DGeneral"),
    "Taunt": (SFX + "Taunt3D_buffactivate", VOICE + "Taunt3DGeneral"),
    "Laugh": (SFX + "Laugh3D_buffactivate", VOICE + "Laugh3DGeneral"),
    "Recall": (SFX + "Recall3D_buffactivate",),
    # The animation graph uses the shared base start/loop names. The Skin69
    # sound bank maps those cues to its own Skin69 events and media.
    "Homeguard Start": (SFX + "Homeguard3D_buffactivate",),
    "Homeguard Gun": (SFX + "Homeguard3D_gun",),
    "Homeguard Onboard": (SFX + "Homeguard3D_onboard",),
    "Homeguard Loop": (SFX + "Homeguard3D_loop",),
    "Homeguard Exit": (SFX + "HomeguardToRun_buffactivate",),
    "Joke Cast": (SFX + "Joke3D_cast",),
    "Joke Loop": (SFX + "Joke3D_loop",),
    "Death": (SFX + "Death3D_cast",),
    "Death Voice": (VOICE + "Death3D",),
    "Respawn": (SFX + "Respawn3D_buffactivate",),
    "Respawn Voice": (VOICE + "Respawn2DGeneral",),
    "Taunt Intro": (SFX + "Taunt3D_cast_anim",),
}


def embedded_media(bank):
    """Return Wwise DIDX entries backed by a bank's DATA chunk."""
    chunks = {}
    position = 0
    while position + 8 <= len(bank):
        name, length = struct.unpack_from("<4sI", bank, position)
        position += 8
        chunks[name] = bank[position:position + length]
        position += length
    index, data = chunks.get(b"DIDX", b""), chunks.get(b"DATA", b"")
    for media_id, start, length in struct.iter_unpack("<III", index):
        end = start + length
        if end > len(data) or data[start:start + 4] != b"RIFF":
            raise ValueError(f"Invalid embedded Wwise media {media_id}")
        yield f"{media_id}.wem", data[start:end]


def extract_skin(wad, folder, category, locale=None):
    archive = Wad(str(wad), {})
    members = {entry.path_hash: entry for entry in archive.files}
    base = f"assets/sounds/wwise2016/{category}/"
    if locale:
        base += locale + "/"
    base += "characters/missfortune/skins/skin69/"
    provenance = {}
    with wad.open("rb") as stream:
        for suffix in ("audio.bnk", "audio.wpk", "events.bnk"):
            filename = f"missfortune_skin69_{category.lower()}_{suffix}"
            path = base + filename
            entry = members.get(wad_hash(path))
            if entry is None:
                raise ValueError(f"Missing Skin69 archive member {path}")
            content = entry.read_data(stream, None)
            if content is None or len(content) != entry.size:
                raise ValueError(f"Could not read Skin69 archive member {path}")
            provenance[path] = sha256(content).hexdigest()
            if suffix.endswith(".wpk"):
                extract_wem(content, folder)
            else:
                (folder / filename).write_bytes(content)
                for name, media in embedded_media(content):
                    target = folder / name
                    if target.exists() and target.read_bytes() != media:
                        raise ValueError(f"Conflicting Wwise media {name}")
                    target.write_bytes(media)
    return {"file": wad.name, "sha256": archive_hash(wad), "members": provenance}


def event_playlists(event, folder):
    files = sorted(file for file in folder.glob(event + "*.txtp")
                   if file.stem == event or file.stem.startswith(event + " "))
    if event in SOUNDS["W"] + SOUNDS["R"] + SOUNDS["R Barrage"]:
        files = [file for file in files if SKIN_SWITCH in file.name]
    if not files:
        raise ValueError(f"Missing Wwise event {event}")
    return files


def run(command, **kwargs):
    subprocess.run(command, check=True, timeout=60, **kwargs)


def playlist_media(playlist):
    return re.findall(r"(?m)^\s*\.\./banks/(\d+\.wem)\b",
                      playlist.read_text(encoding="utf-8"))


def decode(playlist, media, decoder, temporary):
    if not media or any(not (temporary / "banks" / name).is_file() for name in media):
        raise ValueError(f"Missing media for {playlist.name}")
    target = temporary / (playlist.stem + ".wav")
    if target.exists():
        return target
    run([str(decoder), "-i", "-W", "4", "-o", str(target), str(playlist)],
        stdout=subprocess.DEVNULL)
    return target


def export_wav(inputs, target, ffmpeg):
    command = [ffmpeg, "-nostdin", "-loglevel", "error"]
    for source in inputs:
        command.extend(("-i", str(source)))
    # The event renderer can produce float peaks above full scale. Limit only
    # those peaks before converting to PCM and keep the original sound length.
    limiter = "alimiter=limit=0.9:level=0:latency=1"
    if len(inputs) > 1:
        command.extend(("-filter_complex", f"amix=inputs=2:weights='0.65 1':normalize=0,{limiter}"))
    else:
        command.extend(("-af", limiter))
    command.extend(("-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(target)))
    run(command)
    with wave.open(str(target), "rb") as audio:
        frames = audio.getnframes()
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 44100):
            raise ValueError(f"Wrong PCM format for {target.name}")
        if frames == 0 or not any(audio.readframes(frames)):
            raise ValueError(f"Invalid silent audio {target.name}")
    return frames


def update_xml(samples):
    xml_path = MOD / "content/sounds.xml"
    root = ET.parse(xml_path).getroot()
    for element in list(root.findall("sound")):
        if element.get("name") in samples:
            root.remove(element)
    for name, variants in samples.items():
        sound = ET.SubElement(root, "sound", name=name)
        for variant in variants:
            ET.SubElement(sound, "sample", weight="1", path=variant["file"])
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)


def import_audio(args):
    for asset, expected in ((args.wwiser, WWISER_SHA256),
                            (args.vgmstream_archive, VGMSTREAM_SHA256)):
        if archive_hash(asset) != expected:
            raise ValueError(f"Unexpected audio converter release: {asset.name}")
    with TemporaryDirectory(prefix="mf-audio-", dir=args.scratch_dir) as temporary:
        stage = Path(temporary)
        banks = stage / "banks"
        banks.mkdir()
        sources = [extract_skin(args.sfx_wad, banks, "SFX"),
                   extract_skin(args.voice_wad, banks, "VO", "en_us")]
        events = list(dict.fromkeys(event for sound in SOUNDS.values() for event in sound))
        (banks / "wwnames.txt").write_text("\n".join(events) + "\n", encoding="ascii")
        run([sys.executable, str(args.wwiser.resolve()), "-g", "-gd", "-d", "none", "-gbs",
             "-go", "../txtp", "-gw", "../banks", "-gra", "*.bnk", "-gf", *events], cwd=banks)
        decoder_folder = stage / "decoder"
        with ZipFile(args.vgmstream_archive) as archive:
            for name in archive.namelist():
                if name == "vgmstream-cli.exe" or re.fullmatch(r"[\w.-]+\.dll", name):
                    archive.extract(name, decoder_folder)
        decoder = decoder_folder / "vgmstream-cli.exe"
        samples = {}
        for action, event_names in SOUNDS.items():
            choices = [event_playlists(event, stage / "txtp") for event in event_names]
            variants = []
            for index in range(max(map(len, choices))):
                playlists = [options[index % len(options)] for options in choices]
                media_lists = [playlist_media(playlist) for playlist in playlists]
                inputs = [decode(playlist, media, decoder, stage)
                          for playlist, media in zip(playlists, media_lists)]
                filename = f"mf_skin69_{action.lower().replace(' ', '_')}_{index + 1}.wav"
                output = stage / filename
                frames = export_wav(inputs, output, args.ffmpeg)
                variants.append({
                    "file": filename,
                    "frames": frames,
                    "sha256": archive_hash(output),
                    "playlists": {playlist.stem: media
                                  for playlist, media in zip(playlists, media_lists)},
                })
            samples[f"Miss Fortune {action}"] = variants
        for variants in samples.values():
            for variant in variants:
                name = variant["file"]
                copyfile(stage / name, RESOURCE_DIR / name)
        update_xml(samples)
        write_json(LOCK, {
            "copyright": "MVP T1 Miss Fortune voice and sound effects © Riot Games.",
            "voice_locale": "en_US",
            "pcm": {"sample_rate": 44100, "bits_per_sample": 16, "channels": 1},
            "source_archives": sources,
            "tools": {"wwiser.pyz": WWISER_SHA256, "vgmstream-win64.zip": VGMSTREAM_SHA256,
                      "ffmpeg": subprocess.check_output([args.ffmpeg, "-version"], text=True).splitlines()[0]},
            "samples": samples,
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sfx-wad", type=Path, required=True)
    parser.add_argument("--voice-wad", type=Path, required=True)
    parser.add_argument("--wwiser", type=Path, required=True)
    parser.add_argument("--vgmstream-archive", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--scratch-dir", type=Path, default=PROJECT.parent,
                        help="Writable folder with a short path for wwiser filenames")
    args = parser.parse_args()
    try:
        import_audio(args)
    except (OSError, ValueError, struct.error, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Miss Fortune audio import failed: {exc}\n")


if __name__ == "__main__":
    main()
