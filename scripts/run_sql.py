import sqlite3
import sys
import time

t0 = time.time()
conn = sqlite3.connect("data/db/olist_growth.db")

# drop analytics-layer objects from previous runs
names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'mv_%' OR name LIKE 'vw_%'")]
for n in names:
    kind = "VIEW" if n.startswith("vw_") else "TABLE"
    conn.execute(f"DROP {kind} IF EXISTS {n}")

# parse the file into complete statements (comment/string aware)
sql = open("sql/growth_retention_analysis.sql", encoding="utf-8").read()
stmts, buf = [], []
for line in sql.splitlines():
    buf.append(line)
    if sqlite3.complete_statement("\n".join(buf)):
        stmts.append("\n".join(buf))
        buf = []
if buf and any(l.strip() for l in buf):
    stmts.append("\n".join(buf))

created, failed = [], []
for s in stmts:
    try:
        conn.execute(s)
        w = s.strip().split()[0].upper() if s.strip() else ""
        if w in ("CREATE", "SELECT"):
            created.append(s)
    except Exception as e:
        first = next((l for l in s.splitlines() if l.strip() and not l.strip().startswith('--')), "")
        failed.append((first[:90], str(e)))

if failed:
    print("FIRST FAILURE:")
    for a, b in failed[:1]:
        print(" ", a)
        print("  ->", b)
    conn.rollback()
    print(f"statements executed before failure: {len(created)}")
    sys.exit(1)

cur = conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'mv_%' ORDER BY name")
for (name,) in cur.fetchall():
    n = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(f"{name:34} {n:>10,}")
conn.commit()
conn.close()
print(f"OK — {len(stmts)} statements executed in {time.time()-t0:.1f}s")
