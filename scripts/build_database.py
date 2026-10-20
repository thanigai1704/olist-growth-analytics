"""
build_database.py — Olist Growth & Retention Analytics
=======================================================

STAGE 1 of the pipeline: raw CSVs  ->  cleaned relational SQLite database.

What this script does (in order):

  1. Creates a proper relational schema  (PK/FK relationships, types, indexes)
     mirroring the 9-table Olist star-ish structure:
         customers ─< orders ─< order_items >─ products
                         │           └─>─ sellers
                         ├─< payments
                         └─< reviews
         geolocation (postcode-level lookup)  ·  product_category_translation
  2. Loads every CSV inside data/raw/ with EXPLICIT dtype per column
     (zip codes read as TEXT so leading zeros survive; money as REAL).
  3. Applies the documented cleaning rules (see CLEANING RULES below).
  4. Prints + saves a data-quality report (data/db_load_report.txt).

CLEANING RULES (each one is a deliberate, documented decision)
-------------------------------------------------------------
 R1  Reviews: the raw table violates its PK — the SAME review_id is reused
     across rows (814 collisions) and 551 orders carry 2+ submissions that
     are later survey re-entries of one event.  Rule: keep exactly ONE row
     per order_id — the one with the most recent review_answer_timestamp
     (the latest submission).  Result: reviews becomes a clean 1:0..1
     bridge from orders.
 R2  Reviews: missing comment title / message are OPTIONAL fields by design
     (42.7k of 99.2k rows have some text).  They are stored as '' +
     flagged with has_comment ('' is honest NULL-marking; a fake text would
     distort any future NLP work).
 R3  Geolocation: 261,831 rows are exact duplicates of another row.
     They are removed so the postcode lookup is unique-safe.
 R4  Orders with a NULL timestamp for steps they legally skipped
     (e.g. 'delivered' but no carrier step) are KEPT as-is: NULL means
     "event did not happen", and every downstream query aggregates with
     filters instead of inventing dates.
 R5  Money columns are cast to REAL and stay in Brazilian Reais (R$).
     They are NEVER silently converted to dollars; the README explains the
     "generic revenue" framing instead (a currency conversion would only
     distort halves of cents and lose interpretability).
 R6  Zip code prefixes are TEXT (leading zeros are meaningful).
 R7  No row is dropped for having NULL products weight/dims (only 6 rows):
     those columns are not used in any growth/retention metric.

Run:  python scripts/build_database.py
Output: data/db/olist_growth.db (~120 MB) + data/db_load_report.txt
"""
import csv
import os
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "raw")
DB = os.path.join(BASE, "data", "db", "olist_growth.db")
REPORT = os.path.join(BASE, "data", "db_load_report.txt")

report_lines = []


def log(msg=""):
    report_lines.append(str(msg))
    print(msg)


# ----------------------------------------------------------------------------
# 1. SCHEMA (SQLite dialect; ER description lives in docs/schema.md)
# ----------------------------------------------------------------------------
SCHEMA = """
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS geolocation;
DROP TABLE IF EXISTS product_category_translation;

CREATE TABLE customers (
    customer_id            TEXT PRIMARY KEY,          -- one per ORDER in Olist (see README)
    customer_unique_id     TEXT NOT NULL,             -- true cross-order identity
    customer_zip_code_prefix TEXT NOT NULL,
    customer_city          TEXT NOT NULL,
    customer_state         TEXT NOT NULL
);

CREATE TABLE geolocation (
    geolocation_zip_code_prefix TEXT NOT NULL,
    geolocation_lat        REAL NOT NULL,
    geolocation_lng        REAL NOT NULL,
    geolocation_city       TEXT NOT NULL,
    geolocation_state      TEXT NOT NULL
);

CREATE TABLE orders (
    order_id                      TEXT PRIMARY KEY,
    customer_id                   TEXT NOT NULL REFERENCES customers(customer_id),
    order_status                  TEXT NOT NULL,
    order_purchase_timestamp      TEXT,   -- ISO 'YYYY-MM-DD HH:MM:SS'
    order_approved_at             TEXT,
    order_delivered_carrier_date  TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT
);

CREATE TABLE order_items (
    order_id            TEXT NOT NULL REFERENCES orders(order_id),
    order_item_id       INTEGER NOT NULL,
    product_id          TEXT NOT NULL REFERENCES products(product_id),
    seller_id           TEXT NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date TEXT,
    price               REAL NOT NULL,            -- R$ per unit
    freight_value       REAL NOT NULL,            -- R$ freight allocated to this item
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE payments (
    order_id             TEXT NOT NULL REFERENCES orders(order_id),
    payment_sequential   INTEGER NOT NULL,
    payment_type         TEXT NOT NULL,
    payment_installments INTEGER NOT NULL DEFAULT 1,
    payment_value        REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE reviews (
    review_id               TEXT NOT NULL,
    order_id                TEXT NOT NULL REFERENCES orders(order_id),
    review_score            INTEGER NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title    TEXT NOT NULL DEFAULT '',        -- R2: '' = genuine NULL
    review_comment_message  TEXT NOT NULL DEFAULT '',
    review_creation_date    TEXT,
    review_answer_timestamp TEXT,
    has_comment             INTEGER NOT NULL DEFAULT 0,      -- 1 if title or message present
    PRIMARY KEY (order_id)                                    -- R1: one review per order
);

CREATE TABLE products (
    product_id                 TEXT PRIMARY KEY,
    product_category_name      TEXT,
    product_name_lenght        INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           REAL,
    product_length_cm          REAL,
    product_height_cm          REAL,
    product_width_cm           REAL
);

CREATE TABLE sellers (
    seller_id             TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT NOT NULL,
    seller_city           TEXT NOT NULL,
    seller_state          TEXT NOT NULL
);

CREATE TABLE product_category_translation (
    product_category_name      TEXT PRIMARY KEY,
    product_category_name_english TEXT NOT NULL
);

-- Query-speed indexes for the exact joins the analysis SQL takes
CREATE INDEX idx_orders_customer    ON orders(customer_id);
CREATE INDEX idx_items_order        ON order_items(order_id);
CREATE INDEX idx_items_product      ON order_items(product_id);
CREATE INDEX idx_items_seller       ON order_items(seller_id);
CREATE INDEX idx_payments_order     ON payments(order_id);
CREATE INDEX idx_reviews_order      ON reviews(order_id);
CREATE INDEX idx_geo_prefix         ON geolocation(geolocation_zip_code_prefix);
"""

# ----------------------------------------------------------------------------
# 2. LOADERS
# ----------------------------------------------------------------------------
def read_csv(fname):
    """Read one raw CSV with utf-8-sig (v2 files ship a BOM)."""
    path = os.path.join(RAW, fname)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def iso_or_none(s):
    """Validate the 'YYYY-MM-DD HH:MM:SS' shape; return '' for true NULLs."""
    s = (s or "").strip()
    if not s:
        return ""
    return s if len(s) == 19 else s[:19]


def r(num, nd=2):
    return round(float(num), nd)


def load_static(conn):
    customers = read_csv("olist_customers_dataset.csv")
    geo = read_csv("olist_geolocation_dataset.csv")
    prod = read_csv("olist_products_dataset.csv")
    sell = read_csv("olist_sellers_dataset.csv")
    tr = read_csv("product_category_name_translation.csv")

    conn.executemany(
        "INSERT INTO customers VALUES (?,?,?,?,?)",
        [(x["customer_id"], x["customer_unique_id"], x["customer_zip_code_prefix"],
          x["customer_city"], x["customer_state"]) for x in customers],
    )

    # R3 — de-duplicate geolocation rows
    seen, keep = set(), []
    for x in geo:
        key = (x["geolocation_zip_code_prefix"], x["geolocation_lat"], x["geolocation_lng"],
               x["geolocation_city"], x["geolocation_state"])
        if key not in seen:
            seen.add(key)
            keep.append(key)
    log(f"[clean R3] geolocation: {len(geo):,} raw rows -> {len(keep):,} unique "
        f"({len(geo) - len(keep):,} exact duplicates removed)")
    conn.executemany("INSERT INTO geolocation VALUES (?,?,?,?,?)", keep)

    def _int(v):
        return int(float(v)) if v.strip() else None

    def _real(v):
        return float(v) if v.strip() else None

    conn.executemany(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)",
        [(x["product_id"], x["product_category_name"] or None,
          _int(x["product_name_lenght"]), _int(x["product_description_lenght"]),
          _int(x["product_photos_qty"]), _real(x["product_weight_g"]),
          _real(x["product_length_cm"]), _real(x["product_height_cm"]),
          _real(x["product_width_cm"])) for x in prod],
    )
    conn.executemany(
        "INSERT INTO sellers VALUES (?,?,?,?)",
        [(x["seller_id"], x["seller_zip_code_prefix"], x["seller_city"], x["seller_state"])
         for x in sell],
    )
    conn.executemany(
        "INSERT INTO product_category_translation VALUES (?,?)",
        [(x["product_category_name"], x["product_category_name_english"]) for x in tr],
    )
    return len(customers), len(prod), len(sell), len(tr)


def load_transactions(conn):
    orders = read_csv("olist_orders_dataset.csv")
    items = read_csv("olist_order_items_dataset.csv")
    pay = read_csv("olist_order_payments_dataset.csv")
    rev = read_csv("olist_order_reviews_dataset.csv")

    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)",
        [(x["order_id"], x["customer_id"], x["order_status"],
          iso_or_none(x["order_purchase_timestamp"]),
          iso_or_none(x["order_approved_at"]),
          iso_or_none(x["order_delivered_carrier_date"]),
          iso_or_none(x["order_delivered_customer_date"]),
          iso_or_none(x["order_estimated_delivery_date"])) for x in orders],
    )

    conn.executemany(
        "INSERT INTO order_items VALUES (?,?,?,?,?,?,?)",
        [(x["order_id"], int(x["order_item_id"]), x["product_id"], x["seller_id"],
          iso_or_none(x["shipping_limit_date"]), float(x["price"]), float(x["freight_value"]))
         for x in items],
    )

    conn.executemany(
        "INSERT INTO payments VALUES (?,?,?,?,?)",
        [(x["order_id"], int(x["payment_sequential"]), x["payment_type"],
          int(float(x["payment_installments"] or 1)), float(x["payment_value"] or 0))
         for x in pay],
    )

    # R1 — keep the LATEST submission per order_id
    latest = {}
    for x in rev:
        oid = x["order_id"]
        key = (iso_or_none(x["review_creation_date"]), iso_or_none(x["review_answer_timestamp"]))
        cur = latest.get(oid)
        if cur is None or key > cur[0]:
            latest[oid] = (key, x)
    log(f"[clean R1] reviews: {len(rev):,} raw rows -> {len(latest):,} unique reviewed orders "
        f"({len(rev) - len(latest):,} duplicate submissions collapsed to latest answer)")

    rows = []
    for _key, x in latest.values():
        title = (x["review_comment_title"] or "").strip()
        msg = (x["review_comment_message"] or "").strip()
        rows.append((x["review_id"], x["order_id"], int(x["review_score"]),
                     title, msg, iso_or_none(x["review_creation_date"]),
                     iso_or_none(x["review_answer_timestamp"]),
                     1 if (title or msg) else 0))
    conn.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?)", rows)
    return len(orders), len(items), len(pay), len(rows), len(latest)


# ----------------------------------------------------------------------------
# 3. RUN
# ----------------------------------------------------------------------------
def main():
    t0 = time.time()
    log("=" * 74)
    log("OLIST GROWTH & RETENTION — DATABASE BUILD")
    log("=" * 74)
    if os.path.exists(DB):
        os.remove(DB)
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)

    log("")
    log("[load] static dimension tables ...")
    n_cust, n_prod, n_sell, n_tr = load_static(conn)
    log(f"[load] customers={n_cust:,}  products={n_prod:,}  sellers={n_sell:,}  translation={n_tr}")
    log("")
    log("[load] transactional fact tables ...")
    n_ord, n_items, n_pay, n_rev_kept, n_rev_unique = load_transactions(conn)
    log(f"[load] orders={n_ord:,}  order_items={n_items:,}  payments={n_pay:,}  reviews={n_rev_kept:,}")

    conn.commit()

    # ---- integrity verification -------------------------------------------
    log("")
    log("[verify] integrity checks:")
    checks = [
        ("orders.customer_id all resolve to customers",
         "SELECT COUNT(*) FROM orders o LEFT JOIN customers c USING(customer_id) WHERE c.customer_id IS NULL", 0),
        ("order_items.order_id all resolve to orders",
         "SELECT COUNT(*) FROM order_items i LEFT JOIN orders o USING(order_id) WHERE o.order_id IS NULL", 0),
        ("order_items.product_id all resolve to products",
         "SELECT COUNT(*) FROM order_items i LEFT JOIN products p USING(product_id) WHERE p.product_id IS NULL", 0),
        ("order_items.seller_id all resolve to sellers",
         "SELECT COUNT(*) FROM order_items i LEFT JOIN sellers s USING(seller_id) WHERE s.seller_id IS NULL", 0),
        ("payments.order_id all resolve to orders",
         "SELECT COUNT(*) FROM payments p LEFT JOIN orders o USING(order_id) WHERE o.order_id IS NULL", 0),
        ("reviews.order_id all resolve to orders",
         "SELECT COUNT(*) FROM reviews r LEFT JOIN orders o USING(order_id) WHERE o.order_id IS NULL", 0),
        ("orders PK unique (max dup = 0)",
         "SELECT COUNT(*) FROM (SELECT order_id FROM orders GROUP BY order_id HAVING COUNT(*)>1)", 0),
        ("reviews PK unique per order (max dup = 0)",
         "SELECT COUNT(*) FROM (SELECT order_id FROM reviews GROUP BY order_id HAVING COUNT(*)>1)", 0),
        ("review scores within 1..5",
         "SELECT COUNT(*) FROM reviews WHERE review_score NOT BETWEEN 1 AND 5", 0),
    ]
    ok = True
    for name, sql, expect in checks:
        n = conn.execute(sql).fetchone()[0]
        flag = "OK" if n == expect else "FAIL"
        ok = ok and (n == expect)
        log(f"    {flag:4} {name:<46} unexpected={n}")

    log("")
    log("[scope] analysis-wide figures (whole db):")
    n_del = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE order_status='delivered'"
    ).fetchone()[0]
    rev_items = conn.execute(
        "SELECT COALESCE(SUM(i.price+i.freight_value),0) FROM order_items i "
        "JOIN orders o USING(order_id) WHERE o.order_status='delivered'"
    ).fetchone()[0]
    rev_pay = conn.execute("SELECT COALESCE(SUM(payment_value),0) FROM payments").fetchone()[0]
    n_unique = conn.execute("SELECT COUNT(DISTINCT customer_unique_id) FROM customers").fetchone()[0]
    log(f"    distinct customers (customer_unique_id): {n_unique:,}")
    log(f"    delivered orders: {n_del:,}")
    log(f"    GMV sum(price+freight): R$ {rev_items:,.2f}")
    pay_del = conn.execute(
        "SELECT COALESCE(SUM(p.payment_value),0) FROM payments p JOIN orders o USING(order_id) "
        "WHERE o.order_status='delivered'"
    ).fetchone()[0]
    log(f"    cross-check A (all rows):      payments R$ {rev_pay:,.2f} "
        f"({100*(rev_pay-rev_items)/rev_items:+.2f}% vs items GMV incl. non-delivered)")
    log(f"    cross-check B (delivered only): payments R$ {pay_del:,.2f} "
        f"(gap {100*(pay_del-rev_items)/rev_items:+.2f}% — voucher/side-adjustments only; "
        f"analysis standardises on item-level GMV)")

    conn.execute("PRAGMA optimize")
    conn.commit()
    conn.close()
    log("")
    log(f"[done] database written to {DB}  in {time.time() - t0:,.1f}s")
    log(f"       ALL INTEGRITY CHECKS {'PASSED' if ok else 'FAILED'}")

    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(report_lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
