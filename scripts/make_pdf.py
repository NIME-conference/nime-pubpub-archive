#!/usr/bin/env python3
"""Regenerate a NIME-template PDF from a PubPub export folder (HTML export as the body source).

Usage: python3 -I make_pdf.py ITEM_DIR OUT_DIR [--doi DOI] [--year YYYY]

Pipeline
  HTML cover      -> title, authors, affiliations
  HTML body       -> tokenised (citations, footnotes, maths, figures, media) -> pandoc html->latex -> tokens expanded
  JATS <ref-list> -> BibTeX (pandoc) for structured citations; pre-formatted citation text otherwise
  assets          -> local pubpub_assets/ copies (SVG -> PDF, GIF -> PNG)
  nimeart.cls     -> pdflatex + bibtex
"""
import sys, re, json, subprocess, pathlib, shutil, html, argparse, base64

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "pdf-pilot" / "template"
ap = argparse.ArgumentParser()
ap.add_argument("item"); ap.add_argument("out"); ap.add_argument("--doi"); ap.add_argument("--year", type=int)
args = ap.parse_args()
ITEM = pathlib.Path(args.item); OUT = pathlib.Path(args.out); OUT.mkdir(parents=True, exist_ok=True)
uuid = next(p.stem for p in ITEM.glob("*.xml"))
xml = (ITEM / f"{uuid}.xml").read_text(errors="replace"); htm = (ITEM / f"{uuid}.html").read_text(errors="replace")

def run(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)
def tex_escape(s): return re.sub(r"([&%$#_{}])", r"\\\1", s).replace("~", "\\textasciitilde{}").replace("^", "\\textasciicircum{}")
def h2tex(fragment):
    fragment = re.sub(r'<div class="csl-(?:bib-body|entry)"[^>]*>|</div>', "", fragment)
    return run(["pandoc", "-f", "html", "-t", "latex", "--wrap=none"], input=fragment).stdout.strip()
def strip_tags(s): return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
def resize_to_asset(url):
    m = re.match(r"https://resize-v3\.pubpub\.org/([A-Za-z0-9+/=_-]+)", url)
    if not m: return url
    try: j = json.loads(base64.b64decode(m.group(1) + "==")); return f"https://{j['bucket']}/{j['key']}"
    except Exception: return url

# ---- metadata from cover ------------------------------------------------------
cover = re.search(r'<section class="cover">(.*?)</section>', htm, re.S).group(1)
title = strip_tags(re.search(r'<h1 class="title"[^>]*>(.*?)</h1>', cover, re.S).group(1))
affs = {k: strip_tags(v) for k, v in re.findall(r'<span class="affiliation"><sup>(\d+)</sup>(.*?)</span>', cover, re.S)}
authors = []
for n in re.findall(r'<span class="name">(.*?)</span>', cover, re.S):
    sups = re.findall(r"<sup>([\d,\s]+)</sup>", n); nm = strip_tags(re.sub(r"<sup>.*?</sup>", "", n)).strip(" ,")
    if not nm: continue
    ids = [s.strip() for s in sups[0].split(",")] if sups else []
    authors.append((nm, [affs[a] for a in ids if a in affs]))
orcids = dict(re.findall(r'<contrib-id contrib-id-type="orcid">([^<]+)</contrib-id>\s*<name>\s*<surname>([^<]+)</surname>', xml))
orcids = {v: k for k, v in orcids.items()}
year = args.year or next((int(x.name) for x in ITEM.parents if x.name.isdigit() and len(x.name) == 4), 2022)
doi = args.doi or f"10.21428/92fbeb44.{uuid[:8]}"
conf = {2021: ("NIME '21", "June 14--18, 2021", "Shanghai, China"), 2022: ("NIME '22", "June 28--July 1, 2022", "Auckland, New Zealand")}[year]
abstract_m = re.search(r"<abstract>(.*?)</abstract>", xml, re.S)
abstract_tex = h2tex(abstract_m.group(1)) if abstract_m else ""

# ---- body -------------------------------------------------------------------------
_start = htm.index('<div class="editor Prosemirror">') + len('<div class="editor Prosemirror">')
_notes = htm.find('<div class="pub-notes">')
body = htm[_start:_notes if _notes > 0 else None]; notes = htm[_notes:] if _notes > 0 else ""
body = re.sub(r"</div>\s*</div>\s*</body>\s*</html>\s*$", "", body.strip())
structured = "<ref-list" in xml
# citation order from the notes list (ids -> number)
cite_order = {cid: i + 1 for i, cid in enumerate(re.findall(r'<li id="(citation-[^"]+)-bottom">', notes))}
cite_text = {}
for cid, inner in re.findall(r'<li id="(citation-[^"]+)-bottom">(.*?)<a href="#citation[^"]*" class="return-link">', notes, re.S):
    cite_text[cid] = re.sub(r'<span class="pub-note-content-component"><span></span><span>', "", inner)
footnote_html = {}
TOK = {}
def tok(kind, payload):
    k = f"ZZ{kind}{len(TOK):04d}ZZ"; TOK[k] = payload; return k
extra_bib = []
def cite(mm):
    tag = mm.group(0); cid = re.search(r'id="(citation-[^"]+)-inline"', tag).group(1)
    val = html.unescape(re.search(r'data-value="([^"]*)"', tag).group(1)) if 'data-value="' in tag else ""
    km = re.match(r"\s*@\w+\{([^,]+),", val)
    if structured and km: key = km.group(1).strip()
    else:
        key = f"c{cite_order.get(cid, 0)}"
        if structured:  # mixed: unstructured entry inside a structured paper -> synthesise a bib entry
            txt = strip_tags(cite_text.get(cid, "")) or strip_tags(html.unescape(re.search(r'data-unstructured-value="([^"]*)"', tag).group(1)))
            extra_bib.append((key, txt))
    return tok("CITE", key)
body = re.sub(r'<a [^>]*data-node-type="citation"[^>]*>.*?</a>', cite, body, flags=re.S)
def fn(mm):
    tag = mm.group(0); val = html.unescape(re.search(r'data-value="([^"]*)"', tag).group(1)) if 'data-value="' in tag else ""
    return tok("FN", h2tex(val))
body = re.sub(r'<a [^>]*data-node-type="footnote"[^>]*>.*?</a>', fn, body, flags=re.S)
def replace_balanced(src, open_re, tag, kind):
    """Replace each element matched by open_re (whole start tag, group 1 = data-value) and its balanced closing tag with a token."""
    out, pos = [], 0
    for m in re.finditer(open_re, src):
        if m.start() < pos: continue
        depth, i = 1, m.end()
        while depth and i < len(src):
            o = src.find(f"<{tag}", i); c = src.find(f"</{tag}>", i)
            if c == -1: break
            if o != -1 and o < c: depth += 1; i = o + 1
            else: depth -= 1; i = c + len(tag) + 3
        out.append(src[pos:m.start()]); out.append(tok(kind, html.unescape(m.group(1)))); pos = i
    out.append(src[pos:]); return "".join(out)
body = replace_balanced(body, r'<div[^>]*data-node-type="math-block"[^>]*data-value="([^"]*)"[^>]*>', "div", "MB")
body = replace_balanced(body, r'<span[^>]*data-node-type="math-inline"[^>]*data-value="([^"]*)"[^>]*>', "span", "MI")
def local_graphic(url):
    url = resize_to_asset(html.unescape(url)); rel = url.split("assets.pubpub.org/", 1)[-1]
    src = ITEM / "pubpub_assets" / rel; dst = OUT / "figures" / rel.replace("/", "_"); dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists(): return None
    ext = src.suffix.lower()
    if ext == ".svg":
        dst = dst.with_suffix(".pdf")
        if not dst.exists():
            if shutil.which("rsvg-convert"): run(["rsvg-convert", "-f", "pdf", "-o", str(dst), str(src)])
            else: run(["magick", "-density", "150", str(src), str(dst)])
    elif ext == ".gif":
        dst = dst.with_suffix(".png"); run(["magick", f"{src}[0]", str(dst)])
    elif ext in (".jpg", ".jpeg", ".png"):
        if not dst.exists(): run(["magick", str(src), "-resize", "2400x2400>", "-strip", str(dst)])  # keep print-quality, cap huge originals
    else:
        if not dst.exists(): shutil.copy(src, dst)
    return f"figures/{dst.name}"
fig_n = 0
def figure(mm):
    global fig_n
    fig = mm.group(0); url = re.search(r'data-url="([^"]+)"', fig)
    cap = re.search(r"<figcaption[^>]*>(.*?)</figcaption>", fig, re.S); cap = cap.group(1) if cap else ""
    cap = re.sub(r"<strong[^>]*>\s*(Image|Figure)\s*\d+\s*</strong>", "", cap)
    size = re.search(r'data-size="(\d+)"', fig); size = int(size.group(1)) if size else 100
    path = local_graphic(url.group(1)) if url else None
    fig_n += 1
    return tok("FIG", {"path": path, "cap": h2tex(cap), "size": size, "n": fig_n})
body = re.sub(r'<figure[^>]*data-node-type="image"[^>]*>.*?</figure>', figure, body, flags=re.S)
def media(mm):
    fig = mm.group(0); kind = re.search(r'data-node-type="(\w+)"', fig).group(1)
    url = re.search(r'<(?:video|audio|iframe)[^>]*\ssrc="([^"]+)"', fig) or re.search(r'data-url="([^"]+)"', fig)
    url = html.unescape(url.group(1)) if url else ""
    if url.startswith("data:"):
        alt = re.search(r'<iframe[^>]*\salt="([^"]*)"', fig); alt = html.unescape(alt.group(1)) if alt else ""
        u2 = re.search(r'href="([^"]+)"', alt); url = u2.group(1) if u2 else ""
    cap = re.search(r"<figcaption[^>]*>(.*?)</figcaption>", fig, re.S); cap = cap.group(1) if cap else ""
    label = re.search(r"<strong[^>]*>\s*((?:Video|Audio)\s*\d+)\s*</strong>", cap); label = label.group(1) if label else {"video": "Video", "audio": "Audio", "iframe": "Embedded content", "file": "Attachment"}[kind]
    cap = re.sub(r"<strong[^>]*>\s*(Video|Audio)\s*\d+\s*</strong>", "", cap)
    name = re.search(r'data-file-name="([^"]*)"', fig)
    return tok("MEDIA", {"label": label, "cap": h2tex(cap), "url": url, "name": html.unescape(name.group(1)) if name else None})
body = re.sub(r'<figure[^>]*data-node-type="(?:video|audio|iframe|file)"[^>]*>.*?</figure>', media, body, flags=re.S)
# images inside tables
def img_in_table(mm):
    tag = mm.group(0); src = re.search(r'\ssrc="([^"]+)"', tag); ss = re.search(r'srcSet="([^"]+)"', tag, re.I)
    url = src.group(1) if src else (ss.group(1).split()[0] if ss else "")
    return tok("IMG", local_graphic(url))
body = re.sub(r"<img\b[^>]*>", img_in_table, body)
body = re.sub(r'\s(data-[\w-]+|spellcheck|id)="[^"]*"', "", body)
# CCS concepts / author keywords sections -> metadata
ccs_m = re.search(r"<h[1-3][^>]*>\s*CCS Concepts\s*</h[1-3]>(.*?)(?=<h[1-3]|$)", body, re.S | re.I)
ccs = []
if ccs_m:
    for p in re.findall(r"<p[^>]*>(.*?)</p>", ccs_m.group(1), re.S):
        t = strip_tags(p).strip(" •;.")
        t = re.sub(r"ZZMI\d{4}ZZ", "→", t)
        if t: ccs.append(re.sub(r"\s*→\s*", "~", t.strip(" •;.")))
    body = body.replace(ccs_m.group(0), "")
kw_m = re.search(r"<h[1-3][^>]*>\s*(?:Author )?Keywords\s*</h[1-3]>(.*?)(?=<h[1-3]|$)", body, re.S | re.I)
keywords = strip_tags(kw_m.group(1)) if kw_m else ""
if kw_m: body = body.replace(kw_m.group(0), "")
abs_m = re.search(r"<h[1-3][^>]*>\s*Abstract\s*</h[1-3]>(.*?)(?=<h[1-3]|$)", body, re.S | re.I)
if abs_m:
    if not abstract_tex: abstract_tex = h2tex(abs_m.group(1))
    body = body.replace(abs_m.group(0), "")

tex = run(["pandoc", "-f", "html", "-t", "latex", "--wrap=none", "--top-level-division=section"], input=body).stdout
(OUT / "body_raw.tex").write_text(tex)

# ---- expand tokens ----------------------------------------------------------------
def expand(mm):
    k = mm.group(0); p = TOK.get(k)
    if p is None: return k
    kind = re.match(r"ZZ([A-Z]+)", k).group(1)
    if kind == "CITE": return f"\\cite{{{p}}}"
    if kind == "FN": return f"\\footnote{{{p}}}"
    if kind == "MI": return f"${p}$"
    if kind == "MB": return f"\n\\begin{{equation}}{p}\\end{{equation}}\n"
    if kind == "IMG": return f"\\includegraphics[width=\\linewidth]{{{p}}}" if p else "[missing image]"
    if kind == "FIG":
        if not p["path"]: return f"[Figure {p['n']} not in archive]"
        wide = p["size"] >= 95 and False  # keep single column for now; wide figures become figure* when needed
        env = "figure*" if wide else "figure"
        return f"\n\\begin{{{env}}}[htbp]\\centering\\includegraphics[width=\\linewidth]{{{p['path']}}}\\caption{{{p['cap']}}}\\end{{{env}}}\n"
    if kind == "MEDIA":
        link = f"\\url{{{p['url']}}}" if p["url"] else ""
        what = f"{p['label']}" + (f" ({tex_escape(p['name'])})" if p["name"] else "")
        return f"\n\\begin{{quote}}\\small\\textbf{{{what}.}} {p['cap']} {('Available at ' + link + '.') if link else ''}\\end{{quote}}\n"
    return k
tex = re.sub(r"ZZ[A-Z]+\d{4}ZZ", expand, tex)
tex = re.sub(r"(\\cite\{[^}]+\})(\s*\\cite\{[^}]+\})+", lambda mm: "\\cite{" + ",".join(re.findall(r"\\cite\{([^}]+)\}", mm.group(0))) + "}", tex)
tex = tex.replace("\\tightlist", "")
tex = re.sub(r"^\\hfill\\break\s*$", "", tex, flags=re.M)
tex = tex.replace("\\hfill\\break\n", "")
# tables: pandoc longtable -> tabular inside table (two-column friendly); shrink wide ones
def fix_table(mm):
    spec = mm.group(1); inner = mm.group(2)
    ncol = len(re.findall(r"(?<!\\)[lcrp]|>\{", re.sub(r"\{[^{}]*\}", "", spec))) or 1
    inner = re.sub(r"\\endfirsthead|\\endhead|\\endlastfoot|\\endfoot", "", inner)
    cap = re.search(r"\\caption\{(.*?)\}\\tabularnewline", inner, re.S)
    inner = inner.replace(cap.group(0), "") if cap else inner
    capline = f"\\caption{{{cap.group(1)}}}" if cap and not re.fullmatch(r"\s*Table\s*\d+\s*", cap.group(1)) else ""
    # image gallery tables (PubPub authors often lay figures out in a table): figure* with images side by side
    imgs = re.findall(r"\\begin\{figure\}\[htbp\]\\centering(\\includegraphics\[[^\]]*\]\{[^}]+\})\\caption\{(.*?)\}\\end\{figure\}|(\\includegraphics\[[^\]]*\]\{[^}]+\})", inner, re.S)
    stripped = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}|\\includegraphics\[[^\]]*\]\{[^}]+\}", " ", inner, flags=re.S)
    stripped = re.sub(r"\\multicolumn\{\d+\}\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\{%?", " ", stripped)
    words = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?|[&{}\[\]%]|\(\\?[a-z]+ - \d+\\?[a-z]+\) \* \\?real\{[\d.]+\}( \+ \d\\?[a-z]+)?", " ", stripped)
    words = re.sub(r"\s+", " ", words).strip()
    if imgs and len(words) < 160:
        rows = [r for r in re.split(r"\\tabularnewline|\\\\", inner) if "includegraphics" in r]
        out = []
        for r in rows:
            cells = re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", r)
            w = round(0.95 / max(len(cells), 1), 2)
            out.append("".join(f"\\includegraphics[width={w}\\textwidth]{{{c}}}" for c in cells) + "\\\\[2pt]")
        capt = cap.group(1) if cap and capline else words
        env = "figure*" if len(cells) > 1 else "figure"
        return f"\\begin{{{env}}}[htbp]\\centering\n" + "\n".join(out) + (f"\\caption{{{capt}}}" if capt else "") + f"\\end{{{env}}}"
    inner = re.sub(r"\\begin\{figure\}\[htbp\]\\centering(\\includegraphics\[[^\]]*\]\{[^}]+\})\\caption\{(.*?)\}\\end\{figure\}", lambda f: f.group(1) + (" " + f.group(2) if f.group(2).strip() else ""), inner, flags=re.S)
    inner = inner.replace("\\includegraphics[width=\\linewidth]", f"\\includegraphics[width={0.9/ncol:.2f}\\linewidth]")
    spec_fixed = spec.replace("\\linewidth - ", "\\columnwidth - ")
    return f"\\begin{{table}}[htbp]\\centering\\small{capline}\n\\begin{{adjustbox}}{{max width=\\columnwidth}}\\begin{{tabular}}{{{spec_fixed}}}{inner}\\end{{tabular}}\\end{{adjustbox}}\\end{{table}}"
tex = re.sub(r"\\begin\{longtable\}\[\]\{(.*?)\}\n(.*?)\\end\{longtable\}", fix_table, tex, flags=re.S)
tex = tex.replace("\\real{", "\\real{")
# references
if structured:
    bib = run(["pandoc", "-f", "jats", "-t", "bibtex", str(uuid) + ".xml"], cwd=ITEM).stdout
    for key, txt in extra_bib: bib += f"\n@misc{{{key},\n  title = {{{tex_escape(txt)}}}\n}}\n"
    (OUT / "refs.bib").write_text(bib)
    bibblock = "\\bibliographystyle{ACM-Reference-Format}\n\\bibliography{refs}"
else:
    items = [f"\\bibitem{{c{n}}} {h2tex(cite_text[cid]).replace(chr(10), ' ')}" for cid, n in sorted(cite_order.items(), key=lambda x: x[1]) if cid in cite_text]
    bibblock = ("\\begin{thebibliography}{%d}\n%s\n\\end{thebibliography}" % (len(items), "\n".join(items))) if items else ""

auth_tex = []
for nm, afl in authors:
    a = f"\\author{{{tex_escape(nm)}}}"
    if nm in orcids: a += f"\n\\orcid{{{orcids[nm]}}}"
    for af in (afl or [""]): a += "\n\\affiliation{\\institution{" + tex_escape(af) + "}\\country{}}"
    auth_tex.append(a)
short_title = title if len(title) <= 70 else re.sub(r"\s+\S*$", "", title[:67]) + "…"
short = authors[0][0].split()[-1] + (" et al." if len(authors) > 2 else (" and " + authors[1][0].split()[-1] if len(authors) == 2 else "")) if authors else ""
GREEK = {0x3B1:"alpha",0x3B2:"beta",0x3B3:"gamma",0x3B4:"delta",0x3B5:"varepsilon",0x3B6:"zeta",0x3B7:"eta",0x3B8:"theta",0x3B9:"iota",0x3BA:"kappa",0x3BB:"lambda",0x3BC:"mu",0x3BD:"nu",0x3BE:"xi",0x3C0:"pi",0x3C1:"rho",0x3C3:"sigma",0x3C4:"tau",0x3C5:"upsilon",0x3C6:"varphi",0x3C7:"chi",0x3C8:"psi",0x3C9:"omega",0x393:"Gamma",0x394:"Delta",0x398:"Theta",0x39B:"Lambda",0x39E:"Xi",0x3A0:"Pi",0x3A3:"Sigma",0x3A6:"Phi",0x3A8:"Psi",0x3A9:"Omega",
 0x2202:"partial",0x2207:"nabla",0x221A:"surd",0x221D:"propto",0x2211:"sum",0x220F:"prod",0x222B:"int",0x2229:"cap",0x222A:"cup",0x2282:"subset",0x2286:"subseteq",0x2260:"neq",0x2261:"equiv",0x21D0:"Leftarrow",0x21D2:"Rightarrow",0x21D4:"Leftrightarrow",0x2190:"leftarrow",0x2194:"leftrightarrow",0x2191:"uparrow",0x2193:"downarrow",0x2026:"ldots",0x2217:"ast",0x2218:"circ",0x2205:"emptyset",0x2200:"forall",0x2203:"exists",0x00D7:"times",0x00F7:"div",0x2032:"prime",0x2225:"parallel",0x22A5:"perp",0x2220:"angle",0x2297:"otimes",0x2295:"oplus",0x2299:"odot",0x25CB:"circ",0x2062:"",0x2061:""}
uni_block = "".join("\\DeclareUnicodeCharacter{%04X}{\\ensuremath{\\%s}}" % (c, n) if n else "\\DeclareUnicodeCharacter{%04X}{}" % c for c, n in GREEK.items())
ccs_block = "".join("\\ccsdesc{" + tex_escape(c).replace("\\textasciitilde{}", "~") + "}\n" for c in ccs)
kw_block = ("\\keywords{" + tex_escape(keywords) + "}") if keywords else ""
doc = f"""\\documentclass[sigconf]{{nimeart}}
\\usepackage{{bm}}
\\usepackage{{array,calc,adjustbox}}
\\DeclareUnicodeCharacter{{202F}}{{\\,}}\\DeclareUnicodeCharacter{{2009}}{{\\,}}\\DeclareUnicodeCharacter{{200B}}{{}}\\DeclareUnicodeCharacter{{FEFF}}{{}}\\DeclareUnicodeCharacter{{22C5}}{{\\ensuremath{{\\cdot}}}}\\DeclareUnicodeCharacter{{21A9}}{{}}\\DeclareUnicodeCharacter{{2192}}{{\\ensuremath{{\\rightarrow}}}}
\\DeclareUnicodeCharacter{{2248}}{{\\ensuremath{{\\approx}}}}\\DeclareUnicodeCharacter{{2264}}{{\\ensuremath{{\\leq}}}}\\DeclareUnicodeCharacter{{2265}}{{\\ensuremath{{\\geq}}}}
\\DeclareUnicodeCharacter{{2208}}{{\\ensuremath{{\\in}}}}\\DeclareUnicodeCharacter{{221E}}{{\\ensuremath{{\\infty}}}}\\DeclareUnicodeCharacter{{223C}}{{\\ensuremath{{\\sim}}}}
\\DeclareUnicodeCharacter{{2212}}{{\\ensuremath{{-}}}}\\DeclareUnicodeCharacter{{00B1}}{{\\ensuremath{{\\pm}}}}\\DeclareUnicodeCharacter{{2032}}{{\\ensuremath{{'}}}}\\DeclareUnicodeCharacter{{2A09}}{{\\ensuremath{{\\times}}}}
\\DeclareUnicodeCharacter{{03BC}}{{\\ensuremath{{\\mu}}}}\\DeclareUnicodeCharacter{{03C0}}{{\\ensuremath{{\\pi}}}}\\DeclareUnicodeCharacter{{0394}}{{\\ensuremath{{\\Delta}}}}\\DeclareUnicodeCharacter{{03B1}}{{\\ensuremath{{\\alpha}}}}
\\DeclareUnicodeCharacter{{03B2}}{{\\ensuremath{{\\beta}}}}\\DeclareUnicodeCharacter{{03C3}}{{\\ensuremath{{\\sigma}}}}\\DeclareUnicodeCharacter{{03C4}}{{\\ensuremath{{\\tau}}}}\\DeclareUnicodeCharacter{{03C9}}{{\\ensuremath{{\\omega}}}}
\\DeclareUnicodeCharacter{{2713}}{{\\checkmark}}\\DeclareUnicodeCharacter{{2717}}{{\\ensuremath{{\\times}}}}\\DeclareUnicodeCharacter{{25B6}}{{\\ensuremath{{\\blacktriangleright}}}}\\DeclareUnicodeCharacter{{2B06}}{{\\ensuremath{{\\uparrow}}}}\\DeclareUnicodeCharacter{{2B07}}{{\\ensuremath{{\\downarrow}}}}
{uni_block}
\\AtBeginDocument{{\\providecommand\\BibTeX{{{{Bib\\TeX}}}}}}
\\setcopyright{{cc}}\\copyrightyear{{{year}}}\\acmYear{{{year}}}\\acmDOI{{{doi}}}
\\acmConference[{conf[0]}]{{International Conference on New Interfaces for Musical Expression}}{{{conf[1]}}}{{{conf[2]}}}
\\settopmatter{{printacmref=false}}\\acmISBN{{}}
\\providecommand{{\\pandocbounded}}[1]{{#1}}
\\begin{{document}}
\\title[{tex_escape(short_title)}]{{{tex_escape(title)}}}
{chr(10).join(auth_tex)}
\\renewcommand{{\\shortauthors}}{{{tex_escape(short)}}}
\\begin{{abstract}}
{abstract_tex}
\\end{{abstract}}
{ccs_block}
{kw_block}
\\maketitle
{tex}
{bibblock}
\\end{{document}}
"""
(OUT / "paper.tex").write_text(doc)
for f in ("nimeart.cls", "ACM-Reference-Format.bst"): shutil.copy(TEMPLATE / f, OUT / f)
(OUT / "meta.json").write_text(json.dumps({"title": title, "authors": authors, "doi": doi, "year": year, "structured_refs": structured, "ccs": ccs, "keywords": keywords}, indent=1, ensure_ascii=False))
steps = []
for cmd in (["pdflatex", "-interaction=nonstopmode", "paper.tex"], ["bibtex", "paper"], ["pdflatex", "-interaction=nonstopmode", "paper.tex"], ["pdflatex", "-interaction=nonstopmode", "paper.tex"]):
    if cmd[0] == "bibtex" and not structured: continue
    r = run(cmd, cwd=OUT); steps.append((cmd[0], r.returncode))
log = (OUT / "paper.log").read_text(errors="replace")
errs = sorted(set(re.findall(r"^! .*", log, re.M)))
pages = re.search(r"Output written on paper.pdf \((\d+) pages", log)
print(json.dumps({"item": ITEM.name, "pages": int(pages.group(1)) if pages else None, "steps": steps, "latex_errors": errs[:10], "n_err_lines": len(re.findall(r'^! ', log, re.M)),
                  "undefined_cites": len(re.findall(r"Citation `[^']+' on page \d+ undefined", log)), "overfull": len(re.findall(r"Overfull \\hbox", log)),
                  "structured_refs": structured, "n_authors": len(authors), "ccs": len(ccs)}, ensure_ascii=False))
