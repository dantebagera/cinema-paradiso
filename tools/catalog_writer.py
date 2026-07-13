import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.catalog_repository import CatalogRepository


def configured_user_data(project_root):
    project_root = Path(project_root).resolve()
    config_path = project_root / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    return Path(config.get("user_data_dir") or (project_root / "data")).resolve()


def status(repository):
    connection = repository.store.connect()
    try:
        counts = {
            "file_records": connection.execute("SELECT COUNT(*) FROM media_files").fetchone()[0],
            "tmdb_movies": connection.execute("SELECT COUNT(*) FROM tmdb_movies").fetchone()[0],
            "plex_files": connection.execute("SELECT COUNT(*) FROM plex_files").fetchone()[0],
            "manual_matches": connection.execute("SELECT COUNT(*) FROM manual_matches").fetchone()[0],
            "user_lists": connection.execute("SELECT COUNT(*) FROM user_lists").fetchone()[0],
            "list_movies": connection.execute("SELECT COUNT(*) FROM list_items").fetchone()[0],
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
        dirty = connection.execute("SELECT value FROM catalog_meta WHERE key='export_dirty'").fetchone()
    finally:
        connection.close()
    return {
        "database": str(repository.database_path),
        "write_authority": "sqlite" if repository.authority_enabled() else "json",
        "generation": repository.generation(),
        "integrity": integrity,
        "foreign_key_errors": foreign_keys,
        "export_dirty": bool(dirty and dirty[0] == "1"),
        "counts": counts,
    }


def main():
    parser = argparse.ArgumentParser(description="Manage the Cinema Paradiso SQLite catalog writer.")
    parser.add_argument("command", choices=("status", "activate", "export", "verify"))
    parser.add_argument("--project-root", default=PROJECT_ROOT)
    args = parser.parse_args()

    user_data = configured_user_data(args.project_root)
    repository = CatalogRepository(user_data)
    if args.command == "activate":
        activated = repository.activate_from_json()
        print(json.dumps({"activated": activated, **status(repository)}, indent=2))
    elif args.command == "export":
        names = repository.export_all()
        print(json.dumps({"exported": names, "verification": repository.verify_exports(names)}, indent=2))
    elif args.command == "verify":
        print(json.dumps(repository.verify_exports(repository.export_all()), indent=2))
    else:
        print(json.dumps(status(repository), indent=2))


if __name__ == "__main__":
    main()
