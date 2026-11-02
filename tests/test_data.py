import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from emporio.config import ROOT
from emporio.ingest import build_database
from emporio.pricing import PromotionConflict, format_brl, quote, to_cents
from emporio.repository import Repository


@pytest.mark.parametrize("base,discounts,payment,expected", [
    (54900, [20], "pix", 43920), (35900, [10], None, 32310),
    (239900, [18], "pix", 196718), (599900, [8], None, 551908),
    (219900, [], "pix", 208905), (219900, [], None, 219900),
    (15990, [], "pix", 15191),
])
def test_prices_are_deterministic(base, discounts, payment, expected):
    assert quote(base, discounts, payment)["final_cents"] == expected


def test_money_conversion_and_conflict():
    assert to_cents("599.90") == 59990
    assert format_brl(123456789) == "R$ 1.234.567,89"
    with pytest.raises(PromotionConflict):
        quote(10000, [10, 20], "pix")
    for invalid in ["-1", "NaN", "Infinity"]:
        with pytest.raises(ValueError):
            to_cents(invalid)


def test_snapshot_counts_and_no_private_fields(repo):
    counts = json.loads(repo.metadata()["counts"])
    assert counts == {"categories": 9, "customers": 50, "products": 65, "promotions": 25,
                      "orders": 20, "order_items": 22, "policies": 28}
    with repo.connect() as db:
        assert [r[1] for r in db.execute("PRAGMA table_info(customers)")] == ["customer_id"]
        assert "notes" not in [r[1] for r in db.execute("PRAGMA table_info(orders)")]


@pytest.mark.parametrize("product_id", [96, 113, 130, 136])
def test_inactive_or_zero_stock_not_available(repo, product_id):
    result = repo.get_product(product_id)
    assert result["status"] == "unavailable"
    assert result["product"]["available"] is False


def test_catalog_budget_and_price_basis(repo):
    result = repo.search_products(category="violão", max_price_brl=Decimal("1000"))
    assert result["total_matches"] == 12
    assert len(result["products"]) == 5
    assert all(p["available"] and p["price"]["final_cents"] <= 100000 for p in result["products"])
    ukuleles = repo.search_products(query="Ohana CK-20", category="ukulele", max_price_brl=Decimal("450"))
    assert any(p["product_id"] == 121 and p["price"]["final_cents"] == 43920 for p in ukuleles["products"])


def test_named_product_punctuation_and_wrong_category(repo):
    assert repo.search_products(query="Ohana CK-20?")["products"][0]["product_id"] == 121
    result = repo.search_products(query="Ohana CK-20", category="violão")
    assert result["status"] == "needs_clarification"
    assert result["products"][0]["category"] == "Ukuleles"


def test_inactive_promotion_ignored(repo):
    price = repo.get_product(95)["product"]["price"]
    assert price["final_cents"] == 219900
    assert price["discount_origin"] == "none"


def test_named_unavailable_product_is_identifiable_without_offering_it(repo):
    result = repo.search_products(query="Giannini GF-3D")
    assert result["status"] == "unavailable"
    assert result["products"][0]["product_id"] == 96
    assert result["products"][0]["available"] is False


def test_promotion_conflict_is_exposed(database, tmp_path):
    path = tmp_path / "conflict.sqlite3"
    shutil.copyfile(database, path)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO promotions VALUES(999,121,30,'Conflito de teste',1)")
    repo = Repository(path)
    assert repo.get_product(121)["status"] == "needs_clarification"
    assert repo.get_product(121)["product"]["price"] is None
    assert not repo.search_products(query="Ohana CK-20")["products"]


def test_order_access_old_forecast_and_historical_total(repo, database):
    order = repo.get_order_status(8, today=date(2026, 11, 1))["order"]
    assert order["status_pt"] == "enviado" and order["estimate_in_past"]
    assert order["tracking_code"] == "BRJL5544332BR"
    assert order["effective_received_at"] is None
    assert repo.get_order_status(1) == repo.get_order_status(99999)
    assert Repository(database, customer_id=12).get_order_status(3)["order"]["total"] == "R$ 3.450,00"


@pytest.mark.parametrize("query,sections", [
    ("Posso devolver uma compra online?", {"4.1", "4.4"}),
    ("Desconto PIX acumula com promoção?", {"6.2", "3"}),
    ("WhatsApp da loja", {"7", "1.2"}),
    ("Frete exatamente 500 reais", {"5.1", "5.2"}),
    ("Parcelamento no cartão", {"3.1", "3"}),
    ("Qual o horário no sábado?", {"2"}),
])
def test_policy_retrieval_preserves_rules_and_provenance(repo, query, sections):
    result = repo.search_policies(query)
    assert {c["section"] for c in result["chunks"]} == sections
    assert all(c["body"] and c["source"]["page_start"] >= 2 for c in result["chunks"])


def test_delivery_chunk_crosses_pages_and_ambiguity_is_explicit(repo):
    chunks = repo.search_policies("frete")["chunks"]
    outside = next(c for c in chunks if c["section"] == "5.2")
    assert outside["page_start"] == 4 and outside["page_end"] == 5
    assert "500" in chunks[0]["note"]


def test_search_query_cannot_inject_sql_or_fts(repo):
    assert not repo.search_products(query="'; DROP TABLE products;--")["products"]
    repo.search_policies('" OR * - () ; DROP TABLE policies;')
    assert repo.get_product(121)["status"] == "ok"


def test_ingest_is_idempotent_and_failure_preserves_previous_database(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    path = tmp_path / "test.sqlite3"
    first = build_database(data, path)
    second = build_database(data, path)
    assert first["counts"] == second["counts"]
    old_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    source = next(data.glob("* - promotions.csv"))
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    rows[0]["discount_percent"] = "200"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(sqlite3.IntegrityError):
        build_database(data, path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == old_hash
    assert Repository(path).get_product(121)["status"] == "ok"
