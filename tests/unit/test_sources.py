"""Behaviour: classify a PDF filename into ACL groups, doc_type, and a product name."""

import pytest

from bas_assistant.ingest.sources import (
    acl_groups_for,
    doc_type_for,
    product_for,
    product_from_filename,
)

pytestmark = pytest.mark.unit


def test_engineer_only_filenames_get_the_engineer_acl_group() -> None:
    assert acl_groups_for("DAC-633PoE-Catalog-Sheet.pdf") == ["engineer"]
    assert acl_groups_for("UNOnext-MODBUS-RTU-Protocol.pdf") == ["engineer"]


def test_other_filenames_get_the_all_acl_group() -> None:
    assert acl_groups_for("eBM-800-Catalog-Sheet.pdf") == ["all"]
    assert acl_groups_for("UNOnext-Datasheet.pdf") == ["all"]


def test_doc_type_reads_protocol_datasheet_or_defaults_to_catalog() -> None:
    assert doc_type_for("UNOnext-MODBUS-RTU-Protocol.pdf") == "protocol"
    assert doc_type_for("UNOnext-Datasheet.pdf") == "datasheet"
    assert doc_type_for("eBM-800-Catalog-Sheet.pdf") == "catalog"


def test_product_for_known_starter_pdf_uses_the_listed_name() -> None:
    assert product_for("enteliWEB-Catalog-Sheet.pdf") == "enteliWEB"


def test_product_for_unknown_pdf_falls_back_to_the_filename_heuristic() -> None:
    assert product_for("O3-Sensor-Hub-Catalog-Sheet.pdf") == "O3 Sensor Hub"


def test_product_from_filename_strips_the_doc_type_suffix() -> None:
    assert product_from_filename("O3-Sensor-Hub-Catalog-Sheet.pdf") == "O3 Sensor Hub"
    assert product_from_filename("Red5-PLUS-1180_Catalog_Sheet.pdf") == "Red5 PLUS 1180"


def test_product_from_filename_with_no_recognised_suffix_de_slugs_the_whole_stem() -> None:
    assert product_from_filename("eZNS-T100.pdf") == "eZNS T100"
