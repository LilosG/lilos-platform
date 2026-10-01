"""One place that registers every ORM model with the shared SQLAlchemy metadata.

The API gets a complete registry for free because importing its routes imports every
service and therefore every model. A standalone entry point (an operator script, a
worker task) imports only what it uses, so a foreign key to a table whose model was
never imported (``growth_initiatives.approved_by_user_id`` -> ``user_profiles``) fails
at the first flush with ``NoReferencedTableError``. ``load_all_models`` imports every
model module under ``apps.api.app`` by naming convention, so a new model is covered
without editing a list.
"""

from __future__ import annotations

import importlib
import pkgutil

from sqlalchemy.orm import configure_mappers

import apps.api.app as app_package
from apps.api.app.database.base import Base

# Models that live outside a ``models``/``*_models`` module. The parity test in
# tests/python/scripts fails if a model is missing here and from the naming convention.
EXTRA_MODEL_MODULES = ("apps.api.app.integrations.secrets",)


def _is_model_module(name: str) -> bool:
    leaf = name.rsplit(".", 1)[-1]
    return leaf == "models" or leaf.endswith("_models") or name in EXTRA_MODEL_MODULES


def load_all_models() -> None:
    """Import every model module, then fail fast if the registry is incomplete.

    ``configure_mappers`` and ``sorted_tables`` resolve every relationship and foreign
    key, so a table that is referenced but not registered raises here, at start-up,
    instead of in the middle of a write.
    """
    for module in pkgutil.walk_packages(
        app_package.__path__, prefix=f"{app_package.__name__}.", onerror=_raise
    ):
        if _is_model_module(module.name):
            importlib.import_module(module.name)
    configure_mappers()
    _ = Base.metadata.sorted_tables


def _raise(name: str) -> None:
    raise ImportError(f"could not import {name} while registering ORM models")
