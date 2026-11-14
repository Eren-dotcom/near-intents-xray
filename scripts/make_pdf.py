#!/usr/bin/env python3
"""Optional: print docs/report.html to docs/NEAR-Intents-X-Ray-report.pdf (needs `pip install playwright`
and `python3 -m playwright install chromium`). Not part of rebuild.py, which uses the standard library only."""
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("file://" + os.path.join(ROOT, "docs", "report.html"))
    pg.pdf(path=os.path.join(ROOT, "docs", "NEAR-Intents-X-Ray-report.pdf"), format="A4", print_background=True,
           display_header_footer=True, header_template="<span></span>",
           footer_template='<div style="font:7pt sans-serif;color:#6b7280;width:100%;padding:0 15mm;display:flex;justify-content:space-between"><span>NEAR Intents X-Ray · research note · not investment advice</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
           margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"})
    b.close()
print("wrote docs/NEAR-Intents-X-Ray-report.pdf")
