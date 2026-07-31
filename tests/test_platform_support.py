import unittest

from tests.platform_support import (
    can_create_symbolic_links,
    renders_windows_documents,
    uses_posix_file_modes,
)


class PlatformSupportTest(unittest.TestCase):
    def test_posix_modes_are_not_portable_to_windows(self) -> None:
        self.assertFalse(uses_posix_file_modes("nt"))
        self.assertTrue(uses_posix_file_modes("posix"))

    def test_documents_are_rendered_only_on_windows(self) -> None:
        self.assertTrue(renders_windows_documents("nt"))
        self.assertFalse(renders_windows_documents("posix"))

    def test_symbolic_link_probe_returns_a_boolean(self) -> None:
        self.assertIsInstance(can_create_symbolic_links(), bool)


if __name__ == "__main__":
    unittest.main()
