
import zipfile
import os
import html
import re
from lxml import etree
from statistics import mean
from datetime import datetime

# ---------------- Namespaces ----------------

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dcterms": "http://purl.org/dc/terms/",
}

BULK_INSERT_THRESHOLD = 300

# ---------------- Utilities ----------------

def safe(val, default=""):
    return val if val is not None else default

def parse_date(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", ""))
    except Exception:
        return None

def format_date(val):
    dt = parse_date(val)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "Unknown date"

# ---------------- Filename Handling ----------------

def next_available_html(base_path):
    i = 1
    while True:
        candidate = f"{base_path}-{i}.html"
        if not os.path.exists(candidate):
            return candidate
        i += 1

# ---------------- DOCX Loading ----------------

def load_xml(docx, path):
    with zipfile.ZipFile(docx) as z:
        if path not in z.namelist():
            return None
        return etree.fromstring(z.read(path))

# ---------------- Metadata ----------------

def extract_core_metadata(docx):
    root = load_xml(docx, "docProps/core.xml")
    if root is None:
        return {}

    return {
        "created": safe(root.findtext("dcterms:created", namespaces=NS)),
        "modified": safe(root.findtext("dcterms:modified", namespaces=NS)),
        "lastModifiedBy": safe(root.findtext("cp:lastModifiedBy", namespaces=NS)),
        "revision": safe(root.findtext("cp:revision", namespaces=NS)),
    }

# ---------------- Paragraph Processing ----------------

def paragraph_text(p):
    return "".join(t.text or "" for t in p.findall(".//w:t", NS))

# ---------------- Revisions ----------------

def extract_revisions(p):
    revs = []
    for tag in ("ins", "del"):
        for el in p.findall(f".//w:{tag}", NS):
            text = "".join(el.itertext())
            revs.append({
                "type": tag,
                "author": el.get(f"{{{NS['w']}}}author", "Unknown"),
                "date": el.get(f"{{{NS['w']}}}date"),
                "text": text,
                "bulk": len(text) >= BULK_INSERT_THRESHOLD,
            })
    return revs

# ---------------- Anomalies ----------------

def detect_anomalies(p):
    issues = set()
    for r in p.findall(".//w:r", NS):
        rpr = r.find("w:rPr", NS)
        text = "".join(t.text or "" for t in r.findall(".//w:t", NS))
        if rpr is not None and not text.strip():
            issues.add("Formatting-only run")
        if "\u200b" in text or "\ufeff" in text:
            issues.add("Zero-width / BOM characters")
        if rpr is not None and rpr.find("w:vanish", NS) is not None:
            issues.add("Hidden text (vanish)")
    return list(issues)

# ---------------- Stylometry ----------------

def stylometry(text):
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return None
    avg_len = mean(len(s.split()) for s in sentences)
    return avg_len

# ---------------- Analysis ----------------

def analyze(docx):
    root = load_xml(docx, "word/document.xml")

    paragraphs = {}
    revisions = []
    anomalies = {}
    styles = {}

    pid = 0
    for p in root.findall(".//w:p", NS):
        pid += 1
        key = f"P{pid:04d}"
        text = paragraph_text(p)
        paragraphs[key] = text

        for r in extract_revisions(p):
            r["paragraph"] = key
            revisions.append(r)

        a = detect_anomalies(p)
        if a:
            anomalies[key] = a

        s = stylometry(text)
        if s:
            styles[key] = s

    contrast = []
    keys = list(styles.keys())
    for i in range(1, len(keys) - 1):
        if abs(styles[keys[i]] - (styles[keys[i - 1]] + styles[keys[i + 1]]) / 2) > 10:
            contrast.append(keys[i])

    return paragraphs, revisions, anomalies, contrast

# ---------------- HTML Rendering ----------------

def render_html(docx, meta, data):
    paragraphs, revisions, anomalies, contrast = data
    base = os.path.splitext(docx)[0]
    out = next_available_html(base)

    with open(out, "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>DOCX Forensic Audit</title>
<style>
body { font-family: sans-serif; margin: 1em; }
.container { display: flex; gap: 1em; }
.pane { flex: 1; border: 1px solid #ccc; padding: 1em; height: 85vh; overflow-y: auto; }
.ins { background: #e6ffe6; }
.del { background: #ffe6e6; text-decoration: line-through; }
.warn { color: darkred; }
.meta { font-size: 0.9em; color: #555; }
</style>
</head>
<body>
<h1>DOCX Forensic Audit</h1>
""")

        f.write("<h2>Document Metadata</h2><ul>")
        for k, v in meta.items():
            f.write(f"<li>{k}: {html.escape(v)}</li>")
        f.write("</ul>")

        f.write("""
<div class="container">
<div class="pane">
<h2>Rendered Text</h2>
""")

        for k, t in paragraphs.items():
            f.write(f"<p><b>{k}</b>: {html.escape(t)}</p>")

        f.write("""
</div>
<div class="pane">
<h2>Tracked Revisions</h2>
""")

        for r in revisions:
            cls = "ins" if r["type"] == "ins" else "del"
            bulk = " (bulk insertion heuristic)" if r["bulk"] else ""
            f.write(
                f"<p class='{cls}'>"
                f"<b>{r['type'].upper()}</b> — {r['author']}<br>"
                f"<span class='meta'>{format_date(r['date'])} — [{r['paragraph']}]</span><br>"
                f"{html.escape(r['text'])}{bulk}"
                f"</p>"
            )

        f.write("<h3>Formatting & Structural Anomalies</h3>")
        for p, a in anomalies.items():
            f.write(f"<p class='warn'>[{p}] {', '.join(a)}</p>")

        f.write("<h3>Stylometric Contrast</h3>")
        for p in contrast:
            f.write(f"<p class='warn'>[{p}] Deviates from surrounding paragraphs</p>")

        f.write("</div></div></body></html>")

    return out

# ---------------- Entrypoints ----------------

def main(docx):
    meta = extract_core_metadata(docx)
    data = analyze(docx)
    render_html(docx, meta, data)

def run(docx):
    main(docx)
