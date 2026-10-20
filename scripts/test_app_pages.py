# -*- coding: utf-8 -*-
"""Headless smoke test for all GrowthLens pages using streamlit AppTest."""
import os
import sys

APP_DIR = r"C:\Users\thanigaivel\Documents\Default Project\olist-growth-analytics\streamlit_app"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)  # relative page-link paths resolve like a real `streamlit run`

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = [
    "app.py",
    "pages/1_Executive_Summary.py",
    "pages/2_Cohort_Retention.py",
    "pages/3_Customer_Segments.py",
    "pages/4_Category_Insights.py",
]

failures = 0
for page in PAGES:
    at = AppTest.from_file(os.path.join(APP_DIR, page), default_timeout=120)
    at.run()
    errors = [str(e) for e in at.exception]
    status = "OK" if not errors else "FAIL"
    failures += len(errors)
    print(f"{status} | {page}")
    for e in errors:
        print("      ", e.splitlines()[0][:200])
sys.exit(1 if failures else 0)
