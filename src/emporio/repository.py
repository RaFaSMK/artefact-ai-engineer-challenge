"""Consultas de leitura. O modelo não recebe acesso a SQL nem a dados de clientes."""

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .policies import normalize, preferred_sections, search_terms
from .pricing import PromotionConflict, format_brl, quote, to_cents

CATEGORY_ALIASES = {
    "violao": 5, "violoes": 5, "guitarra": 1, "guitarras": 1,
    "baixo": 2, "baixos": 2, "bateria": 3, "baterias": 3,
    "teclado": 4, "piano": 4, "teclados": 4, "pianos": 4,
    "ukulele": 9, "ukuleles": 9,
}
ORDER_STATUS = {"pending": "pendente", "confirmed": "confirmado", "shipped": "enviado",
                "delivered": "entregue", "cancelled": "cancelado"}


class Repository:
    def __init__(self, path: Path, customer_id: int = 2):
        self.path = path
        self.customer_id = customer_id

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def metadata(self) -> dict:
        with self.connect() as db:
            return dict(db.execute("SELECT key,value FROM metadata"))

    @staticmethod
    def _policy_source(row: dict) -> dict:
        pages = str(row["page_start"])
        if row["page_end"] != row["page_start"]:
            pages += f"–{row['page_end']}"
        return {"id": f"policy:{row['section']}", "kind": "policy", "section": row["section"],
                "page_start": row["page_start"], "page_end": row["page_end"],
                "label": f"Manual · {row['section']} {row['title']} · p. {pages}"}

    def _product(self, db, row, payment_method) -> dict:
        promotions = db.execute(
            "SELECT promotion_id,discount_percent,description FROM promotions WHERE product_id=? AND is_active=1",
            (row["product_id"],),
        ).fetchall()
        sources = [{"id": f"product:{row['product_id']}", "kind": "product",
                    "label": f"Catálogo · produto {row['product_id']} · {row['name']}"}]
        sources.extend({"id": f"promotion:{p['promotion_id']}", "kind": "promotion",
                        "label": f"Promoção {p['promotion_id']} · {p['description']} · ativa no snapshot"}
                       for p in promotions)
        available = row["status"] == "active" and row["stock_quantity"] > 0
        product = {
            "product_id": row["product_id"], "name": row["name"], "category": row["category_name"], "category_id": row["category_id"],
            "description": row["description"], "specs": json.loads(row["specs"]),
            "stock_quantity": row["stock_quantity"], "catalog_status": row["status"],
            "available": available, "sources": sources,
        }
        try:
            product["price"] = quote(row["price_cents"], [p["discount_percent"] for p in promotions], payment_method)
            product["price_conflict"] = False
        except PromotionConflict:
            product["price"] = None
            product["price_conflict"] = True
        if promotions or payment_method == "pix":
            section = "6.2" if promotions else "3"
            policy = db.execute("SELECT * FROM policies WHERE section=?", (section,)).fetchone()
            if policy:
                sources.append(self._policy_source(dict(policy)))
        return product

    def get_product(self, product_id: int, payment_method: str | None = None) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT p.*,c.name AS category_name FROM products p JOIN categories c USING(category_id) WHERE product_id=?",
                             (product_id,)).fetchone()
            if not row:
                return {"status": "not_found", "message": "Produto não encontrado no catálogo fornecido.", "sources": []}
            product = self._product(db, row, payment_method)
            status = "needs_clarification" if product["price_conflict"] else ("ok" if product["available"] else "unavailable")
            return {"status": status, "product": product, "sources": product["sources"],
                    "message": "Snapshot local: não representa consulta ao estoque de uma loja real."}

    def search_products(self, query: str = "", category: str | None = None,
                        max_price_brl: Decimal | None = None, payment_method: str | None = None,
                        limit: int = 5) -> dict:
        limit = max(1, min(limit, 5))
        query_normalized = normalize(query)
        words = re.findall(r"[a-z0-9]+", query_normalized)
        category_id = CATEGORY_ALIASES.get(normalize(category or ""))
        if not category_id:
            category_id = next((CATEGORY_ALIASES[w] for w in words if w in CATEGORY_ALIASES), None)
        words = [w for w in words if w not in CATEGORY_ALIASES and w not in {
            "disponivel", "disponiveis", "instrumento", "instrumentos", "quanto", "custa", "preco",
            "pix", "no", "na", "do", "da", "de", "e", "com", "ate", "por", "reais",
        }]
        with self.connect() as db:
            if category and not category_id:
                categories = db.execute("SELECT category_id,name FROM categories").fetchall()
                matches = [r["category_id"] for r in categories if normalize(category) in normalize(r["name"])]
                if len(matches) != 1:
                    return {"status": "needs_clarification", "message": "Informe uma categoria mais específica.", "products": [], "sources": []}
                category_id = matches[0]
            rows = db.execute("SELECT p.*,c.name AS category_name FROM products p JOIN categories c USING(category_id) WHERE p.status='active' AND p.stock_quantity>0").fetchall()
            found, conflicts = [], 0
            for row in rows:
                if category_id and row["category_id"] != category_id:
                    continue
                haystack = normalize(row["name"] + " " + row["description"])
                if not all(w in haystack for w in words):
                    continue
                product = self._product(db, row, payment_method)
                if product["price_conflict"]:
                    conflicts += 1
                    continue
                if max_price_brl is not None and product["price"]["final_cents"] > to_cents(max_price_brl):
                    continue
                found.append(product)
            found.sort(key=lambda p: (p["price"]["final_cents"], p["product_id"]))
            products = found[:limit]
            if not products and words and max_price_brl is None:
                unavailable = db.execute("SELECT p.*,c.name AS category_name FROM products p JOIN categories c USING(category_id) WHERE p.status!='active' OR p.stock_quantity=0").fetchall()
                matches = [r for r in unavailable if (not category_id or r["category_id"] == category_id)
                           and all(w in normalize(r["name"] + " " + r["description"]) for w in words)]
                if matches:
                    products = [self._product(db, r, payment_method) for r in matches[:limit]]
                    sources = {src["id"]: src for p in products for src in p["sources"]}
                    return {"status": "unavailable", "products": products, "sources": list(sources.values()),
                            "message": "Nome encontrado, mas indisponível para oferta pelo status ou estoque. Explique o status e use outra busca por categoria para alternativas disponíveis."}
            if not products and category_id and words:
                # Nome e categoria podem se contradizer. Pedir confirmação com evidência
                # em vez de declarar que o produto não existe em toda a base.
                alternative = self.search_products(" ".join(words), None, max_price_brl, payment_method, limit)
                if alternative.get("products"):
                    alternative["status"] = "needs_clarification"
                    alternative["message"] = "Encontrei o nome em outra categoria. Informe a categoria real e confirme com o cliente qual instrumento ele quer."
                    return alternative
            sources = {source["id"]: source for p in products for source in p["sources"]}
            return {"status": "ok" if products else ("needs_clarification" if conflicts else "not_found"),
                    "products": products, "total_matches": len(found), "sources": list(sources.values()),
                    "price_conflicts_excluded": conflicts,
                    "price_condition": payment_method or "promoção ativa ou tabela; sem presumir PIX",
                    "message": "Ofertas exigem status active e estoque positivo. Resultados ordenados por preço final."}

    def get_order_status(self, order_id: int, today: date | None = None) -> dict:
        today = today or datetime.now(ZoneInfo("America/Campo_Grande")).date()
        with self.connect() as db:
            # A identidade não vem do argumento do modelo nem do corpo da requisição.
            row = db.execute("SELECT * FROM orders WHERE order_id=? AND customer_id=?", (order_id, self.customer_id)).fetchone()
            if not row:
                return {"status": "not_found", "message": "Não localizei esse pedido no contexto desta demonstração.", "sources": []}
            items = db.execute("SELECT i.product_id,p.name,i.quantity FROM order_items i JOIN products p USING(product_id) WHERE i.order_id=?",
                               (order_id,)).fetchall()
            estimate = row["estimated_delivery"]
            return {"status": "ok", "order": {
                "order_id": order_id, "order_status": row["status"], "status_pt": ORDER_STATUS[row["status"]],
                "order_date": row["order_date"], "total": format_brl(row["total_cents"]),
                "tracking_code": row["tracking_code"], "estimated_delivery": estimate,
                "estimate_in_past": bool(estimate and date.fromisoformat(estimate) < today),
                "effective_received_at": None, "purchase_channel": None,
                "items": [dict(r) for r in items],
            }, "message": "Dados históricos do snapshot. Previsão não é garantia de entrega nem consulta à transportadora. Não há registro da data efetiva de recebimento.",
                "sources": [{"id": f"order:{order_id}", "kind": "order", "label": f"Base de pedidos · pedido {order_id} · snapshot fornecido"}]}

    def search_policies(self, query: str) -> dict:
        selected = preferred_sections(query)
        with self.connect() as db:
            if not selected:
                terms = search_terms(query)
                if terms:
                    # Sintaxe construída a partir de tokens, nunca FTS bruto do usuário.
                    expression = " OR ".join(f'"{word}"' for word in terms)
                    fts = db.execute("SELECT value FROM metadata WHERE key='fts_enabled'").fetchone()
                    if fts and fts[0] == "true":
                        selected = [r[0] for r in db.execute("SELECT section FROM policy_fts WHERE policy_fts MATCH ? ORDER BY bm25(policy_fts) LIMIT 3", (expression,))]
                    else:
                        rows = db.execute("SELECT section,title,body FROM policies").fetchall()
                        ranked = sorted(rows, key=lambda r: sum(w in normalize(r[1] + " " + r[2]) for w in terms), reverse=True)
                        selected = [r[0] for r in ranked[:3] if any(w in normalize(r[1] + " " + r[2]) for w in terms)]
            chunks = []
            for section in selected:
                row = db.execute("SELECT * FROM policies WHERE section=?", (section,)).fetchone()
                if row:
                    chunks.append({**dict(row), "source": self._policy_source(dict(row))})
            return {"status": "ok" if chunks else "not_found", "chunks": chunks,
                    "sources": [c["source"] for c in chunks],
                    "message": "Manual interno versão 2.1, junho/2025. Aplicação de política não executa transações. Respeitar as notas de ambiguidade."}
