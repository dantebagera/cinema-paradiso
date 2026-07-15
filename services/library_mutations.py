import os
import shutil
import stat
from pathlib import Path

from send2trash import send2trash


class LibraryMutationError(RuntimeError):
    pass


class LibraryMutationService:
    """Own filesystem mutations and their matching catalog updates."""

    def __init__(self, roots, metadata_store, video_extensions, trash_file=send2trash):
        self.roots = [Path(root).resolve() for root in roots if root]
        self.metadata_store = metadata_store
        self.video_extensions = {str(ext).lower() for ext in video_extensions}
        self.trash_file = trash_file

    def _library_root(self, path):
        candidate = Path(path).resolve()
        for root in self.roots:
            try:
                candidate.relative_to(root)
                return root
            except ValueError:
                continue
        return None

    def delete(self, path, *, use_trash=True):
        candidate = Path(path).resolve()
        root = self._library_root(candidate)
        if root is None:
            raise LibraryMutationError('Path is outside the allowed movies directory')
        if not candidate.is_file():
            raise FileNotFoundError(str(candidate))

        current_mode = candidate.stat().st_mode
        if not (current_mode & stat.S_IWRITE):
            candidate.chmod(current_mode | stat.S_IWRITE)

        parent = candidate.parent
        if use_trash:
            self.trash_file(str(candidate))
        else:
            candidate.unlink()

        folder_removed = False
        if not use_trash and parent != root and parent.is_dir():
            remaining_videos = [
                child for child in parent.iterdir()
                if child.is_file() and child.suffix.lower() in self.video_extensions
            ]
            if not remaining_videos:
                shutil.rmtree(parent, ignore_errors=True)
                folder_removed = True

        self.metadata_store.remove_path_records(str(candidate))
        return {
            'success': True,
            'deleted': str(candidate),
            'folder_removed': folder_removed,
            'folder': str(parent),
            'trashed': bool(use_trash),
        }
