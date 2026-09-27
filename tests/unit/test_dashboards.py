"""Behaviour: the provisioned dashboards and alert rules load, point at provisioned data
sources, and read Postgres only through the dash_* views that grafana_reader may select."""

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = Path(__file__).parents[2]
GRAFANA = ROOT / "deploy" / "grafana"
MIGRATION = ROOT / "src/bas_assistant/db/migrations/versions/0005_dashboards.py"
DASHBOARDS = sorted((GRAFANA / "dashboards").glob("*.json"))
RELATION = re.compile(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0005", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _views() -> set[str]:
    return set(_migration().VIEWS)


def _datasource_uids() -> dict[str, str]:
    provisioned = yaml.safe_load(
        (GRAFANA / "provisioning/datasources/datasources.yaml").read_text()
    )
    return {source["uid"]: source["type"] for source in provisioned["datasources"]}


# Any: Grafana's dashboard and alert-rule JSON has no schema to type it against.
def _queries() -> list[tuple[str, dict[str, Any]]]:
    """(where, query) for every panel target and every alert-rule query."""
    found = []
    for path in DASHBOARDS:
        for panel in json.loads(path.read_text())["panels"]:
            found += [(f"{path.name}: {panel['title']}", target) for target in panel["targets"]]
    rules = yaml.safe_load((GRAFANA / "provisioning/alerting/rules.yaml").read_text())
    for rule in rules["groups"][0]["rules"]:
        found += [
            (rule["uid"], {"datasource": {"uid": query["datasourceUid"]}, **query["model"]})
            for query in rule["data"]
            if query["datasourceUid"] != "__expr__"
        ]
    return found


def test_both_dashboards_are_provisioned_read_only() -> None:
    boards = {
        json.loads(path.read_text())["uid"]: json.loads(path.read_text()) for path in DASHBOARDS
    }

    assert set(boards) == {"bas-budget", "bas-quality"}
    assert all(board["editable"] is False for board in boards.values())


def test_every_query_uses_a_provisioned_data_source() -> None:
    uids = _datasource_uids()

    unknown = [where for where, query in _queries() if query["datasource"]["uid"] not in uids]

    assert unknown == []


def test_postgres_queries_read_only_views_grafana_reader_may_select() -> None:
    readable = set(_migration().READABLE)
    postgres = [
        (where, q["rawSql"]) for where, q in _queries() if q["datasource"]["uid"] == "postgres"
    ]

    outside = [
        (where, relation)
        for where, sql in postgres
        for relation in RELATION.findall(sql)
        if relation not in readable
    ]

    assert postgres
    assert outside == []


def test_every_view_is_a_dash_view() -> None:
    assert all(name.startswith("dash_") for name in _views())


def test_quality_dashboard_shows_rerank_time() -> None:
    quality = json.loads((GRAFANA / "dashboards/quality.json").read_text())

    rerank = [
        target["rawSql"]
        for panel in quality["panels"]
        for target in panel["targets"]
        if "rerank" in panel["title"].lower()
    ]

    assert any("p95_rerank_ms" in sql for sql in rerank)
