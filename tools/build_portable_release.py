import argparse
import json
import shutil
import sys
import zipfile
import copy
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.player_runtime import (
    PLAYER_SELECTOR_SCHEMA,
    validate_player_manifest,
)


QBT_VERSION = "5.2.2"
FFMPEG_VERSION = "8.1.1"
EXCLUDED_QBT_NAMES = {
    "profile",
    "BT_backup",
    "logs",
    "incomplete",
    "downloads",
}
PORTABLE_ROOT_FILES = {
    "app.py",
    "CHANGELOG.md",
    "index.html",
    "package-lock.json",
    "package.json",
    "README.md",
    "THIRD-PARTY-NOTICES.md",
    "requirements.txt",
    "run.bat",
    "vite.config.js",
}
PORTABLE_ROOT_DIRECTORIES = {
    "design",
    "dist",
    "services",
    "src",
    "static",
    "tools",
}
PORTABLE_NATIVE_DIRECTORIES = {
    "player",
}


def read_project_version(project_root=PROJECT_ROOT):
    package_path = Path(project_root) / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    version = str(package.get("version") or "").strip()
    if not version:
        raise ValueError(f"Package version is missing: {package_path}")
    return version


def should_include_qbt_file(path):
    candidate = Path(path)
    parts = {part.lower() for part in candidate.parts}
    if any(name.lower() in parts for name in EXCLUDED_QBT_NAMES):
        return False
    if candidate.suffix.lower() == ".pdb":
        return False
    return True


def build_qbt_manifest(version=QBT_VERSION, app_version=None):
    app_version = app_version or read_project_version()
    return {
        "name": "qBittorrent",
        "version": version,
        "source": "official qBittorrent Windows x64 release",
        "website": "https://www.qbittorrent.org/",
        "license": "GPL",
        "bundled_for": f"Cinema Paradiso {app_version}",
    }


def copy_qbt_runtime(source, destination, version=QBT_VERSION, app_version=None):
    source = Path(source)
    destination = Path(destination)
    executable = source / "qbittorrent.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"qBittorrent executable not found: {executable}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        if not should_include_qbt_file(relative):
            continue
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
    manifest = build_qbt_manifest(version, app_version=app_version)
    (destination / "cinema-paradiso-qbittorrent.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_ffmpeg_manifest(version=FFMPEG_VERSION, app_version=None):
    app_version = app_version or read_project_version()
    return {
        "name": "FFmpeg",
        "version": version,
        "source": "Gyan.dev Windows full build",
        "website": "https://www.gyan.dev/ffmpeg/builds/",
        "license": "GPLv3",
        "purpose": "Local IPTV remuxing to browser-compatible HLS",
        "bundled_for": f"Cinema Paradiso {app_version}",
    }


def copy_ffmpeg_runtime(source, destination, version=FFMPEG_VERSION, app_version=None):
    source = Path(source)
    destination = Path(destination)
    candidates = [source, source / "bin" / "ffmpeg.exe", source / "ffmpeg.exe"]
    executable = next((candidate for candidate in candidates if candidate.is_file() and candidate.name.lower() == "ffmpeg.exe"), None)
    if executable is None:
        raise FileNotFoundError(f"FFmpeg executable not found under: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    bin_dir = destination / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, bin_dir / "ffmpeg.exe")
    ffprobe = executable.with_name("ffprobe.exe")
    if ffprobe.is_file():
        shutil.copy2(ffprobe, bin_dir / "ffprobe.exe")
    manifest = build_ffmpeg_manifest(version, app_version=app_version)
    (destination / "cinema-paradiso-ffmpeg.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def resolve_player_bundle_source(project_root, player_source=None):
    if player_source:
        return Path(player_source).resolve()
    runtime_root = Path(project_root).resolve() / "runtime" / "player"
    selector_path = runtime_root / "current.json"
    try:
        selector = json.loads(selector_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise FileNotFoundError(
            "The pinned native player runtime is missing. "
            "Provide --player-source or assemble runtime/player/current.json."
        ) from error
    if selector.get("schema") != PLAYER_SELECTOR_SCHEMA:
        raise ValueError(f"Invalid native player selector: {selector_path}")
    bundle_version = str(selector.get("bundle_version") or "").strip()
    if not bundle_version or Path(bundle_version).name != bundle_version:
        raise ValueError(f"Invalid native player bundle version: {selector_path}")
    return (runtime_root / "versions" / bundle_version).resolve()


def copy_player_runtime(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    manifest = validate_player_manifest(source, verify_hashes=True)
    bundle_version = manifest["bundle_version"]
    version_destination = destination / "versions" / bundle_version
    if version_destination.exists():
        shutil.rmtree(version_destination)
    version_destination.mkdir(parents=True, exist_ok=True)
    for relative_text in manifest["required_files"]:
        relative = Path(*relative_text.replace("\\", "/").split("/"))
        source_file = source / relative
        destination_file = version_destination / relative
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination_file)
    shutil.copy2(
        source / "cinema-paradiso-player.json",
        version_destination / "cinema-paradiso-player.json",
    )
    selector = {
        "schema": PLAYER_SELECTOR_SCHEMA,
        "bundle_version": bundle_version,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "current.json").write_text(
        json.dumps(selector, indent=2) + "\n",
        encoding="utf-8",
    )
    validate_player_manifest(version_destination, verify_hashes=True)
    return manifest


def copy_application_files(project_root, staging, dist_source=None):
    """One allowlist for public releases and explicitly private test folders."""
    project_root = Path(project_root).resolve()
    staging = Path(staging)
    for item in project_root.iterdir():
        if item.name == "dist" and dist_source is not None:
            continue
        if item.is_file() and item.name not in PORTABLE_ROOT_FILES:
            continue
        if item.is_dir() and item.name not in PORTABLE_ROOT_DIRECTORIES:
            continue
        target = staging / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"),
            )
        else:
            shutil.copy2(item, target)
    if dist_source is not None:
        shutil.copytree(dist_source, staging / "dist")
    native_root = project_root / "native"
    if native_root.is_dir():
        native_destination = staging / "native"
        native_destination.mkdir(parents=True, exist_ok=True)
        for directory_name in PORTABLE_NATIVE_DIRECTORIES:
            source = native_root / directory_name
            if source.is_dir():
                shutil.copytree(
                    source,
                    native_destination / directory_name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pdb"),
                )


def build_release_zip(project_root, qbt_source=None, ffmpeg_source=None, output_dir=None, player_source=None):
    project_root = Path(project_root).resolve()
    app_version = read_project_version(project_root)
    qbt_source = Path(qbt_source or (project_root / "data" / "qbittorrent" / "versions" / QBT_VERSION)).resolve()
    player_source = resolve_player_bundle_source(project_root, player_source)
    default_ffmpeg_source = project_root / "runtime" / "ffmpeg"
    ffmpeg_source = Path(ffmpeg_source).resolve() if ffmpeg_source else (default_ffmpeg_source.resolve() if default_ffmpeg_source.exists() else None)
    output_dir = Path(output_dir or (project_root / "release")).resolve()
    staging = output_dir / f"Cinema-Paradiso-{app_version}-Portable"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    copy_application_files(project_root, staging)
    copy_qbt_runtime(
        qbt_source,
        staging / "runtime" / "qbittorrent" / "versions" / QBT_VERSION,
        QBT_VERSION,
        app_version=app_version,
    )
    copy_player_runtime(
        player_source,
        staging / "runtime" / "player",
    )
    if ffmpeg_source:
        copy_ffmpeg_runtime(
            ffmpeg_source,
            staging / "runtime" / "ffmpeg",
            FFMPEG_VERSION,
            app_version=app_version,
        )
    zip_path = output_dir / f"Cinema-Paradiso-{app_version}-Portable.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in staging.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(staging.parent))
    return zip_path


def friend_test_config(original):
    """Keep service credentials/preferences, replace machine-specific storage."""
    config = copy.deepcopy(original)
    config.update(movies_dir="library/movies", movies_dirs=["library/movies"],
                  tv_roots=["library/tv"], user_data_dir="data", tmdb_cache_dir="cache",
                  prowlarr_url="http://127.0.0.1:19696", ollama_url="http://127.0.0.1:21434",
                  qbt_mode="embedded", qbt_download_dir="", qbt_incomplete_dir="", qbt_webui_port=18686)
    # Physical screen position belongs to the recipient's monitor.
    if isinstance(config.get("player"), dict):
        config["player"].pop("window_state", None)
    return config


def copy_prowlarr_settings(source, destination):
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f"{(source / 'prowlarr.db').resolve().as_uri()}?mode=ro", uri=True)) as live:
        with closing(sqlite3.connect(destination / "prowlarr.db")) as snapshot:
            live.backup(snapshot)
            if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Prowlarr settings snapshot failed integrity check")
            for row_id, settings in snapshot.execute("SELECT Id,Settings FROM IndexerProxies WHERE Implementation='FlareSolverr'").fetchall():
                payload = json.loads(settings)
                payload["host"] = "http://127.0.0.1:18191/"
                snapshot.execute("UPDATE IndexerProxies SET Settings=? WHERE Id=?", (json.dumps(payload), row_id))
            snapshot.commit()
    config = ET.parse(source / "config.xml")
    for key, value in {"Port": "19696", "BindAddress": "127.0.0.1", "UrlBase": "",
                       "EnableSsl": "False", "LaunchBrowser": "False", "UpdateAutomatically": "False"}.items():
        node = config.getroot().find(key)
        if node is None:
            node = ET.SubElement(config.getroot(), key)
        node.text = value
    config.write(destination / "config.xml", encoding="utf-8", xml_declaration=True)


def build_friend_test_folder(project_root, destination, *, ollama_source, prowlarr_source,
                             flaresolverr_source, ffmpeg_source, dist_source,
                             ollama_identity_source=None):
    """Explicit private export. Never called by the public ZIP command."""
    root, target = Path(project_root).resolve(), Path(destination).resolve()
    if target.exists():
        raise FileExistsError(f"Private test destination already exists: {target}")
    if target == root or root in target.parents:
        raise ValueError("Private export must be outside the source checkout")
    required = [(Path(ollama_source) / "ollama.exe"), (Path(prowlarr_source) / "bin/Prowlarr.Console.exe"),
                (Path(flaresolverr_source) / "flaresolverr.exe"), Path(dist_source) / "index.html"]
    for executable in required:
        if not executable.is_file():
            raise FileNotFoundError(executable)
    settings = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    player = resolve_player_bundle_source(root)
    # Validate hashes before starting a large copy.
    validate_player_manifest(player, verify_hashes=True)
    target.mkdir(parents=True)
    copy_application_files(root, target, dist_source=dist_source)
    (target / "config.json").write_text(json.dumps(friend_test_config(settings), indent=2), encoding="utf-8")
    copy_qbt_runtime(root / "data/qbittorrent/versions" / QBT_VERSION,
                     target / "runtime/qbittorrent/versions" / QBT_VERSION,
                     app_version=read_project_version(root))
    copy_player_runtime(player, target / "runtime/player")
    copy_ffmpeg_runtime(ffmpeg_source, target / "runtime/ffmpeg", app_version=read_project_version(root))
    ollama = Path(ollama_source)
    (target / "runtime/ollama").mkdir(parents=True)
    shutil.copy2(ollama / "ollama.exe", target / "runtime/ollama/ollama.exe")
    shutil.copytree(ollama / "lib", target / "runtime/ollama/lib")
    shutil.copytree(Path(prowlarr_source) / "bin", target / "runtime/prowlarr",
                    ignore=shutil.ignore_patterns("*.pdb", "*.log"))
    copy_prowlarr_settings(prowlarr_source, target / "data/prowlarr")
    flare = Path(flaresolverr_source)
    (target / "runtime/flaresolverr").mkdir(parents=True)
    shutil.copy2(flare / "flaresolverr.exe", target / "runtime/flaresolverr/flaresolverr.exe")
    shutil.copytree(flare / "_internal", target / "runtime/flaresolverr/_internal",
                    ignore=shutil.ignore_patterns("*.log", "__pycache__"))
    data = Path(settings.get("user_data_dir") or root / "data")
    iptv = data / "iptv"
    for relative in [Path("providers.json"), Path("metadata-settings.json")]:
        if (iptv / relative).is_file():
            (target / "data/iptv").mkdir(parents=True, exist_ok=True)
            shutil.copy2(iptv / relative, target / "data/iptv" / relative)
    if (iptv / "providers.json").is_file():
        for provider in json.loads((iptv / "providers.json").read_text())["providers"]:
            provider_id = provider["provider_id"]
            if not provider_id.isalnum():
                raise ValueError("Invalid IPTV provider ID")
            source = iptv / "providers" / provider_id / "provider.json"
            dest = target / "data/iptv/providers" / provider_id
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest / "provider.json")
    if ollama_identity_source is not None:
        home = target / "data/ollama-home/.ollama"
        home.mkdir(parents=True, exist_ok=True)
        for name in ("id_ed25519", "id_ed25519.pub"):
            shutil.copy2(Path(ollama_identity_source) / name, home / name)
    for relative in ("library/movies", "library/tv", "cache", "data/ollama-models"):
        (target / relative).mkdir(parents=True, exist_ok=True)
    # Private launcher replaces the public development launcher only in this copy.
    shutil.copy2(root / "tools/friend_test_run.bat", target / "run.bat")
    shutil.copy2(root / "tools/friend_test_signin.bat", target / "Ollama sign in.bat")
    shutil.copy2(root / "tools/friend_test_stop.bat", target / "Stop CP.bat")
    shutil.copy2(root / "tools/friend_test_handover.md", target / "CODEX-HANDOVER.md")
    for name in ("AGENTS.md", ".gitignore"):
        shutil.copy2(root / name, target / name)
    shutil.copytree(root / "tests", target / "tests", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    manifest = {"kind": "private-friend-test", "source_commit": commit,
                "cp_version": read_project_version(root), "cloud_model": settings.get("ollama_model"),
                "ollama_account_included": ollama_identity_source is not None,
                "libraries": "empty; no media/catalog/jobs copied", "ports": {
                    "CP": 15000, "Ollama": 21434, "Prowlarr": 19696, "FlareSolverr": 18191, "qBittorrent": 18686}}
    (target / "TEST-PACKAGE.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description="Build the Cinema Paradiso portable release ZIP.")
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--qbt-source", default=None)
    parser.add_argument("--ffmpeg-source", default=None)
    parser.add_argument("--player-source", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    print(
        build_release_zip(
            args.project_root,
            qbt_source=args.qbt_source,
            ffmpeg_source=args.ffmpeg_source,
            player_source=args.player_source,
            output_dir=args.output_dir,
        )
    )


if __name__ == "__main__":
    main()
