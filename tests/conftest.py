from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "02_app"

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


@pytest.fixture
def load_app_module(monkeypatch: pytest.MonkeyPatch):
    """Load an app module with explicit substitutes for import-time services."""

    loaded_module_names: list[str] = []

    def load(
        relative_path: str,
        *,
        stubs: dict[str, ModuleType],
    ) -> ModuleType:
        for name, stub in stubs.items():
            monkeypatch.setitem(sys.modules, name, stub)

        module_name = f"_test_{Path(relative_path).stem}_{len(loaded_module_names)}"
        module_path = APP_ROOT / relative_path
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load test module from {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        loaded_module_names.append(module_name)
        spec.loader.exec_module(module)
        return module

    yield load

    for module_name in loaded_module_names:
        sys.modules.pop(module_name, None)
