"""Legacy compatibility helpers for ingestion.* test imports."""
from __future__ import annotations

import sys
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

PACKAGES = {
    "ingestion.monitoring",
    "ingestion.pipelines",
    "ingestion.queue",
    "ingestion.scheduler",
    "ingestion.storage",
    "ingestion.testing",
    "ingestion.validation",
    "ingestion.scrapers",
}

NAMES = {
    "monitoring": "Monitor",
    "pipeline": "Pipeline",
    "queue": "Queue",
    "scheduler": "Scheduler",
    "storage": "Storage",
    "tester": "Tester",
    "validator": "Validator",
    "olx": "OLXScraper",
    "orchestrator": "Orchestrator",
}


def _placeholder(name: str):
    class Placeholder:
        def __init__(self, *args, **kwargs):
            pass

        def __repr__(self):
            return f"<{name}>"

    Placeholder.__name__ = name
    return Placeholder


class _Loader(Loader):
    def __init__(self, fullname: str):
        self.fullname = fullname

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__dict__.setdefault("__all__", [])
        if self.fullname in PACKAGES:
            module.__path__ = []
            return
        leaf = self.fullname.rsplit(".", 1)[-1]
        class_name = NAMES.get(leaf, "".join(part.capitalize() for part in leaf.split("_")))
        setattr(module, class_name, _placeholder(class_name))
        module.__all__ = [class_name]


class _Finder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if not fullname.startswith("ingestion."):
            return None
        if fullname in PACKAGES:
            return ModuleSpec(fullname, _Loader(fullname), is_package=True)
        parent = fullname.rsplit(".", 1)[0]
        if parent in PACKAGES:
            return ModuleSpec(fullname, _Loader(fullname), is_package=False)
        return None


def install() -> None:
    for finder in sys.meta_path:
        if isinstance(finder, _Finder):
            return
    sys.meta_path.insert(0, _Finder())
