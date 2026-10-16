# PubPub → NIME-template PDF conversion: working log

A running record of how `scripts/make_pdf.py` evolved, what the QA pass measures, what each revision fixed, and what is still open. The point of this file is that the knowledge survives the session that produced it. Newest entries at the bottom of each section; keep the metrics table current.

Discussion thread: [NIME-conference/nime-website#94](https://github.com/NIME-conference/nime-website/issues/94). Live pilot: https://nime-conference.github.io/nime-pubpub-archive/pdf-pilot/

## 1. The source material and why the pipeline looks the way it does

PubPub's per-pub exports (pdf, html, md, tex, docx, odt, epub, JATS xml, txt) are each lossy in a different way. Findings that decided the design:

| Format | Good | Bad |
|---|---|---|
| **HTML** | Complete body; every citation, footnote, maths node and figure is a tagged node with its source data (`data-value` holds the BibTeX for a citation, the TeX for a formula, the caption for a figure). Cover block has authors and affiliations. Reference list at the end (`pub-notes`). | Images referenced via `resize-v3.pubpub.org` URLs (base64 JSON wrapping the asset key). |
| **JATS XML** | Clean structure; `<ref-list>` with structured references for papers whose authors used PubPub's citation manager. | **Drops citation markers entirely** for pre-formatted ("unstructured") citations, which is most of 2021. No affiliations. Pub date, not conference date. |
| **Markdown** | Front matter (title, authors, abstract, licence, slug). | Hard-wrapped lines break image URLs across lines; bibliography is an external `/tmp/*.json` that was never exported. |
| **LaTeX** | — | pandoc output with `article` class, CSL macros, remote image URLs; not a usable starting point. |

So: **HTML is the body source for everything**, JATS is used only for its `<ref-list>` (via `pandoc -f jats -t bibtex`), the Markdown front matter is a cross-check, and the year/conference come from the archive folder, not the export.

Reference styles split by year: ~70 of 144 papers (almost all 2022) have structured references → BibTeX + `ACM-Reference-Format.bst`. The rest have only the authors' pre-formatted citation text → a `thebibliography` in whatever style they used (APA, IEEE, …). This cannot be fixed automatically; it would need re-keying ~75 reference lists.

## 2. Pipeline (scripts/make_pdf.py)

1. Read HTML; NFC-normalise and drop stray combining marks (`U+0300–036F` broke pdflatex in 3 of 14 papers).
2. Cover block → title, authors (strip `<sup>` markers), affiliations by superscript number; ORCIDs from JATS.
3. Split body from `pub-notes`. Build citation order from the notes list (needed for unstructured citations: `[n]` ↔ list position).
4. **Tokenise** nodes that pandoc would mangle, replacing each with `ZZKIND0000ZZ`:
   citations → `\cite{key}` (key = BibTeX key from `data-value`, escaped the way JATS/pandoc escape ids: `/` → `U002F`, Unicode letters kept); footnotes → `\footnote{}` from `data-value`; maths (inline and block) → TeX from `data-value` via a balanced-tag scanner (the KaTeX markup nests spans, regexes failed); figures → local file + caption; video/audio/iframe/file → a short note with the URL; `<img>` inside tables → includegraphics.
5. Pull CCS Concepts / Keywords / Abstract sections out of the body into template metadata.
6. `pandoc -f html-tex_math_dollars-tex_math_double_backslash -t latex` (the extension names matter: with dollar-maths on, authors' literal `$` in prose became maths and broke a paper).
7. Expand tokens; merge adjacent `\cite{a}\cite{b}` → `\cite{a,b}`; strip `\hyperref[anchor]{}` (anchors do not exist); drop `\hfill\break` paragraphs (PubPub empty paragraphs).
8. **Tables** (pandoc emits `longtable`, which cannot live in two-column mode):
   parse the full multi-line column spec with brace matching (an earlier regex read only its first line and got column counts wrong); keep booktabs rules in the right places; image-only tables → `figure*` with images side by side and the text cells as caption; text tables with no cell > 70 chars → natural-width `l/c/r` columns, `multirow{n}{*}`, wrapped in `adjustbox{max width=…}`; wide tables (≥ 6 columns or long cells) → `table*`.
9. `verbatim` → `fvextra` `Verbatim[breaklines]` (a Faust listing overflowed by 493 pt).
10. Wrap in `nimeart.cls` with `\setcopyright{cc}`, year, DOI, `\acmConference`, short running title (long titles wrapped the header and left a stray comma on its own line).
11. pdflatex → bibtex → pdflatex ×2. Then read the log: any display equation overfull by > 10 pt is wrapped in `\resizebox{0.92\columnwidth}` and the document recompiled (matrices in two 2021 papers).

## 3. QA method (scripts/qa_pdf.py)

Automated, per paper, so the loop is "run batch → read flags → look only at flagged pages → fix → rerun":

- **log**: LaTeX error lines; overfull boxes (count, worst in pt); undefined citations; missing graphics.
- **text coverage**: alphabetic words in the PDF vs in the HTML body (should be ≥ 1 since the PDF adds the reference list; < 0.85 means lost content); section headings in HTML missing from PDF text.
- **figures**: `\includegraphics` count vs `image` nodes + table `<img>`s in HTML; "not in archive" placeholders.
- **page geometry** (40 dpi render, ink counting): ink in the margins (overflow), largest interior blank band (float gaps), near-empty pages.
- **small text**: words set below 0.6× the body size, excluding running head/foot. Flags scaled-down tables; also picks up text inside vector figures, so it is a hint not a fail.
- **contact sheet**: all pages as a thumbnail grid (`contact.jpg`). One glance shows float pile-ups, empty columns, broken tables.
- Everything lands in `qa.json` per paper and `qa_report.md` for the batch.

What the QA cannot see: wrong reference formatting, captions attached to the wrong figure, semantic loss inside tables, and anything about typographic taste. Those need a human pass with the contact sheet as the map.

## 4. Revision history

| Rev | Date | Papers | Change | Effect |
|---|---|---|---|---|
| 1 | 2026-10-16 | 4 | JATS as body source, natbib, remote images localised | Compiled, but 2021 papers lost all citation markers; images in tables broke two-column layout |
| 2 | 2026-10-16 | 4 | HTML as body source; tokenised citations/footnotes/figures/media; author/affiliation from cover; CCS/keywords to metadata | Both years compile; references correct in both modes |
| 3 | 2026-10-16 | 4 | Maths from TeX source via balanced scanner (was MathML → inline); numbered `equation`s; tables natural-width with booktabs; image-grid tables → `figure*`; short running title; empty paragraphs dropped | Equations readable; tables fit; stray header comma gone |
| 4 | 2026-10-16 | 14 | QA tooling; NFC normalisation; dollar-maths extension off; `fvextra` for code; `table*` for wide tables; `xurl`; key escaping `U002F`; duplicate BibTeX entries removed; empty maths nodes skipped; KaTeX-only commands mapped; `\hyperref` anchors stripped; equation auto-resize pass | 14/14 compile with 0 LaTeX errors, 0 undefined citations in 13/14, all figures present |

## 5. Metrics over time (14-paper set)

| Rev | LaTeX errors (papers with any) | undefined citations (papers) | papers with all figures | worst overfull | pages (14 papers) vs PubPub |
|---|---|---|---|---|---|
| 4 start (first batch run) | 4 | 6 | 12 | 493 pt | — |
| 4 end | 0 | 0 | 14 | 24 pt | 113 vs 373 |

Per-paper detail: `docs/pdf-pilot/qa_report.md`.

## 6. Open issues, ranked by how many papers they would affect

1. **Pre-formatted references (≈75 papers).** Come out in the authors' original style, not ACM. Options: accept; or run them through a reference parser (AnyStyle, GROBID) into BibTeX, then review. Half a day of tooling plus review.
2. **Tables longer than a column** (e.g. nime2022_8 taxonomy): placed as a single float, leaving a sparse page. Needs `longtable` in a one-column stretch or splitting by hand.
3. **Code appendices** in two-column layout look poor (nime2022_23). Could switch those sections to `\onecolumn`, or set code at `\scriptsize` in `table*`.
4. **CCS concepts** are typeset from the authors' text (`A~B~C`), not ACM codes; no `\ccsdesc[weight]`. Cosmetic.
5. **Figure placement**: `[htbp]` only; some papers get figure pages. nimeart tolerates this, but a `\FloatBarrier` per section might read better.
6. **"Image N" labels** in body text are PubPub's names; the regenerated captions say "Figure N". Text says "see Image 3", caption says "Figure 3". A regex rewrite of `Image (\d+)` → `Figure \1` in body text is safe in most papers but not all.
7. **Media notes** (video/audio) are a plain quoted paragraph with a URL. A small icon/box would be nicer; the URL points at PubPub's CDN which is fine while PubPub is up.
8. **Vector figures** (SVG → PDF via ImageMagick) rasterise. `rsvg-convert` or `cairosvg` would keep them vector; not installed on the build machine.
9. **Small-text metric** conflates scaled tables with text inside figures. Masking figure regions would fix it.

## 7. How to run

```
# one paper
python3 -I scripts/make_pdf.py <export>/<year>/in_proceedings/papers*/<key> out/<key>
# a batch + QA
python3 -I scripts/run_batch.py <export-root> out key1 key2 ...
python3 -I scripts/qa_pdf.py  <export-root> out key1 key2 ...
open out/qa_report.md out/<key>/contact.jpg
```
Requires: pandoc ≥ 3, TeX Live 2025 (nimeart.cls, booktabs, adjustbox, multirow, fvextra, xurl), ImageMagick, poppler (`pdftotext`, `pdfinfo`), ffmpeg (site only).
