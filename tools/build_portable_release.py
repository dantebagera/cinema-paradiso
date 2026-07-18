import argparse
import json
import shutil
import zipfile
from pathlib import Path


CP_VERSION = "2.8.0"
QBT_VERSION = "5.2.2"
EXCLUDED_QBT_NAMES = {
    "profile",
    "BT_backup",
    "logs",
    "incomplete",
    "downloads",
}


def should_include_qbt_file(path):
    candidate = Path(path)
    parts = {part.lower() for part in candidate.parts}
    if any(name.lower() in parts for name in EXCLUDED_QBT_NAMES):
        return False
    if candidate.suffix.lower() == ".pdb":
        return False
    return True


def build_qbt_manifest(version=QBT_VERSION):
    return {
        "name": "qBittorrent",
        "version": version,
        "source": "official qBittorrent Windows x64 release",
        "website": "https://www.qbittorrent.org/",
        "license": "GPL",
        "bundled_for": f"Cinema Paradiso {CP_VERSION}",
    }


def copy_qbt_runtime(source, destination, version=QBT_VERSION):
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
    manifest = build_qbt_manifest(version)
    (destination / "cinema-paradiso-qbittorrent.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_release_zip(project_root, qbt_source=None, output_dir=None):
    project_root = Path(project_root).resolve()
    qbt_source = Path(qbt_source or (project_root / "data" / "qbittorrent" / "versions" / QBT_VERSION)).resolve()
    output_dir = Path(output_dir or (project_root / "release")).resolve()
    staging = output_dir / f"Cinema-Paradiso-{CP_VERSION}-Portable"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    ignored_roots = {
        ".git",
        ".venv",
        "node_modules",
        "data",
        "cache",
        "release",
        "runtime",
        "winapp",
        "_cf_profile",
        "test-results",
        "__pycache__",
        "config.json",
        "res_cache.json",
    }
    for item in project_root.iterdir():
        if item.name in ignored_roots:
            continue
        target = staging / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, target)
    copy_qbt_runtime(qbt_source, staging / "runtime" / "qbittorrent" / "versions" / QBT_VERSION, QBT_VERSION)
    zip_path = output_dir / f"Cinema-Paradiso-{CP_VERSION}-Portable.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in staging.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(staging.parent))
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build the Cinema Paradiso portable release ZIP.")
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--qbt-source", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    print(build_release_zip(args.project_root, args.qbt_source, args.output_dir))


if __name__ == "__main__":
    main()
