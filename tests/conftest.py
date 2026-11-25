import importlib.util, sys, types
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "print_log"


def _load():
    pkg = types.ModuleType("pl")
    pkg.__path__ = [str(PKG)]
    sys.modules["pl"] = pkg
    for name in ("costs", "store"):
        spec = importlib.util.spec_from_file_location(f"pl.{name}", PKG / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"pl.{name}"] = mod
        spec.loader.exec_module(mod)


_load()
