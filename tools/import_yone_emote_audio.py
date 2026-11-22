"""Extract local Yone emote audio through the project's Wwise decoders."""

import argparse
from pathlib import Path
import re
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import wave
from zipfile import ZipFile

from cdtb.wad import Wad

from import_yone_assets import DESTINATION, archive_hash, read_wad_member, write_json


WWISER_SHA256 = "f4ba1368895adab285f27fa37b142e5da805bcc6fb77e8daba282dac65d89411"
VGMSTREAM_SHA256 = "692d45070852a35c1fa42726aa3c9de528e44eec925d37d99b1074256b99a229"
WWISE = "ASSETS/Sounds/Wwise2016/"
BASE = "Characters/Yone/Skins/Base/Yone_Base_"
SFX = {
    "joke": "Play_sfx_Yone_Joke3D_buffactivate",
    "taunt": "Play_sfx_Yone_Taunt3D_buffactivate",
    "dance": "Play_sfx_Yone_Dance3D_in",
    "dance_loop": "Play_sfx_Yone_Dance3D_loop",
    "laugh": "Play_sfx_Yone_Laugh3D_buffactivate",
}
VOICE = {
    "joke": "Play_vo_Yone_Joke3DGeneral_in",
    "taunt": "Play_vo_Yone_Taunt3DGeneral",
    "laugh": "Play_vo_Yone_Laugh3DGeneral",
}


def extract_wem(package, folder):
    magic, version, count = struct.unpack_from("<4sII", package)
    if (magic, version) != (b"r3d2", 1):
        raise ValueError("Unsupported Yone voice pack header")
    for offset in struct.unpack_from(f"<{count}I", package, 12):
        start, size, length = struct.unpack_from("<3I", package, offset)
        name = package[offset + 12:offset + 12 + length * 2].decode("utf-16le")
        if not re.fullmatch(r"[0-9]+\.wem", name) or start + size > len(package):
            raise ValueError(f"Invalid Yone voice pack entry {name!r}")
        (folder / name).write_bytes(package[start:start + size])


def extract_banks(wad_path, folder, prefix, files):
    members = {entry.path_hash: entry for entry in Wad(str(wad_path), {}).files}
    with wad_path.open("rb") as stream:
        for file in files:
            path = prefix + file
            data = read_wad_member(stream, members, path)
            if path.endswith(".wpk"):
                extract_wem(data, folder)
            else:
                (folder / Path(path).name).write_bytes(data)


def decode_event(event, stage, decoder):
    txtp = stage / "txtp" / (event + ".txtp")
    if not txtp.exists():
        # wwiser emits one playlist per random selection with -gra. Use the
        # first declared choice for a reproducible WAV.
        alternatives = sorted(txtp.parent.glob(event + " {r*}.txtp"))
        if not alternatives:
            raise ValueError(f"Audio event absent from the local Yone banks: {event}")
        txtp = alternatives[0]
    target = stage / (event + ".wav")
    subprocess.run([str(decoder), "-i", "-W", "4", "-o", str(target), str(txtp)],
                   check=True, stdout=subprocess.DEVNULL, timeout=30)
    return target


def make_wav(sources, target, ffmpeg):
    command = [ffmpeg, "-nostdin", "-loglevel", "error"]
    for source in sources:
        command.extend(("-i", str(source)))
    limiter = "alimiter=limit=0.85:level=0:latency=1"
    if len(sources) == 2:
        # Put English VO over the original SFX; decode in float to keep the
        # Wwise transients intact before limiting the combined PCM waveform.
        command.extend(("-filter_complex", f"amix=inputs=2:weights='0.55 0.80':normalize=0,{limiter}"))
    else:
        command.extend(("-af", f"volume=0.75,{limiter}"))
    command.extend(("-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(target)))
    subprocess.run(command, check=True, timeout=30)
    with wave.open(str(target), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    if duration <= 0:
        raise ValueError(f"Decoded empty Yone audio: {target.name}")
    return duration


def import_audio(wad_path, voice_wad, wwiser, vgmstream_zip, ffmpeg):
    for asset, digest in ((wwiser, WWISER_SHA256), (vgmstream_zip, VGMSTREAM_SHA256)):
        if archive_hash(asset) != digest:
            raise ValueError(f"Unexpected audio converter release: {asset.name}")
    with TemporaryDirectory(prefix=".yone-audio-", dir=DESTINATION.parent) as temporary:
        stage = Path(temporary)
        banks = stage / "banks"
        banks.mkdir()
        tools = stage / "vgmstream"
        with ZipFile(vgmstream_zip) as archive:
            for name in archive.namelist():
                if name == "vgmstream-cli.exe" or re.fullmatch(r"[\w.-]+\.dll", name):
                    archive.extract(name, tools)
        extract_banks(wad_path, banks, WWISE + "SFX/" + BASE, ("SFX_audio.bnk", "SFX_events.bnk"))
        events = list(SFX.values())
        if voice_wad is not None:
            extract_banks(voice_wad, banks, WWISE + "VO/en_US/" + BASE,
                          ("VO_audio.bnk", "VO_events.bnk", "VO_audio.wpk"))
            events.extend(VOICE.values())
        (banks / "wwnames.txt").write_text("\n".join(events) + "\n", encoding="ascii")
        subprocess.run([sys.executable, str(wwiser.resolve()), "-g", "-gd", "-d", "none",
                        "-go", "../txtp", "-gw", "../banks", "-gra",
                        "*.bnk", "-gf", *events], cwd=banks, check=True, timeout=30)
        decoder = tools / "vgmstream-cli.exe"
        samples = {}
        for action, sound in SFX.items():
            event_names = [sound]
            if voice_wad is not None and action in VOICE:
                event_names.append(VOICE[action])
            sources = [decode_event(event, stage, decoder) for event in event_names]
            file = action + ".wav"
            duration = make_wav(sources, stage / file, ffmpeg)
            samples[action] = [{"file": file, "duration_seconds": duration, "events": event_names}]
        write_json(stage / "manifest.json", {
            "copyright": "Yone voice and sound effects © Riot Games.",
            "source": "Installed League of Legends classic Yone WADs",
            "voice_locale": "en_US" if voice_wad is not None else None,
            "samples": samples,
        })
        output = DESTINATION / "audio"
        output.mkdir(parents=True, exist_ok=True)
        for name in (*(action + ".wav" for action in SFX), "manifest.json"):
            (stage / name).replace(output / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wad", required=True, type=Path, help="Installed Yone.wad.client")
    parser.add_argument("--voice-wad", type=Path, help="Optional installed Yone.en_US.wad.client")
    parser.add_argument("--wwiser", required=True, type=Path, help="wwiser.pyz from v20260808")
    parser.add_argument("--vgmstream-archive", required=True, type=Path, help="vgmstream-win64.zip from r2168")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable (default: on PATH)")
    args = parser.parse_args()
    try:
        import_audio(args.wad, args.voice_wad, args.wwiser, args.vgmstream_archive, args.ffmpeg)
    except (OSError, ValueError, struct.error, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Yone audio import failed: {exc}\n")
    print(f"Imported {len(SFX)} Yone emote sounds to {DESTINATION / 'audio'}")


if __name__ == "__main__":
    main()
