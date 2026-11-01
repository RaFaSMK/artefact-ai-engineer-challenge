"""Importação validada e atômica. Originais são somente leitura."""

import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

from .policies import extract_sections
from .pricing import to_cents

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE categories(category_id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL);
CREATE TABLE customers(customer_id INTEGER PRIMARY KEY);
CREATE TABLE products(product_id INTEGER PRIMARY KEY, price_cents INTEGER NOT NULL CHECK(price_cents>=0),
 name TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories, description TEXT NOT NULL,
 stock_quantity INTEGER NOT NULL CHECK(stock_quantity>=0), status TEXT NOT NULL CHECK(status IN ('active','discontinued','coming_soon')),
 specs TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE promotions(promotion_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products,
 discount_percent INTEGER NOT NULL CHECK(discount_percent BETWEEN 0 AND 100), description TEXT NOT NULL,
 is_active INTEGER NOT NULL CHECK(is_active IN (0,1)));
CREATE TABLE orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers,
 order_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','confirmed','shipped','delivered','cancelled')),
 total_cents INTEGER NOT NULL CHECK(total_cents>=0), payment_method TEXT NOT NULL,
 tracking_code TEXT, estimated_delivery TEXT);
CREATE TABLE order_items(order_id INTEGER NOT NULL REFERENCES orders, product_id INTEGER NOT NULL REFERENCES products,
 quantity INTEGER NOT NULL CHECK(quantity>0), PRIMARY KEY(order_id,product_id));
CREATE TABLE policies(section TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 page_start INTEGER NOT NULL, page_end INTEGER NOT NULL, note TEXT NOT NULL);
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX products_category ON products(category_id);
CREATE INDEX promotions_product ON promotions(product_id,is_active);
CREATE INDEX orders_customer ON orders(customer_id,order_id);
"""


def read_table(data_dir: Path, name: str) -> list[dict]:
    files = list(data_dir.glob(f"* - {name}.csv"))
    if len(files) != 1:
        raise ValueError(f"Esperado um CSV de {name}; encontrados {len(files)}.")
    with files[0].open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_database(data_dir: Path, database_path: Path) -> dict:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    tables = {name: read_table(data_dir, name) for name in
              ("categories", "customers", "products", "promotions", "orders", "order_items")}
    sections = extract_sections(data_dir / "políticas_da_loja.pdf")
    with tempfile.NamedTemporaryFile(dir=database_path.parent, suffix=".sqlite3", delete=False) as temp:
        temporary = Path(temp.name)
    db = None
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript(SCHEMA)
            for r in tables["categories"]:
                db.execute("INSERT INTO categories VALUES(?,?,?)", (int(r["category_id"]), r["name"], r["description"]))
            for r in tables["customers"]:
                # Nomes, e-mails, telefones e observações internas não são importados.
                db.execute("INSERT INTO customers VALUES(?)", (int(r["customer_id"]),))
            for r in tables["products"]:
                specs = json.loads(r["specs"])
                if not isinstance(specs, dict):
                    raise ValueError("Especificações devem ser um objeto JSON.")
                date.fromisoformat(r["created_at"])
                db.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?)", (
                    int(r["product_id"]), to_cents(r["price_brl"]), r["name"], int(r["category_id"]),
                    r["description"], int(r["stock_quantity"]), r["status"], json.dumps(specs, ensure_ascii=False), r["created_at"]))
            for r in tables["promotions"]:
                db.execute("INSERT INTO promotions VALUES(?,?,?,?,?)", (
                    int(r["promotion_id"]), int(r["product_id"]), int(r["discount_percent"]), r["description"], int(r["is_active"])))
            for r in tables["orders"]:
                date.fromisoformat(r["order_date"])
                if r["estimated_delivery"]:
                    date.fromisoformat(r["estimated_delivery"])
                db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?)", (
                    int(r["order_id"]), int(r["customer_id"]), r["order_date"], r["status"],
                    to_cents(r["total_brl"]), r["payment_method"], r["tracking_code"] or None,
                    r["estimated_delivery"] or None))
            for r in tables["order_items"]:
                db.execute("INSERT INTO order_items VALUES(?,?,?)", (
                    int(r["order_id"]), int(r["product_id"]), int(r["quantity"])))
            for r in sections:
                db.execute("INSERT INTO policies VALUES(:section,:title,:body,:page_start,:page_end,:note)", r)
            fts = True
            try:
                db.execute("CREATE VIRTUAL TABLE policy_fts USING fts5(section UNINDEXED,title,body,tokenize='unicode61 remove_diacritics 2')")
                db.execute("INSERT INTO policy_fts SELECT section,title,body FROM policies")
            except sqlite3.OperationalError:
                fts = False
            digest = hashlib.sha256()
            for path in sorted(data_dir.iterdir()):
                if path.suffix in {".csv", ".pdf"}:
                    digest.update(path.name.encode())
                    digest.update(path.read_bytes())
            metadata = {
                "schema_version": "1", "imported_at": datetime.now(UTC).isoformat(),
                "source_sha256": digest.hexdigest(), "fts_enabled": str(fts).lower(),
                "counts": json.dumps({**{name: len(rows) for name, rows in tables.items()}, "policies": len(sections)}),
            }
            db.executemany("INSERT INTO metadata VALUES(?,?)", metadata.items())
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Relacionamento inválido na base.")
        # O context manager conclui a transação; fechar libera o arquivo no Windows.
        db.close()
        os.replace(temporary, database_path)
        return metadata
    finally:
        if db is not None:
            db.close()
        if temporary.exists():
            temporary.unlink()
