#!/usr/bin/env python3
"""Build the experimental static site from the PubPub export.
Usage: python3 -I build_site.py ARCHIVE_ROOT WORKDIR OUT_DIR
WORKDIR holds inventory.json, slugs.json, assets.json, embeds.json, site-build/media (from optimise_media.py).
"""
import sys, re, json, html, pathlib, shutil, base64, collections
ROOT, WORK, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
inv = json.load(open(WORK / "inventory.json")); assets = json.load(open(WORK / "assets.json"))
embeds = json.load(open(WORK / "embeds.json")); media_map = json.load(open(WORK / "site-build/media/media_map.json"))
MEDIA_SRC = WORK / "site-build/media"
TRACK = {"papers": "Papers", "papers(full_short_demo)": "Papers", "music": "Music", "installations": "Installations",
         "workshops": "Workshops", "work-in-progress_showcase": "Work-in-Progress Showcase", "demo": "Demos"}
TRACK_SLUG = {"papers": "papers", "papers(full_short_demo)": "papers", "music": "music", "installations": "installations",
              "workshops": "workshops", "work-in-progress_showcase": "wip", "demo": "demos"}
YEAR_INFO = {2021: "NIME 2021 · Shanghai (online)", 2022: "NIME 2022 · Auckland (hybrid)"}
embed_status = {}
for nu, r in embeds.items():
    for raw in r["raw"]: embed_status[raw] = (r["status"], r.get("title"))

def resize_to_asset(url):
    """Decode a resize-v3.pubpub.org URL into its assets.pubpub.org URL."""
    m = re.match(r"https://resize-v3\.pubpub\.org/([A-Za-z0-9+/=_-]+)", url)
    if not m: return url
    try:
        j = json.loads(base64.b64decode(m.group(1) + "==")); return f"https://{j['bucket']}/{j['key']}"
    except Exception: return url

def item_url(it):  # relative path of item page from site root
    return f"{it['year']}/{TRACK_SLUG[it['collection']]}/{it['folder']}/"

def web_media(url, dest_dir):
    """Copy optimised image for url into dest_dir; return relative filename or None."""
    mm = media_map.get(url)
    if not mm or "web" not in mm: return None
    src = MEDIA_SRC / mm["web"]; dst = dest_dir / "img" / pathlib.Path(mm["web"]).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists(): shutil.copy(src, dst)
    return f"img/{dst.name}"

def poster(url, dest_dir):
    mm = media_map.get(url)
    if not mm or not mm.get("poster"): return None, mm
    src = MEDIA_SRC / mm["poster"]; dst = dest_dir / "img" / ("poster_" + pathlib.Path(mm["poster"]).name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists(): shutil.copy(src, dst)
    return f"img/{dst.name}", mm

def fmt_bytes(b):
    return f"{b/1e9:.1f} GB" if b >= 1e9 else f"{b/1e6:.0f} MB" if b >= 1e6 else f"{b/1e3:.0f} KB"

def status_badge(url):
    st, title = embed_status.get(url, ("unchecked", None))
    cls = "ok" if st == "live" else "unk" if st == "unchecked" else "bad"
    label = {"live": "link live", "unchecked": "not checked"}.get(st, f"unavailable ({st})")
    return f'<span class="badge {cls}">{label}</span>' + (f" <span class=\"muted\">{html.escape(title)}</span>" if title else "")

def process_body(body, it, dest_dir, notes):
    """Rewrite the PubPub editor HTML for offline use."""
    # images: figure[data-node-type=image] with data-url
    def img_fig(m):
        fig = m.group(0)
        url = re.search(r'data-url="([^"]+)"', fig)
        url = html.unescape(url.group(1)) if url else None
        cap = re.search(r'data-caption="([^"]*)"', fig); cap = html.unescape(cap.group(1)) if cap else ""
        alt = re.search(r'data-alt-text="([^"]*)"', fig); alt = html.unescape(alt.group(1)) if alt else ""
        fid = re.search(r'<figure id="([^"]+)"', fig); fid = fid.group(1) if fid else ""
        existing_cap = re.search(r"<figcaption.*?</figcaption>", fig, re.S)
        local = web_media(url, dest_dir) if url else None
        src = local or url
        note = "" if local else '<div class="warn">figure not in archive; shown from PubPub CDN</div>'
        capt = existing_cap.group(0) if existing_cap else (f"<figcaption>{cap}</figcaption>" if cap else "")
        return f'<figure id="{fid}" class="image"><a href="{html.escape(url or src)}"><img src="{src}" alt="{html.escape(re.sub("<[^>]+>","",alt or cap))}" loading="lazy"></a>{capt}{note}</figure>'
    body = re.sub(r'<figure[^>]*data-node-type="image"[^>]*>.*?</figure>', img_fig, body, flags=re.S)
    # stray <img> outside figures (e.g. inside table cells)
    def img_tag(m):
        tag = m.group(0)
        src = re.search(r'\ssrc="([^"]+)"', tag); srcset = re.search(r'srcSet="([^"]+)"', tag, re.I)
        url = html.unescape(src.group(1)) if src else (resize_to_asset(srcset.group(1).split()[0]) if srcset else None)
        if url and "resize-v3" in url: url = resize_to_asset(url)
        local = web_media(url, dest_dir) if url else None
        return f'<img src="{local or url}" loading="lazy">'
    body = re.sub(r"<img\b[^>]*>", img_tag, body)
    # video
    def vid(m):
        fig = m.group(0); url = re.search(r'<video[^>]*\ssrc="([^"]+)"', fig); url = html.unescape(url.group(1)) if url else None
        capt = re.search(r"<figcaption.*?</figcaption>", fig, re.S); capt = capt.group(0) if capt else ""
        p, mm = poster(url, dest_dir) if url else (None, None)
        size = assets.get(url, {}).get("bytes"); dur = mm.get("duration") if mm else None
        meta = " · ".join(x for x in [fmt_bytes(size) if size else None, f"{float(dur)/60:.0f} min" if dur and float(dur) > 90 else (f"{float(dur):.0f} s" if dur else None)] if x)
        srcnote = f'<div class="muted">archive file: <code>{html.escape(mm["source_file"])}</code></div>' if mm and mm.get("source_file") else ""
        notes["videos"].append(url)
        img = f'<img src="{p}" alt="video still" loading="lazy">' if p else '<div class="noposter">video</div>'
        return (f'<figure class="video"><a class="media-link" href="{html.escape(url or "#")}">{img}<span class="play">▶</span></a>'
                f'{capt}<div class="media-meta">Video hosted on PubPub CDN ({meta}). Not included in this static site.{srcnote}</div></figure>')
    body = re.sub(r'<figure[^>]*data-node-type="video"[^>]*>.*?</figure>', vid, body, flags=re.S)
    # audio
    def aud(m):
        fig = m.group(0); url = re.search(r'<audio[^>]*\ssrc="([^"]+)"', fig); url = html.unescape(url.group(1)) if url else None
        capt = re.search(r"<figcaption.*?</figcaption>", fig, re.S); capt = capt.group(0) if capt else ""
        size = assets.get(url, {}).get("bytes"); notes["audio"].append(url)
        return (f'<figure class="audio"><audio controls preload="none" src="{html.escape(url)}"></audio>{capt}'
                f'<div class="media-meta">Audio streamed from PubPub CDN ({fmt_bytes(size) if size else "size unknown"}). <a href="{html.escape(url)}">Download</a></div></figure>')
    body = re.sub(r'<figure[^>]*data-node-type="audio"[^>]*>.*?</figure>', aud, body, flags=re.S)
    # iframe embeds
    def ifr(m):
        fig = m.group(0)
        url = re.search(r'<iframe[^>]*\ssrc="([^"]+)"', fig); url = html.unescape(url.group(1)) if url else ""
        if url.startswith("data:"):
            alt = re.search(r'<iframe[^>]*\salt="([^"]*)"', fig); alt = html.unescape(alt.group(1)) if alt else ""
            u2 = re.search(r'href="([^"]+)"', alt); url = u2.group(1) if u2 else ""
        capt = re.search(r"<figcaption.*?</figcaption>", fig, re.S); capt = capt.group(0) if capt else ""
        notes["embeds"].append(url)
        return (f'<figure class="embed"><div class="embed-card">External content: <a href="{html.escape(url)}">{html.escape(url)}</a> {status_badge(url)}</div>{capt}</figure>')
    body = re.sub(r'<figure[^>]*data-node-type="iframe"[^>]*>.*?</figure>', ifr, body, flags=re.S)
    # attached files
    def fil(m):
        fig = m.group(0); url = re.search(r'data-url="([^"]+)"', fig); url = html.unescape(url.group(1)) if url else ""
        name = re.search(r'data-file-name="([^"]*)"', fig); name = html.unescape(name.group(1)) if name else url
        size = re.search(r'data-file-size="([^"]*)"', fig); size = size.group(1) if size else ""
        notes["files"].append(url)
        return f'<div class="file-card">Attachment: <a href="{html.escape(url)}">{html.escape(name)}</a> <span class="muted">{size} · on PubPub CDN</span></div>'
    body = re.sub(r'<figure[^>]*data-node-type="file"[^>]*>.*?</figure>', fil, body, flags=re.S)
    body = re.sub(r'<span class="katex-html" aria-hidden="true">.*?</span></span></span>', '</span></span>', body, flags=re.S)
    body = re.sub(r'<div id="[^"]*" data-node-type="math-block"', '<div class="math-block"', body)
    # strip editor attributes that are noise
    body = re.sub(r'\s(data-value|data-unstructured-value|data-structured-value|data-custom-label|date-structured-value|spellcheck|data-colwidth)="[^"]*"', "", body)
    body = re.sub(r'<p id="[^"]*"', "<p", body)
    return body

def page(title, body, depth, extra_head=""):
    rel = "../" * depth
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><link rel="stylesheet" href="{rel}style.css">{extra_head}</head><body>
<header class="site"><a href="{rel}index.html">NIME 2021–2022 archive</a> <span class="muted">experimental static edition of the PubPub proceedings</span></header>
<main>{body}</main>
<footer class="site">Built from Stefano Fasciani's December 2025 export of <a href="https://nime.pubpub.org">nime.pubpub.org</a>. Content © the authors, <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. The PubPub version is the version of record. <a href="https://github.com/NIME-conference/nime-website/issues/94">Discussion</a>.</footer>
</body></html>"""

CSS = """
:root{--fg:#1d1d1f;--bg:#fff;--muted:#6b6b70;--line:#e3e3e6;--acc:#0a5c8a;--warn:#9a5b00;--bad:#a12626;--ok:#1b7a3a;--max:46rem}
@media(prefers-color-scheme:dark){:root{--fg:#e8e8ea;--bg:#131316;--muted:#9a9aa1;--line:#2c2c31;--acc:#6fb3dd;--warn:#e0a94a;--bad:#ef7b7b;--ok:#6fcf8f}}
*{box-sizing:border-box}body{margin:0;font:17px/1.6 Georgia,"Times New Roman",serif;color:var(--fg);background:var(--bg)}
header.site,footer.site{font:14px/1.5 system-ui,sans-serif;padding:.8rem 1rem;border-bottom:1px solid var(--line)}footer.site{border-top:1px solid var(--line);border-bottom:0;margin-top:3rem}
header.site a{font-weight:600;color:var(--fg);text-decoration:none;margin-right:.6rem}
main{max-width:var(--max);margin:0 auto;padding:1rem 16px}a{color:var(--acc)}.muted{color:var(--muted)}
h1.title{font-size:1.9rem;line-height:1.2;margin:.5rem 0}.byline{font-family:system-ui,sans-serif;font-size:1rem}.byline .aff{color:var(--muted);font-size:.9rem}
.meta{font:14px/1.6 system-ui,sans-serif;border:1px solid var(--line);border-radius:8px;padding:.7rem 1rem;margin:1rem 0;display:grid;grid-template-columns:max-content 1fr;gap:.1rem 1rem}
.meta b{font-weight:600}.abstract{border-left:3px solid var(--line);padding-left:1rem;margin:1.2rem 0}
figure{margin:1.5rem 0}figure img{max-width:100%;height:auto;display:block;margin:0 auto}figcaption{font:14px/1.5 system-ui,sans-serif;color:var(--muted);margin-top:.4rem}
figure.video a.media-link{position:relative;display:block}figure.video .play{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-size:3rem;color:#fff;text-shadow:0 0 12px #000}
.media-meta,.embed-card,.file-card,.warn{font:13px/1.5 system-ui,sans-serif;color:var(--muted);background:color-mix(in srgb,var(--line) 40%,transparent);padding:.4rem .7rem;border-radius:6px;margin-top:.3rem}
.warn{color:var(--warn)}.badge{font:12px/1 system-ui,sans-serif;padding:.15rem .45rem;border-radius:999px;border:1px solid}.badge.ok{color:var(--ok)}.badge.bad{color:var(--bad)}.badge.unk{color:var(--muted)}
.noposter{background:#333;color:#ccc;height:10rem;display:grid;place-items:center}
table{border-collapse:collapse;font-size:.9rem;max-width:100%;display:block;overflow-x:auto}td,th{border:1px solid var(--line);padding:.3rem .5rem;vertical-align:top}td p{margin:.2rem 0}td img{max-width:14rem}
.pub-notes{font-size:.95rem;border-top:1px solid var(--line);margin-top:2rem}.pub-notes h1{font-size:1.3rem}.pub-notes li{margin:.4rem 0}.return-link{text-decoration:none}
.editor .footnote,.editor .citation{text-decoration:none;font-size:.8em;vertical-align:super}
ul.items{list-style:none;padding:0}ul.items li{padding:.5rem 0;border-bottom:1px solid var(--line)}ul.items .t{font-weight:600}ul.items .a{color:var(--muted);font-size:.95rem;font-family:system-ui,sans-serif}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:1rem;font-family:system-ui,sans-serif}.card{border:1px solid var(--line);border-radius:8px;padding:1rem}.card b{font-size:1.1rem}
.editor h1{font-size:1.4rem;margin-top:2rem}.editor h2{font-size:1.2rem}.editor h3{font-size:1.05rem}
.math-block{overflow-x:auto;text-align:center;margin:1rem 0}
"""

OUT.mkdir(parents=True, exist_ok=True); (OUT / "style.css").write_text(CSS)
by_year = collections.defaultdict(lambda: collections.defaultdict(list))
report = []
for it in inv:
    d = ROOT / it["path"]; u = it["pubpub_uuid"]
    htm = (d / f"{u}.html").read_text(errors="replace")
    cover = re.search(r'<section class="cover">(.*?)</section>', htm, re.S).group(1)
    names = [n for n in (re.sub(r"^[,\s]+|[,\s]+$", "", x) for x in re.findall(r'<span class="name">(.*?)</span>', cover, re.S)) if re.sub(r"<[^>]+>", "", n).strip()]
    affs = {k: v for k, v in re.findall(r'<span class="affiliation"><sup>(\d+)</sup>(.*?)</span>', cover, re.S)}
    body_m = re.search(r'<div class="editor Prosemirror">(.*?)</div>\s*(?:<div class="pub-notes">(.*))?\s*</body>', htm, re.S)
    if not body_m:
        body_m = re.search(r'<div class="editor Prosemirror">(.*)', htm, re.S); notes_html = ""
        body_html = body_m.group(1) if body_m else "<p><em>No body export.</em></p>"
    else:
        body_html, notes_html = body_m.group(1), body_m.group(2) or ""
    dest = OUT / item_url(it); dest.mkdir(parents=True, exist_ok=True)
    notes = {"videos": [], "audio": [], "embeds": [], "files": []}
    body = process_body(body_html, it, dest, notes)
    notes_html = re.sub(r'\s(data-value|data-unstructured-value|spellcheck)="[^"]*"', "", notes_html)
    # math: PubPub exports KaTeX HTML + MathML; keep as is (MathML renders natively in modern browsers)
    authors_html = ", ".join(f'{n}' for n in names) if names else html.escape(", ".join(it["authors"]))
    affs_html = "; ".join(f"<sup>{k}</sup>{v}" for k, v in affs.items())
    pdfs = [f for f in d.iterdir() if f.suffix == ".pdf"]
    pubpub_pdf = f"https://nime.pubpub.org/pub/{it['pubpub_slug']}/download/pdf"
    nimeorg_pdf = None
    ext_links = []
    for url, st in it["external_links"]:
        if url not in notes["embeds"]: ext_links.append(url)
    meta_rows = [("Track", f"{TRACK[it['collection']]} · {YEAR_INFO[it['year']]}")]
    if it["bib_key"]: meta_rows.append(("BibTeX key", f"<code>{it['bib_key']}</code>"))
    if it["doi"]: meta_rows.append(("DOI", f'<a href="https://doi.org/{it["doi"]}">{it["doi"]}</a>' + ("" if it["doi_registered"] else ' <span class="badge unk">not registered</span>')))
    meta_rows.append(("Version of record", f'<a href="{it["pubpub_url"]}">{it["pubpub_url"]}</a>'))
    meta_rows.append(("PDF", f'<a href="{pubpub_pdf}">PubPub PDF</a>' + (f' · author-supplied PDF in archive: <code>{it["author_pdf"][0]}</code>' if it["author_pdf"] else "")))
    if it["presentation_video"]: meta_rows.append(("Presentation video", f'<a href="{it["presentation_video"]}">{it["presentation_video"]}</a> {status_badge(it["presentation_video"])}'))
    if it["local_media"]: meta_rows.append(("Media in archive", ", ".join(f"<code>{m}</code>" for m in it["local_media"])))
    if ext_links: meta_rows.append(("Other external links", "<br>".join(f'<a href="{html.escape(x)}">{html.escape(x)}</a> {status_badge(x)}' for x in ext_links)))
    meta_rows.append(("Licence", 'CC BY 4.0'))
    meta = "".join(f"<b>{k}</b><span>{v}</span>" for k, v in meta_rows)
    crumbs = f'<nav class="muted"><a href="../../../index.html">Archive</a> › <a href="../../index.html">{it["year"]}</a> › <a href="../index.html">{TRACK[it["collection"]]}</a></nav>'
    abstract = ""
    am = re.search(r"<abstract>(.*?)</abstract>", (d / f"{u}.xml").read_text(errors="replace"), re.S)
    first_heads = [h.lower() for h in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", body, re.S)[:2]]
    if am and not any("abstract" in h for h in first_heads): abstract = f'<div class="abstract"><b>Abstract.</b> {re.sub(r"</?p>", " ", am.group(1)).strip()}</div>'
    content = f"""{crumbs}<article><h1 class="title">{html.escape(it['title'])}</h1>
<div class="byline">{authors_html}<div class="aff">{affs_html}</div></div>
<div class="meta">{meta}</div>{abstract}
<div class="editor">{body}</div>
{'<div class="pub-notes">' + notes_html + '</div>' if notes_html.strip() else ''}
</article>"""
    (dest / "index.html").write_text(page(it["title"], content, 3))
    by_year[it["year"]][it["collection"]].append(it)
    report.append({"path": it["path"], **{k: len(v) for k, v in notes.items()}})

# listings
def li(it):
    return f'<li><a class="t" href="{it["folder"]}/">{html.escape(it["title"])}</a><div class="a">{html.escape(", ".join(it["authors"]))}</div></li>'
order = ["papers", "papers(full_short_demo)", "music", "installations", "workshops", "work-in-progress_showcase", "demo"]
for y, colls in by_year.items():
    cards = []
    for c in order:
        if c not in colls: continue
        items = sorted(colls[c], key=lambda i: (int(re.sub(r"\D", "", i["folder"].split("_")[-1]) or 0)))
        tdir = OUT / str(y) / TRACK_SLUG[c]; tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "index.html").write_text(page(f"{TRACK[c]} · NIME {y}", f'<nav class="muted"><a href="../../index.html">Archive</a> › <a href="../index.html">{y}</a></nav><h1>{TRACK[c]} · NIME {y}</h1><ul class="items">{"".join(li(i) for i in items)}</ul>', 2))
        cards.append(f'<a class="card" href="{TRACK_SLUG[c]}/"><b>{TRACK[c]}</b><br>{len(items)} items</a>')
    (OUT / str(y) / "index.html").write_text(page(f"NIME {y}", f'<nav class="muted"><a href="../index.html">Archive</a></nav><h1>{YEAR_INFO[y]}</h1><div class="cards">{"".join(cards)}</div>', 1))
n = len(inv); nimg = sum(1 for v in media_map.values() if "web" in v); nvid = sum(1 for v in media_map.values() if "poster" in v)
index = f"""<h1>NIME 2021–2022 proceedings: experimental static edition</h1>
<p>An experiment in rebuilding the two PubPub-hosted NIME conferences as a plain static website, from the December 2025 export. {n} items: every paper, music and installation work in the proceedings, plus workshops, demos and the work-in-progress showcase. Figures are included (web-optimised, {nimg} images); the {nvid} videos and all audio stay on PubPub's CDN and are shown as a still frame with a link. Citations, footnotes and maths are PubPub's own HTML.</p>
<div class="cards">{"".join(f'<a class="card" href="{y}/"><b>{YEAR_INFO[y]}</b><br>{sum(len(v) for v in by_year[y].values())} items</a>' for y in sorted(by_year))}</div>
<h2>Why this exists</h2><p>PubPub remains the version of record for these years. This site tests whether a self-hosted HTML edition (and, separately, regenerated PDFs in the NIME template) would be a better long-term reading copy than the auto-generated PubPub PDFs. See the <a href="https://github.com/NIME-conference/nime-website/issues/94">discussion issue</a> and the <a href="pdf-pilot/">PDF pilot</a>.</p>
<h2>Known gaps</h2><ul><li>Interactive embeds (YouTube, Vimeo, Google Sheets, p5.js) are links, with a liveness check from October 2026.</li><li>Maths is rendered from PubPub's exported MathML/KaTeX markup; some browsers may differ.</li><li>Tables containing images keep PubPub's layout.</li></ul>"""
(OUT / "index.html").write_text(page("NIME 2021–2022 archive", index, 0))
json.dump(report, open(WORK / "site-build/site_report.json", "w"), indent=1)
print("built", n, "items ->", OUT)
