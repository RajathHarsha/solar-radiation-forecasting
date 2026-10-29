"""Build the redesigned single-file dashboard (dashboard.html) from
outputs/city_data.json (per-city series + forecasts) and outputs/results.json (extensions).
Chart.js and Plotly.js load from CDN; everything else is inline."""
import json, re
from pathlib import Path

ROOT = Path(__file__).parent
D = json.loads((ROOT / "outputs" / "city_data.json").read_text(encoding="utf-8"))
R = json.loads((ROOT / "outputs" / "results.json").read_text(encoding="utf-8"))
RAW = json.loads((ROOT / "outputs" / "weekly_raw.json").read_text(encoding="utf-8"))

# Reuse the honest literature text (PAPERS / GAP) from the earlier generator without running it.
src = (ROOT / "make_dashboard.py").read_text(encoding="utf-8")
block = src[src.index("PAPERS = ["): src.index("# ------------------------------------------------------------------ template")]
ns = {}
exec(block, ns)
PAPERS, GAP = ns["PAPERS"], ns["GAP"]

html = (ROOT / "dashboard_template.html").read_text(encoding="utf-8")
html = (html.replace("__DATA__", json.dumps(D, separators=(",", ":")))
            .replace("__EXT__", json.dumps(R.get("extensions", {}), separators=(",", ":")))
            .replace("__RAW__", json.dumps(RAW, separators=(",", ":")))
            .replace("__PAPERS__", json.dumps(PAPERS))
            .replace("__GAP__", json.dumps(GAP)))
(ROOT / "dashboard.html").write_text(html, encoding="utf-8")
print("dashboard.html written,", len(html) // 1024, "KB")

# ---- publish version: the artifact host adds the document skeleton, so strip it and keep title/styles/scripts/body content
pub = html
pub = re.sub(r"<!DOCTYPE html>\s*", "", pub, flags=re.I)
pub = re.sub(r"</?html[^>]*>\s*", "", pub)
pub = re.sub(r"</?head>\s*", "", pub)
pub = re.sub(r"</?body>\s*", "", pub)
pub = re.sub(r'<meta charset="utf-8">\s*', "", pub)
pub = re.sub(r'<meta name="viewport"[^>]*>\s*', '<meta name="claude:viewport-fit-sides" content="cover">\n', pub)
(ROOT / "dashboard_publish.html").write_text(pub, encoding="utf-8")
print("dashboard_publish.html written,", len(pub) // 1024, "KB")
