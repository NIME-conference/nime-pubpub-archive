# Status and how to resume

_Last updated 2026-10-16 (Friday). Everything below was done in one day; treat it as a working prototype, not a finished system._

## Where things live

| What | Where |
|---|---|
| The PubPub export (72 GB, extracted) | External drive `charles2025`: `/Volumes/charles2025/nime-pubpub-backup/extracted/NIME_PubPub_Backup/`. Zip parts, `README.txt`, `REPORT.md`, `inventory.csv` sit one level up. Not in git. |
| Fetched figures and missing media | Inside each item folder of the export, `pubpub_assets/<bucket>/<file>` (2.76 GB). Not in git. |
| Web-optimised images and video posters | `~/src/nime/pubpub-archive/site-build/media/` (247 MB) with `media_map.json`. The images are also in `docs/` here; the map is in `data/`. |
| This repo (local clone) | `~/src/nime/nime-pubpub-archive` → github.com/NIME-conference/nime-pubpub-archive. GitHub Pages serves `docs/` from `main`. |
| Working folder the scripts were developed in | `~/src/nime/pubpub-archive/` — same scripts as `scripts/` here (verified identical on 2026-10-16), plus logs and `pdf-pilot/` build directories with `.log`, `body_raw.tex`, `figures/`. |
| Live site | https://nime-conference.github.io/nime-pubpub-archive/ (pilot: `/pdf-pilot/`) |
| Discussion | NIME-conference/nime-website#94 (three comments from 2026-10-16 summarise the inventory, the site, and the PDF pilot) |
| NIME template source | `~/src/nime/nime-template` (nimeart.cls copied to `scripts/pdf-pilot/template/`) |
| NIME bibliography | `~/src/nime/NIME-bibliography` (used by `build_manifest.py` for keys/DOIs/presentation videos) |

Gotcha: `~/.gitignore` ignores `*.pdf`. Add PDFs with `git add -f`.

## State of each piece

1. **Inventory of the export** — done. `inventory.csv/json`, `REPORT.md`. 297 items, all media verified against the CDN, figures fetched.
2. **Static site** — complete first version, all 297 items. Known gaps: no search, no BibTeX download, "Image N" labels, interactive embeds are links. `build_site.py` is deterministic; rebuild takes ~1 min.
3. **PDF regeneration** — 14 papers at revision 4, all compiling clean. Method and open issues in `PDF-CONVERSION-LOG.md`. Not yet run on the other 130 papers or on music/installation items (those use a different template section: `nime-music-workshop-template.tex`).
4. **Decisions waiting on humans** (raised on #94):
   - reference style for the ~75 papers with pre-formatted citations (accept mixed, or parse to BibTeX);
   - whether the static-site format is the direction for nime.org integration (see #90, #89 there);
   - external video policy (link only vs mirror).

## To pick up on Monday

```sh
cd ~/src/nime/nime-pubpub-archive && git pull
R=/Volumes/charles2025/nime-pubpub-backup/extracted/NIME_PubPub_Backup   # drive must be mounted
# rebuild one paper
python3 -I scripts/make_pdf.py "$R/2022/in_proceedings/papers/nime2022_1" /tmp/out/nime2022_1
# batch + QA (keys = folder names under the export)
python3 -I scripts/run_batch.py $R /tmp/out nime2022_1 nime2022_2
python3 -I scripts/qa_pdf.py   $R /tmp/out nime2022_1 nime2022_2 && open /tmp/out/qa_report.md
# rebuild the site (needs site-build/media from optimise_media.py, or copy it from the working folder)
python3 -I scripts/build_site.py $R ~/src/nime/pubpub-archive docs
```

Suggested next steps, in order:
0. Quick win first: table header rule placement (log §6 item 10). Every table is affected; the fix is local to `fix_table` in `make_pdf.py`.
1. Decide the reference-style question; if parsing, try AnyStyle on the `pub-notes` text of three 2021 papers.
2. Run the full 144-paper batch into `pdf-pilot/all/`, read `qa_report.md`, fix the top recurring flag, repeat. Log each revision in `PDF-CONVERSION-LOG.md` §4–5.
3. Add the regenerated PDFs to the item pages on the site next to the PubPub PDF link.
4. Music/installation/workshop items: adapt `make_pdf.py` for the music template (shorter, no CCS).
