# NIME 2021–2022 PubPub archive: experimental static edition

An experiment in rebuilding the two PubPub-hosted NIME conferences (2021 Shanghai, 2022 Auckland) as a plain static website, and in regenerating their papers as PDFs in the standard NIME LaTeX template. Discussion: [NIME-conference/nime-website#94](https://github.com/NIME-conference/nime-website/issues/94).

**Site:** https://nime-conference.github.io/nime-pubpub-archive/

PubPub (https://nime.pubpub.org) remains the version of record. This is a test of what a better self-hosted reading copy could look like.

## What is here

- `docs/` — the generated site (GitHub Pages). 297 items: all papers, music and installation works, plus workshops, demos and the WiP showcase. Figures are included, web-optimised (max 1600 px). Videos and audio stay on PubPub's CDN and appear as a still frame plus link. Citations, footnotes and maths are PubPub's own exported HTML.
- `docs/pdf-pilot/` — fourteen papers regenerated in the NIME template from the PubPub export, with LaTeX sources, PubPub originals, contact sheets and QA output. Method and history: `PDF-CONVERSION-LOG.md`.
- `scripts/` — the pipeline (see below).
- `inventory.csv` / `inventory.json` — per-item inventory of the export: identifiers, DOIs, media, external links and their liveness, Wayback coverage.
- `REPORT.md` — what the December 2025 export contains and what it lacks.

## Source

Stefano Fasciani's manual export of nime.pubpub.org (8 December 2025): PubPub's nine per-pub formats (pdf, html, md, tex, docx, odt, epub, JATS xml, txt) plus hand-saved media, ~72 GB. The export itself is not in this repository.

## Pipeline

```
build_manifest.py   walk the export, join with NIME-bibliography       -> manifest.json
crossref_lookup.py  DOI registration + PubPub slug per item            -> crossref.json
check_assets.py     status/size of every assets.pubpub.org reference   -> assets.json
fetch_assets.py     fetch figures + missing media into pubpub_assets/
check_embeds.py     oEmbed liveness of YouTube/Vimeo/SoundCloud links  -> embeds.json
build_inventory.py  merge                                              -> inventory.json/csv
optimise_media.py   web images + video poster frames                   -> site-build/media
build_site.py       static site                                        -> docs/
make_pdf.py         one item -> NIME-template PDF (pandoc + nimeart.cls)
```

`make_pdf.py` uses the HTML export as the body source (the only format that keeps citation markers for the 2021 papers), tokenises citations, footnotes, maths and media, converts with pandoc, and wraps the result in `nimeart.cls`. Structured references (JATS `<ref-list>`, most 2022 papers) go through BibTeX and `ACM-Reference-Format.bst`; pre-formatted citations (most 2021 papers) become a `thebibliography` in the authors' original style.

Licence: content CC BY 4.0 (the authors); scripts MIT.
