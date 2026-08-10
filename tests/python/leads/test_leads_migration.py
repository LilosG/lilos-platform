from importlib import import_module

import pytest


class _Inspector:
    def __init__(self, columns: set[str]) -> None:
        self.columns = columns

    def get_columns(self, table_name: str) -> list[dict[str, str]]:
        assert table_name == "leads"
        return [{"name": name} for name in self.columns]


@pytest.mark.parametrize(
    ("existing", "expected_added"),
    [
        (set(), {"converted_value_cents", "loss_reason"}),
        ({"converted_value_cents", "loss_reason"}, set()),
        ({"converted_value_cents"}, {"loss_reason"}),
    ],
)
def test_operational_column_migration_reconciles_only_missing_columns(
    monkeypatch: pytest.MonkeyPatch,
    existing: set[str],
    expected_added: set[str],
) -> None:
    migration = import_module("migrations.versions.20260810_0001_leads_operational_columns")
    bind = object()
    added: list[str] = []

    def record_column(table_name: str, column: object) -> None:
        assert table_name == "leads"
        column_name = getattr(column, "name", None)
        assert isinstance(column_name, str)
        added.append(column_name)

    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        migration.sa,
        "inspect",
        lambda candidate: _Inspector(existing) if candidate is bind else None,
    )
    monkeypatch.setattr(
        migration.op,
        "add_column",
        record_column,
    )

    migration.upgrade()

    assert set(added) == expected_added
