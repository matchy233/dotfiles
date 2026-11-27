import importlib.util
from pathlib import Path
import sys
from types import ModuleType


def load_script(path: Path) -> ModuleType:
    """Import a script from the chezmoi source without leaving bytecode in it."""
    name = path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load script: {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module
