"""Assemble the personal Windows bundle; never starts Isaac or its renderer."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("overlay model bridge layered_surface samira_vfx client_vfx canvas system_pointer samira_audio "
           "combat_effects hud status visibility native_cursor shop_ui localization mastery_renderer mastery_glb "
           "mastery_particles yone_combat_audio yone_vfx display_geometry").split()
YONE_FILES = ("yone.glb", "actions.json", "rig-events.json")
YONE_AUDIO = (
    "manifest.json", "joke.wav", "taunt.wav", "dance.wav", "dance_loop.wav", "laugh.wav",
    "attack.wav", "attack2.wav", "q.wav", "q3.wav", "w.wav", "e.wav", "e_return.wav", "r.wav", "shield.wav",
)


def build(output, *, include_local_yone=False):
    if include_local_yone:
        missing = [name for name in YONE_FILES if not (ROOT / "assets/yone-local" / name).is_file()]
        if missing:
            raise FileNotFoundError("Run tools/import_yone_assets.py first. Missing from assets/yone-local: "
                                    + ", ".join(missing))
    output.mkdir(parents=True, exist_ok=True)
    staging_area = ROOT / "work" / ("friend-export-yone-local" if include_local_yone else "friend-export")
    stage = staging_area / "Soul-Fighter-Samira"
    if stage.exists():
        assert stage.resolve().parent == staging_area.resolve()
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    def copy(source, target):
        source = ROOT / source
        target = stage / target
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        else:
            shutil.copy2(source, target)

    copy("src/samira-testroom/mod", "samira_testroom")
    copy("work/export-runtime/python", "companion/python")
    # NumPy build command launchers encode the build machine's interpreter path.
    for name in ("bin", "include"):
        tooling = stage / "companion/python/Lib/site-packages" / name
        if tooling.exists():
            assert tooling.resolve().is_relative_to(stage.resolve())
            shutil.rmtree(tooling)
    for name in MODULES:
        copy(f"src/samira/external/{name}.py", f"companion/src/samira/external/{name}.py")
    copy("src/samira/external/assets/mastery", "companion/src/samira/external/assets/mastery")
    for name in ("model.glb", "rig-events.json"):
        copy(f"src/samira/reference/source/{name}", f"companion/src/samira/reference/source/{name}")
    copy("tools/run_testroom_renderer.py", "companion/tools/run_testroom_renderer.py")
    copy("src/samira-testroom/visual-settings.json", "companion/src/samira-testroom/visual-settings.json")
    for name in ("audio", "vfx", "manifest.json"):
        copy(f"assets/samira-soul-fighter/{name}", f"companion/assets/samira-soul-fighter/{name}")
    if include_local_yone:
        for name in YONE_FILES:
            copy(f"assets/yone-local/{name}", f"companion/assets/yone-local/{name}")
        for name in YONE_AUDIO:
            if (ROOT / "assets/yone-local/audio" / name).is_file():
                copy(f"assets/yone-local/audio/{name}", f"companion/assets/yone-local/audio/{name}")
        if (ROOT / "assets/yone-local/yone-portrait.png").is_file():
            copy("assets/yone-local/yone-portrait.png", "samira_testroom/resources/gfx/samira/yone-portrait.png")
    for name in ("yone-ability-icons.lock.json", "yone-spirit-audio.lock.json"):
        copy(f"docs/{name}", f"provenance/{name}")
    for source, target in (("export-launcher.cmd", "launch.cmd"), ("export-launcher.ps1", "launcher.ps1"), ("export-INSTALL.txt", "INSTALL.txt")):
        copy(f"tools/{source}", target)
    for source, target in (("export-stop.cmd", "stop.cmd"), ("export-stop.ps1", "stop.ps1")):
        if (ROOT / "tools" / source).exists():
            copy(f"tools/{source}", target)
    (stage / "companion/work").mkdir(parents=True, exist_ok=True)
    (stage / "CREDITS.txt").write_text(
        "Soul Fighter Samira — personal experimental mod.\n"
        "League of Legends character, model, animations, sounds and original artwork: Riot Games.\n"
        "Framework and external renderer adapted from TFOS4 Isaac-LoL-HeroStudio:\n"
        "https://github.com/TFOS4/Isaac-LoL-HeroStudio\n"
        "https://github.com/TFOS4/Isaac-LoL-HeroStudio/releases/tag/v1.0.0\n"
        "Asset provenance is retained in companion/assets/samira-soul-fighter manifests.\n"
        "Yone ability icon provenance: provenance/yone-ability-icons.lock.json.\n"
        "Yone spirit warning provenance: provenance/yone-spirit-audio.lock.json.\n"
        "Python and dependency notices/licenses accompany companion/python.\n"
        "Liberation font license: samira_testroom/resources/font/LIBERATION-LICENSE.txt.\n"
        "No blanket license is granted for third-party materials.\n"
        + ("Classic Yone materials were imported locally from the user's League of Legends installation.\n"
           if include_local_yone else ""), encoding="utf-8")
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    manifest = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (stage / "SHA256SUMS.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archive_name = ("Soul-Fighter-Samira-Yone-Local-Windows.zip" if include_local_yone
                    else "Soul-Fighter-Samira-0.3.2-Windows.zip")
    archive = output / archive_name
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(stage.parent))
        z.writestr("Soul-Fighter-Samira/companion/work/", "")
    with zipfile.ZipFile(archive) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"Corrupt archive member: {bad}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size, "files": len(files) + 1, "sha256": digest}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-local-yone", action="store_true",
                        help="Include the locally imported classic Yone model in a personal ZIP.")
    arguments = parser.parse_args()
    build(arguments.output, include_local_yone=arguments.include_local_yone)
