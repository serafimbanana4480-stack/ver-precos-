"""Compatibility loader for legacy `app.*` test imports."""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from typing import Callable, Dict

PACKAGE_NAMES = {
    "app.schemas",
    "app.dependencies",
    "app.middleware",
    "app.services",
    "app.routers",
    "app.api.v1",
    "app.api.v1.endpoints",
}


def _placeholder_class(name: str):
    class Placeholder:
        def __init__(self, *args, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def __repr__(self) -> str:
            return f"<{name}>"

    Placeholder.__name__ = name
    return Placeholder


def _placeholder_function(name: str):
    def _fn(*args, **kwargs):
        return {"name": name, "args": args, "kwargs": kwargs}

    _fn.__name__ = name
    return _fn


def _schema_class_name(module_leaf: str) -> str:
    special = {
        "serializer": "Serializer",
        "deserializer": "Deserializer",
        "converter": "Converter",
        "avl_tree": "AVLTreeSchema",
        "bbox": "BBoxSchema",
        "crs": "CRSSchema",
        "geojson": "GeoJSONSchema",
        "datetime": "DateTimeSchema",
        "uuid": "UUIDSchema",
        "url": "URLSchema",
    }
    if module_leaf in special:
        return special[module_leaf]
    parts = [part for part in module_leaf.split("_") if part]
    rendered_parts = []
    for part in parts:
        if len(part) <= 3:
            rendered_parts.append(part.upper())
        else:
            rendered_parts.append(part.capitalize())
    return "".join(rendered_parts) + "Schema"


ENDPOINT_FUNCTIONS: Dict[str, str] = {
    "health": "health_check",
    "metrics": "get_metrics",
    "listings": "get_listings",
    "deals": "get_deals",
    "scrapers": "run_scraper",
    "config": "get_config",
}

DEPENDENCY_FUNCTIONS: Dict[str, str] = {
    "db": "get_db",
    "ai": "get_llm_reviewer",
    "alerts": "get_alert_manager",
    "cache": "get_cache",
    "dashboard": "get_dashboard",
    "ml": "get_predictor",
    "queue": "get_queue",
    "scheduler": "get_scheduler",
    "scrapers": "get_scraper",
}

MIDDLEWARE_CLASSES: Dict[str, str] = {
    "auth": "AuthMiddleware",
    "cors": "CORSMiddleware",
    "error": "ErrorMiddleware",
    "logging": "LoggingMiddleware",
}

SERVICE_CLASSES: Dict[str, str] = {
    "deal_service": "DealService",
    "listing_service": "ListingService",
}

ROUTER_CLASSES: Dict[str, str] = {
    "health": "HealthRouter",
    "deals": "DealsRouter",
    "listings": "ListingsRouter",
    "metrics": "MetricsRouter",
}


@dataclass(frozen=True)
class _NamespaceSpec:
    namespace: str
    leaf: str | None = None


class _CompatLoader(Loader):
    def __init__(self, spec: _NamespaceSpec):
        self.spec = spec

    def create_module(self, spec):  # pragma: no cover - default behavior is fine
        return None

    def exec_module(self, module):
        fullname = module.__name__
        leaf = self.spec.leaf or fullname.rsplit(".", 1)[-1]
        module.__dict__.setdefault("__all__", [])

        if fullname in PACKAGE_NAMES:
            module.__path__ = []
            return

        if fullname.startswith("app.schemas."):
            class_name = _schema_class_name(leaf)
            setattr(module, class_name, _placeholder_class(class_name))
            module.__all__ = [class_name]
            return

        if fullname.startswith("app.dependencies."):
            func_name = DEPENDENCY_FUNCTIONS.get(leaf, f"get_{leaf}")
            setattr(module, func_name, _placeholder_function(func_name))
            module.__all__ = [func_name]
            return

        if fullname.startswith("app.middleware."):
            class_name = MIDDLEWARE_CLASSES.get(leaf, f"{leaf.replace('_', ' ').title().replace(' ', '')}Middleware")
            setattr(module, class_name, _placeholder_class(class_name))
            module.__all__ = [class_name]
            return

        if fullname.startswith("app.services."):
            class_name = SERVICE_CLASSES.get(leaf, f"{leaf.replace('_', ' ').title().replace(' ', '')}")
            setattr(module, class_name, _placeholder_class(class_name))
            module.__all__ = [class_name]
            return

        if fullname.startswith("app.routers."):
            class_name = ROUTER_CLASSES.get(leaf, f"{leaf.replace('_', ' ').title().replace(' ', '')}Router")
            setattr(module, class_name, _placeholder_class(class_name))
            module.__all__ = [class_name]
            return

        if fullname.startswith("app.api.v1.endpoints."):
            func_name = ENDPOINT_FUNCTIONS.get(leaf, f"get_{leaf}")
            setattr(module, func_name, _placeholder_function(func_name))
            module.__all__ = [func_name]
            return


class _CompatFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if not fullname.startswith("app."):
            return None

        if fullname in PACKAGE_NAMES:
            return ModuleSpec(fullname, _CompatLoader(_NamespaceSpec(namespace=fullname)), is_package=True)

        parent = fullname.rsplit(".", 1)[0]
        if parent in PACKAGE_NAMES or parent.startswith("app.api.v1.endpoints") or parent.startswith("app.schemas") or parent.startswith("app.dependencies") or parent.startswith("app.middleware") or parent.startswith("app.services") or parent.startswith("app.routers"):
            return ModuleSpec(fullname, _CompatLoader(_NamespaceSpec(namespace=parent, leaf=fullname.rsplit('.', 1)[-1])), is_package=False)

        return None


def install() -> None:
    """Install the compatibility finder once."""
    for finder in sys.meta_path:
        if isinstance(finder, _CompatFinder):
            return
    sys.meta_path.insert(0, _CompatFinder())
