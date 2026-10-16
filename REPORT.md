# NIME PubPub archive: what we have, what we need

> **Framing (2026-10-16, from Charles):** PubPub is alive and the community chose it to host NIME 2021/2022. The goal is a _better local edition_ than PubPub's poor auto-generated PDFs (for nime.org / Zenodo), possibly by regenerating PDFs in NIME's standard format from the exports, and optionally integrating the pages into nime.org. Section 2 below lists risks for completeness, not as an emergency.

## Hosting footprint (measured from the extracted archive)

| Option | Size |
|---|---|
| HTML pages + all figures (incl. 6 attached PDFs) | 1.07 GB |
| + article PDFs | 1.60 GB |
| + audio (47 wav/mp3) | 2.56 GB |
| + all 211 videos as uploaded (full-res originals) | 72.9 GB |

Video is 68.6 GB: 18 files over 1 GB (the top ten alone are 20 GB), 61 between 200 MB and 1 GB, 132 under 200 MB. Re-encoding to 1080p H.265 at ~3 Mbit/s would bring the lot to roughly 8–12 GB; 720p roughly half that. `nime.org` currently has 50 GB in `public_html/proceedings` on a 14 TB volume with 3.4 TB free, so even the full-res option fits; the question is hosting-plan quota and bandwidth, not disk.

_Status as of 2026-10-16. Working files in `~/src/nime/pubpub-archive/`; archive on `/Volumes/charles2025/nime-pubpub-backup/`._

## 1. What we have

**Source.** Stefano Fasciani's offline export of nime.pubpub.org (dated 2025-12-08, shared 2025-12-12 as a 72 GB split zip). Downloaded, size-verified, and extracted to
`/Volumes/charles2025/nime-pubpub-backup/extracted/NIME_PubPub_Backup/` (now 70 GB after gap-filling). Original zip parts kept alongside.

**Scope.** Everything NIME published on PubPub: NIME 2021 (Shanghai/online) and NIME 2022 (Auckland/online). 297 items.

| Year | Papers | Music | Installations | Workshops | WiP showcase / Demos |
|---|---|---|---|---|---|
| 2021 | 88 | 35 | 12 | 9 | 35 |
| 2022 | 56 | 28 | 7 | 7 | 20 |

Paper/music/installation counts and BibTeX keys match `NIME-bibliography` exactly (installation folders carry a `nime20201_`/`nime20202_` typo; mapped in the manifest).

**Per item.** PubPub's nine exports (pdf, html, md, tex, docx, odt, epub, JATS xml, txt) named by pub UUID; inline video/audio saved as `videoN.mp4` / `audioN.wav`; author-supplied PDFs where the pub used one (19 items, replacing the auto PDF); `integrated_web_contents_URL.txt` for some external embeds (55 items, incomplete).

**Identifiers.** Every item now has a PubPub slug (`slugs.json`). 286 of 297 have a Crossref-registered DOI of the form `10.21428/92fbeb44.<first 8 hex of pub UUID>`, including 60 WiP/demo/workshop items the bibliography does not cover. The 11 without a DOI are the 2022 workshops (7), three 2022 demos, and one 2021 workshop.

**Media integrity.** The HTML exports reference 1447 files on `assets.pubpub.org`: 1189 images, 253 videos/audio, 6 PDFs. Of the 253 media files, 241 are byte-identical to the local `videoN`/`audioN` copies (size match), 3 very large ones matched on their first 4 MB (CDN refuses ranged size for them), and 9 were absent locally (including the three `Unconfirmed *.crdownload` stubs). **All 9 missing media files and all 1189 images plus 6 PDFs have now been fetched** from the CDN into each item's `pubpub_assets/<bucket>/<file>` (2.76 GB, verified). The HTML/Markdown exports still point at the CDN URLs; rewriting them to the local paths is a simple sed once the publication format is chosen.

**Already on nime.org** (`public_html/proceedings/`): 2021 paper PDFs (88, named by PubPub UUID, plus 2 extras) and 2022 paper PDFs (56, named by submission number, uploaded 2026-10-12). Not linked from the bibliography, which still points 2021/2022 `url` fields at the PubPub DOIs.

**Wayback Machine** has at least one 200 capture of the pub page for 287 of 297 items (`wayback_cdx.txt`); the latest site-wide crawl is 2025-12-03.

## 2. What is at risk / what we don't have

1. **The DOIs resolve to PubPub.** Prefix 10.21428 belongs to PubPub (Crossref member 9621). When nime.pubpub.org goes dark, 286 DOIs break unless PubPub updates the Crossref resource URLs (or transfers the DOIs to a NIME-held prefix). This is the single most important ask of PubPub/KFG.
2. **External video.** 142 items embed or link YouTube/Vimeo/SoundCloud (453 distinct URLs incl. the bib `presentation-video` fields). 24 are already dead or private (`inventory.csv`, `external_dead`), including 7 paper presentation videos from 2022 (nime2022_6, _8, _16, _25, _38, _49, _55). The rest are live today but outside our control. Music performances are **not** the problem: 61 of 63 music items have their performance video stored locally and verified.
3. **Interactive embeds.** nime2021_1 (30 Google Sheets charts + a Google Map), nime2022_53 (9 p5.js sketches), nime2022_8 (a Vercel app), nime2022_40 (a Vimeo showcase). These only survive as links.
4. **Live PubPub is unreachable from here.** nime.pubpub.org returns a Cloudflare 403 to curl, headless Chrome and WebFetch, so I could not diff against the live site. The asset CDN is open.
5. **Page-level content not in the exports**: PubPub discussions/comments, pub metadata like collections/ordering, the "previous NIMEs" landing pages, and NIME 2021/2022 front matter (chairs' messages etc. if any were pubs they'd be in the archive; none found).
6. **Cosmetic**: 3 `Unconfirmed *.crdownload` stubs (now superseded by fetched files, safe to delete), 2 stray `uuid (1).txt` duplicates, one 2021 workshop with no auto PDF or docx.

## 3. How to get what's missing

| Need | How | Effort |
|---|---|---|
| DOI continuity | Write to PubPub (KFG) asking them to repoint the 286 Crossref resource URLs to nime.org once a landing page per item exists (`https://nime.org/proceedings/2021/<key>.html` or similar). Ask about transferring to NIME's own prefix if NIME has/gets a Crossref membership. | Email + follow-up; blocking for everything else |
| Dead external videos (24) | Ask authors (emails in bib) for files; check Wayback for YouTube captures (rare). The 2022 presentation videos may exist on the NIME 2022 organisers' drive. | Author outreach |
| Live external videos (~430) | Decide policy: (a) keep as links, (b) ask authors for files, or (c) mirror with yt-dlp into `pubpub_assets/`. YouTube's ToS makes (c) a NIME-governance call; the NIME archiving workshop (2022/other/workshops/6) is the place this was discussed. | Policy decision first |
| Interactive embeds | Snapshot as static images/PDF for the record; keep live link. | Small, manual |
| Live-site diff | Someone with browser access (or an IP Cloudflare allows) runs the same checks via the PubPub API: `GET /api/pubs/many` and `/api/collections`. Or ask Stefano for his export script's pub list / API dump. | Low, needs access |
| 11 items without DOIs | Decide whether to mint DOIs when republishing (NIME minted none for workshops in other years either). | Decision |
| Rewrite HTML/MD to local assets | `sed` / small script mapping `https://assets.pubpub.org/<b>/<f>` to `pubpub_assets/<b>/<f>`. | Trivial, do when format chosen |

## 4. Files in this folder

- `build_manifest.py` → `manifest.json/csv` (per-item files, formats, media, remote refs, bib join)
- `crossref_lookup.py` → `crossref.json` (DOI registration, slug, Crossref title)
- `check_assets.py`, `recheck_assets.py` → `assets.json` (status/size of all 1447 CDN assets)
- `fetch_assets.py` → `fetch_report.json` (downloaded images, PDFs, missing media into `pubpub_assets/`)
- `check_embeds.py` → `embeds.json` (oEmbed liveness of YouTube/Vimeo/SoundCloud links)
- `build_inventory.py` → **`inventory.json` / `inventory.csv`** (the merged per-item view; start here)
- `slugs.json`, `missing_media.json`, `wayback_cdx.txt`, `nimeorg_2021.txt`

Re-run order: manifest → crossref/assets/embeds → fetch → inventory. All scripts take paths as arguments and are safe to re-run (fetch is resumable).
