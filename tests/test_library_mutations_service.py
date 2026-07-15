import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from services.library_mutations import LibraryMutationError, LibraryMutationService


class LibraryMutationServiceTest(unittest.TestCase):
    def test_delete_updates_catalog_after_filesystem_success(self):
        with tempfile.TemporaryDirectory() as root:
            movie = Path(root) / 'Alien.1979.mkv'
            movie.write_bytes(b'movie')
            metadata_store = Mock()
            service = LibraryMutationService([root], metadata_store, {'.mkv'})

            result = service.delete(movie, use_trash=False)

        self.assertFalse(movie.exists())
        self.assertEqual(result['deleted'], str(movie.resolve()))
        metadata_store.remove_path_records.assert_called_once_with(str(movie.resolve()))

    def test_delete_does_not_update_catalog_when_trash_fails(self):
        with tempfile.TemporaryDirectory() as root:
            movie = Path(root) / 'Alien.1979.mkv'
            movie.write_bytes(b'movie')
            metadata_store = Mock()
            service = LibraryMutationService(
                [root], metadata_store, {'.mkv'},
                trash_file=Mock(side_effect=OSError('trash unavailable')),
            )

            with self.assertRaises(OSError):
                service.delete(movie, use_trash=True)

        metadata_store.remove_path_records.assert_not_called()

    def test_delete_rejects_files_outside_library_roots(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            movie = Path(outside) / 'Alien.1979.mkv'
            movie.write_bytes(b'movie')
            service = LibraryMutationService([root], Mock(), {'.mkv'})

            with self.assertRaises(LibraryMutationError):
                service.delete(movie, use_trash=False)


if __name__ == '__main__':
    unittest.main()
