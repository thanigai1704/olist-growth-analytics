# Business Memo — Retention

**To:** VP of Growth, Olist
**From:** Senior Data Analyst, Growth & Retention
**Date:** 19 October 2026
**Re:** Where our growth is leaking — and the one fix that pays for itself

---

### Headline finding

**97% of our customers never buy from us twice — and 40% of our entire revenue sits in wallets that already stopped shopping.** We are running a scaled acquisition engine with almost no retention engine. Every marketing real buys a customer we see once; the compounding economics that make a marketplace profitable never get to happen.

### Supporting numbers

1. Of 93,358 customers who bought something on the marketplace, only **3.0%** ever purchased again. A customer's chance of buying again *within the first month of their first order* is **0.48%**; by month two it is 0.34% — if the habit does not form immediately, it does not form at all.
2. Our RFM segmentation shows the **"At-Risk" segment — 24% of customers who spent well, then went quiet — holds 39.6% of historical revenue (about R$6.1m)**. These are not cheap customers wasting our time; they are our best customers on pause.
3. Meanwhile the "Champions" (recent, high-spend) segment is only 25% of customers but contributes **41% of revenue**. Concentration is healthy; replacing these people by buying lookalikes is expensive.
4. **Late delivery is the fastest way we delete loyalty:** orders that arrive on time score **4.3 stars**; a promise missed by 3 days scores **3.3**; a promise missed by 8–15 days scores **1.7**, with 80% of those customers leaving a bad review. Delivery failure is not an operations metric — it is the single biggest retention killer we can measure.

### Root cause hypothesis

Between checkout and the 14th day after delivery there is no reason to return. Nothing invites the second purchase in that window, and when we do fail the promise the failure is late and loud (late arrivals generate 32.5% of all bad reviews while being only ~7% of orders). Our own economics confirm the deficit: at an assumed blended acquisition cost of R$60, lifetime value of R$165 repays only **0.8x CAC after margin** — the model only closes if second purchases become normal.

### Recommendation

Build a **"second order within 30 days" engine** for the newest, highest-value customers (Potential Loyalists + early At-Risk): a category-matched offer in the 14 days after delivery, tied to the promise we kept. In parallel, **fix the late-delivery SLA on the top-5 revenue categories** where the score damage is concentrated.

**Expected impact:** converting 5% of the At-Risk wallet returns ~R$305k in revenue per year on a R$15.4m base, before the delivery fix's effect on scores and repeat intent. Ratio target: lifting lifetime repeat rate from 3% to 5% roughly moves LTV/CAC from 0.8x toward 1.4x on margin.

### Next steps (with more data/time)

- Join our marketing spend data so CAC stops being an assumption and the cohort-by-channel LTV becomes actionable.
- Forecast delivery risk at purchase time (seller history + transit path) and warn or redirect before the promise breaks.
- Deep-dive the 63 repeat-buyer product pairs to build the cross-sell trigger list.
- A/B-test the 14-day post-purchase flow on one city (São Paulo) before scaling.

*Data: Olist public dataset, Sep 2016 – Aug 2018 (96,478 delivered orders). Every figure above is reproducible from the project's SQL analysis file.*
