#!/usr/bin/env python3
"""Automated visual/structural QA for regenerated PDFs.

Usage: python3 -I qa_pdf.py ARCHIVE_ROOT PILOT_DIR key [key...]
For each key writes PILOT_DIR/<key>/qa.json and PILOT_DIR/<key>/contact.jpg (thumbnail grid of all pages),
and PILOT_DIR/qa_report.md summarising everything.

Checks
  log        LaTeX errors, overfull boxes (count, worst pt), undefined citations/references, missing graphics
  text       words in PDF vs words in the HTML body (coverage); lost sections (headings present in HTML but not PDF)
  figures    images embedded in PDF vs figure nodes in HTML
  pages      per page: ink fraction, ink in margins (overflow), large blank regions (float gaps), pages that are only floats
  smalltext  words rendered below 6 pt (scaled tables)
  ratio      pages vs PubPub PDF pages
"""
import sys, re, json, pathlib, subprocess, html, statistics
ROOT, PD = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); keys = sys.argv[3:]
def run(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)
def words_of(t): return re.findall(r"[A-Za-z]{3,}", t.lower())

def page_metrics(pdf, outdir):
    """Render pages at 40 dpi greyscale and measure ink distribution."""
    import struct, zlib
    n = int(re.search(r"Pages:\s+(\d+)", run(["pdfinfo", str(pdf)]).stdout).group(1))
    metrics = []
    for p in range(n):
        pgm = outdir / f"_p{p}.pgm"
        run(["magick", "-density", "40", f"{pdf}[{p}]", "-background", "white", "-flatten", "-colorspace", "Gray", "-depth", "8", str(pgm)])
        data = pgm.read_bytes()
        # parse binary PGM
        parts = data.split(b"\n", 3); w, h = map(int, parts[1].split()); pix = parts[3]
        rows = [pix[i*w:(i+1)*w] for i in range(h)]
        ink = lambda x0, x1, y0, y1: sum(1 for y in range(y0, y1) for v in rows[y][x0:x1] if v < 128) / max(1, (x1-x0)*(y1-y0))
        # nimeart: text block ~ 0.75in margins at letter size -> at 40dpi, margin 30px; body from y≈45 (below header) to h-30
        mx, top, bot = 30, 45, h - 30
        body = ink(mx, w-mx, top, bot)
        margin_ink = max(ink(0, mx-6, top, bot), ink(w-mx+6, w, top, bot), ink(mx, w-mx, bot+6, h))
        # blank bands: consecutive body rows with no ink, measured as fraction of body height (largest gap not at the end)
        rowink = [any(v < 128 for v in rows[y][mx:w-mx]) for y in range(top, bot)]
        gaps, cur = [], 0
        for r in rowink:
            cur = cur + 1 if not r else 0
            gaps.append(cur)
        # trailing blank (end of paper) is fine on the last page only
        trailing = 0
        for r in reversed(rowink):
            if r: break
            trailing += 1
        interior_gap = max(gaps[:len(gaps)-trailing] or [0]) / max(1, len(rowink))
        metrics.append({"page": p+1, "ink": round(body, 3), "margin_ink": round(margin_ink, 4), "interior_gap": round(interior_gap, 2), "trailing_blank": round(trailing/max(1,len(rowink)), 2)})
        pgm.unlink()
    return metrics

def small_text(pdf):
    """Words set below 0.6x the body text size, ignoring running head/foot zones. Body size = median word height."""
    out = run(["pdftotext", "-bbox", str(pdf), "-"]).stdout
    ph = float((re.search(r'<page width="[\d.]+" height="([\d.]+)"', out) or [0, "792"])[1])
    rows = [(float(a), float(b) - float(a)) for a, b in re.findall(r'yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)"', out)]
    sizes = [h for y, h in rows if 85 < y < ph - 70]
    if not sizes: return 0, 0
    body = statistics.median(sizes)
    return sum(1 for s in sizes if s < 0.6 * body), len(sizes)

report = {}
for k in keys:
    d = PD / k; pdf = d / "paper.pdf"; item = next(ROOT.glob(f"*/*/*/{k}"))
    uuid = next(item.glob("*.xml")).stem
    htm = (item / f"{uuid}.html").read_text(errors="replace")
    body = htm[htm.index('<div class="editor Prosemirror">'):]
    notes_i = body.find('<div class="pub-notes">'); body_main = body[:notes_i] if notes_i > 0 else body
    html_text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style).*?</\1>", " ", body_main, flags=re.S)))
    html_words = words_of(html_text); heads = [html.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", body_main, re.S)]
    n_fig_html = len(re.findall(r'data-node-type="image"', body_main))
    q = {"key": k}
    if not pdf.exists():
        q["status"] = "no pdf"; report[k] = q; continue
    log = (d / "paper.log").read_text(errors="replace")
    q["latex_errors"] = len(re.findall(r"^! ", log, re.M))
    over = [float(x) for x in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide", log)]
    q["overfull"] = len(over); q["overfull_max_pt"] = round(max(over), 1) if over else 0
    q["undefined_cites"] = len(re.findall(r"Citation `[^']+' on page \d+ undefined", log)); q["undefined_refs"] = 1 if "There were undefined references" in log else 0
    q["missing_graphics"] = len(re.findall(r"File `[^']+' not found", log))
    pdf_text = run(["pdftotext", "-layout", str(pdf), "-"]).stdout
    pw = words_of(pdf_text)
    q["pdf_words"] = len(pw); q["html_words"] = len(html_words)
    q["word_coverage"] = round(len(pw) / max(1, len(html_words)), 2)
    pdf_low = pdf_text.lower()
    q["missing_headings"] = [h for h in heads if h and not re.match(r"(?i)(abstract|author keywords|keywords|ccs concepts)$", h.strip()) and re.sub(r"\s+", " ", h.lower())[:30] not in re.sub(r"\s+", " ", pdf_low)][:8]
    texsrc = (d / "paper.tex").read_text(errors="replace")
    q["pdf_images"] = len(re.findall(r"\\includegraphics", texsrc)) - q["missing_graphics"]; q["html_figures"] = n_fig_html + len(re.findall(r"<img\b", re.sub(r"<figure[^>]*data-node-type=\"image\".*?</figure>", "", body_main, flags=re.S)))
    q["figures_not_in_archive"] = len(re.findall(r"not in archive", texsrc))
    q["pages"] = int(re.search(r"Pages:\s+(\d+)", run(["pdfinfo", str(pdf)]).stdout).group(1))
    orig = [p for p in item.glob("*.pdf")]
    q["pubpub_pages"] = int(re.search(r"Pages:\s+(\d+)", run(["pdfinfo", str(orig[0])]).stdout).group(1)) if orig else None
    sm, tot = small_text(pdf); q["small_words"] = sm; q["small_word_frac"] = round(sm / max(1, tot), 3)
    pm = page_metrics(pdf, d); q["pages_detail"] = pm
    q["pages_overflow"] = [m["page"] for m in pm if m["margin_ink"] > 0.002]
    q["pages_big_gap"] = [m["page"] for m in pm if m["interior_gap"] > 0.25]
    q["pages_sparse"] = [m["page"] for m in pm if m["ink"] < 0.03 and m["page"] != q["pages"]]
    # contact sheet
    run(["montage", "-density", "30", str(pdf), "-tile", "6x", "-geometry", "+4+4", "-background", "white", "-bordercolor", "#999", "-border", "1", str(d / "contact.jpg")])
    flags = []
    if q["latex_errors"]: flags.append(f"{q['latex_errors']} LaTeX errors")
    if q["word_coverage"] < 0.85: flags.append(f"text coverage {q['word_coverage']}")
    if q["missing_headings"]: flags.append(f"missing headings: {q['missing_headings'][:3]}")
    if q["pdf_images"] < q["html_figures"]: flags.append(f"images {q['pdf_images']}/{q['html_figures']}")
    if q["overfull_max_pt"] > 20: flags.append(f"overfull up to {q['overfull_max_pt']}pt")
    if q["pages_overflow"]: flags.append(f"margin overflow p{q['pages_overflow']}")
    if q["pages_big_gap"]: flags.append(f"large gaps p{q['pages_big_gap']}")
    if q["pages_sparse"]: flags.append(f"sparse pages {q['pages_sparse']}")
    if q["small_word_frac"] > 0.01: flags.append(f"small text {q['small_word_frac']*100:.0f}% of words")
    if q["undefined_cites"] or q["undefined_refs"]: flags.append("undefined cites/refs")
    q["flags"] = flags
    json.dump(q, open(d / "qa.json", "w"), indent=1)
    report[k] = q
    print(k, "|", "; ".join(flags) or "clean", flush=True)
lines = ["# QA report", "", "| key | pages (PubPub) | words PDF/HTML | images PDF/HTML | LaTeX err | overfull (max pt) | small text | flags |", "|---|---|---|---|---|---|---|---|"]
for k, q in report.items():
    if q.get("status"): lines.append(f"| {k} | — | — | — | — | — | — | **{q['status']}** |"); continue
    lines.append(f"| {k} | {q['pages']} ({q['pubpub_pages']}) | {q['pdf_words']}/{q['html_words']} = {q['word_coverage']} | {q['pdf_images']}/{q['html_figures']} | {q['latex_errors']} | {q['overfull']} ({q['overfull_max_pt']}) | {q['small_word_frac']*100:.1f}% | {'; '.join(q['flags']) or 'clean'} |")
(PD / "qa_report.md").write_text("\n".join(lines) + "\n")
json.dump(report, open(PD / "qa_report.json", "w"), indent=1)
