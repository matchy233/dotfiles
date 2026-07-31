import os
from pathlib import Path
import tempfile


def uses_posix_file_modes(os_name: str = os.name) -> bool:
    return os_name != "nt"


def renders_windows_documents(os_name: str = os.name) -> bool:
    return os_name == "nt"


def can_create_symbolic_links() -> bool:
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            link = root / "link"
            target.write_text("probe", encoding="utf-8")
            link.symlink_to(target)
            return link.is_symlink()
    except OSError:
        return False


WINDOWS_WITHOUT_SYMBOLIC_LINKS = (
    renders_windows_documents() and not can_create_symbolic_links()
)
