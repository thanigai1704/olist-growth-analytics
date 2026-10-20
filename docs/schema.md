# Data Model & Schema Documentation

Source: [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
— 9 CSVs, 99,441 orders, Sep 2016 – Aug 2018. Engine: **SQLite** (`data/db/olist_growth.db`,
built by `scripts/build_database.py`). PG-flavoured equivalents are commented inside
`sql/growth_retention_analysis.sql`.

## 1. ER diagram (described)

```
                        ┌────────────────────┐
                        │     customers      │
                        │ PK customer_id     │◄────────────┐
                        │    customer_unique_id  (durable) │
                        │    zip/city/state  │             │
                        └────────────────────┘             │
                                 ▲ 1                       │ N
                                 │                         │
                                 │ N                       │
                        ┌────────┴───────────┐             │
   ┌────────────┐       │      orders        │             │
   │ geolocation│       │ PK order_id        │             │
   │ PK zip+lat │       │ FK customer_id ────┼─────────────┘
   │  +lng+city │       │   status, timestamps│
   └────────────┘       └───┬──────────┬───────┘
        (postcode-level      │ 1        │ 1..N
         coordinate lookup   │          │
         for customers/      │          │
         sellers)            │          │
                    N        │          │
             ┌───────────────┴┐      ┌──┴───────────────┐
             │  order_items   │      │    payments       │
             │ PK order_id +  │      │ PK order_id +     │
             │    item_id     │      │    payment_seq    │
             │ FK product_id  │      │   type, installments│
             │ FK seller_id   │      │   payment_value    │
             │   price        │      └───────────────────┘
             │   freight_value│
             └───┬────────┬───┘       ┌───────────────────┐
                 ▲        ▲           │      reviews      │
                 │ 1      │ 1         │ PK order_id (1 per order)
        ┌────────┴──┐  ┌──┴────────┐  │   score(1-5), title, message │
        │  products │  │  sellers  │  │   creation/answer ts          │
        │ PK prod_id│  │ PK seller │  └───────────────────┘
        │  category │  │  zip/city │
        │  dims     │  └───────────┘
        └─────┬─────┘
              ▲ N:1
       ┌──────┴──────────────────────┐
       │ product_category_translation│
       │ PK product_category_name    │→ english name
       └─────────────────────────────┘
```

Key relationships, in words:

- `orders (N) → (1) customers` — every order belongs to exactly one `customer_id`.
- **`customer_id` is scoped to a single order in Olist.** The durable identity across
  orders is `customer_unique_id` (96,096 of them vs. 99,441 `customer_id`s).
  Every retention/RFM query routes `orders → customers` first and then groups on
  `customer_unique_id`. Getting this wrong silently destroys cohort analysis — and it
  is the #1 mistake people make with this dataset.
- `order_items (N) → (1) orders`, `(N) → (1) products`, `(N) → (1) sellers`.
- `payments` and `reviews` hang off `orders` (reviews after cleaning: max 1 per order).
- `geolocation` is a post-code-level lookup table; it is joined by zip prefix, not by PK.
- `product_category_translation` maps the Portuguese category slugs to English.

## 2. Table dictionary (analysis grain)

| table | grain | rows (cleaned) | notes |
|---|---|---|---|
| customers | 1 per order | 99,441 | `customer_unique_id` is the true buyer |
| geolocation | 1 per zip+lat+lng+city+state | 738,332 | after removing 261,831 exact dup rows |
| orders | 1 per order | 99,441 | 8 statuses; 96,478 `delivered` |
| order_items | 1 per order-line | 112,650 | PK (order_id, order_item_id) |
| payments | 1 per order-payment slice | 103,886 | PK (order_id, payment_sequential) |
| reviews | 1 per reviewed order | 98,673 | after R1 dedup (814 colliding ids resolved) |
| products | 1 per product | 32,951 | 610 missing category (mapped to `uncategorised`) |
| sellers | 1 per seller | 3,095 | |
| product_category_translation | 1 per category | 71 | |

## 3. Cleaning rules (each one deliberate and logged in `data/db_load_report.txt`)

1. **R1 — Reviews dedup.** The raw file ships 814 reused `review_id`s and 551 orders
   with 2+ submissions (later re-entries of the same survey). We keep ONE row per
   `order_id` — the row with the most recent `review_answer_timestamp`. This makes
   reviews a clean 1:0..1 bridge from orders so review joins never multiply revenue.
2. **R2 — Review comment text.** Missing title/message are *optional by design*.
   Stored as `''` (true NULLs), flagged by a `has_comment` boolean; 42.7k of 98.7k rows
   carry at least one comment. No invented filler text.
3. **R3 — Geolocation dedup.** 261,831 exact duplicate rows removed.
4. **R4 — Timestamps.** Parsed to `datetime`; steps that legally did not happen
   (e.g. delivered but no carrier step) remain NULL — downstream queries filter rather
   than invent dates. 8 delivered orders lack a delivered date; they are excluded from
   delivery-time analyses automatically via NULL checks.
5. **R5 — Money.** Prices stay in Brazilian Real (R$). No conversion. Delivered-scope
   GMV (R$ 15,419,773.75) is cross-checked against delivered-order payments
   (R$ 15,422,461.77): a +0.02% gap — the analysis standardises on **item-level GMV
   (SUM(price + freight_value))** because only that source is attributable to product /
   category / seller.
6. **R6 — Zip codes are TEXT** (leading zeros are meaningful).
7. **R7 — Nothing is dropped for missing product dims** (6 rows); those columns do not
   feed any growth/retention metric.

## 4. Data boundary notes (what the raw data itself tells us)

- **Dead month:** 0 orders exist for Nov 2016 (the soft-launch gap). It is a real
  hole, not a loader bug; the app/README say so explicitly.
- **Universe ends Aug 2018:** only 16 non-delivered stubs exist after 2018-09-03.
- First/last acquisition cohorts are tiny (1–262 customers); they are kept in the
  matrix but excluded from pooled averages (cohorts ≥ 100 customers).
