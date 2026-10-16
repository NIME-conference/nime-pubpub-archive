#!/usr/bin/env python3
"""Build a manifest of the NIME PubPub backup archive.

Usage: python3 -I build_manifest.py ARCHIVE_ROOT BIB_DIR OUT_DIR
Writes OUT_DIR/manifest.json and OUT_DIR/manifest.csv.
"""
import csv, json, os, re, sys, html
from pathlib import Path
import yaml

ROOT, BIBDIR, OUT = (Path(a) for a in sys.argv[1:4])
EXPORT_EXTS = ["pdf", "html", "md", "tex", "docx", "odt", "epub", "xml", "txt"]
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MEDIA_EXT = {"mp4", "webm", "m4v", "mov", "wav", "mp3", "m4a", "ogg", "gif"}
IMG_EXT = {"png", "jpg", "jpeg", "gif", "svg", "webp", "tif", "tiff"}
VID_EXT = {"mp4", "webm", "m4v", "mov"}
AUD_EXT = {"wav", "mp3", "m4a", "ogg", "flac", "aiff", "aif"}

# ---- bibliography -------------------------------------------------------
def load_bib():
    entries = {}
    for bib in BIBDIR.rglob("nime202[12]*.bib"):
        text = bib.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"@\w+\{([^,]+),(.*?)\n\}", text, re.S):
            key, body = m.group(1).strip(), m.group(2)
            fields = {}
            for fm in re.finditer(r"^\s*([\w-]+)\s*=\s*\{(.*?)\},?\s*$", body, re.S | re.M):
                fields[fm.group(1).lower()] = re.sub(r"\s+", " ", fm.group(2)).strip()
            entries[key] = fields
    return entries

BIB = load_bib()
# archive typo: nime20201_installations_N -> nime2021_installations_N
def bib_key_for(folder):
    k = re.sub(r"^nime2020([12])_", r"nime202\1_", folder)
    return k if k in BIB else None

# ---- per item ------------------------------------------------------------
def parse_md_front(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}

def classify(url):
    ext = url.rsplit(".", 1)[-1].lower().split("?")[0] if "." in url.rsplit("/", 1)[-1] else ""
    if ext in IMG_EXT: return "image"
    if ext in VID_EXT: return "video"
    if ext in AUD_EXT: return "audio"
    return "other"

def scan_html(path):
    """Return remote asset URLs and embed URLs referenced by the export HTML."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return [], []
    text = html.unescape(text)
    assets = sorted(set(re.findall(r"https://assets\.pubpub\.org/[A-Za-z0-9_\-./%]+", text)))
    embeds = sorted(set(re.findall(
        r"https?://(?:www\.)?(?:youtube\.com/(?:embed/|watch\?v=)[\w\-]+|youtu\.be/[\w\-]+|vimeo\.com/[\w/?=&.]+|soundcloud\.com/[\w\-/]+|player\.vimeo\.com/video/\d+)",
        text)))
    return assets, embeds

items = []
for year_dir in sorted(ROOT.iterdir()):
    if not year_dir.is_dir() or not year_dir.name.isdigit():
        continue
    for cat_dir in sorted(year_dir.iterdir()):
        for coll_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
            for item in sorted(p for p in coll_dir.iterdir() if p.is_dir()):
                files = sorted(p for p in item.iterdir() if p.is_file() and not p.name.startswith("."))
                uuids = {f.stem for f in files if UUID_RE.match(f.stem)}
                uuid = next(iter(uuids), None)
                exports = {ext: any(f.name == f"{uuid}.{ext}" for f in files) for ext in EXPORT_EXTS}
                local_media = [{"name": f.name, "bytes": f.stat().st_size}
                               for f in files if f.suffix.lower().lstrip(".") in MEDIA_EXT]
                incomplete = [f.name for f in files if f.suffix == ".crdownload"]
                extra_pdfs = [f.name for f in files if f.suffix == ".pdf" and f.stem != uuid]
                stray = [f.name for f in files
                         if not (UUID_RE.match(f.stem) and f.suffix.lstrip(".") in EXPORT_EXTS)
                         and f.suffix.lower().lstrip(".") not in MEDIA_EXT
                         and f.suffix not in (".crdownload",)
                         and f.name != "integrated_web_contents_URL.txt"
                         and not (f.suffix == ".pdf")]
                url_list = []
                ul = item / "integrated_web_contents_URL.txt"
                if ul.exists():
                    url_list = [l.strip() for l in ul.read_text(errors="replace").splitlines() if l.strip()]
                front = parse_md_front(item / f"{uuid}.md") if uuid else {}
                assets, embeds = scan_html(item / f"{uuid}.html") if uuid else ([], [])
                by_type = {}
                for a in assets:
                    by_type.setdefault(classify(a), []).append(a)
                authors = front.get("author") or []
                if isinstance(authors, list):
                    authors = [a if isinstance(a, str) else a.get("name", str(a)) for a in authors]
                bk = bib_key_for(item.name)
                bib = BIB.get(bk, {}) if bk else {}
                n_local_vid = sum(1 for m in local_media if m["name"].rsplit(".",1)[-1].lower() in VID_EXT)
                n_local_aud = sum(1 for m in local_media if m["name"].rsplit(".",1)[-1].lower() in AUD_EXT)
                items.append({
                    "year": int(year_dir.name),
                    "category": cat_dir.name,
                    "collection": coll_dir.name,
                    "folder": item.name,
                    "path": str(item.relative_to(ROOT)),
                    "bib_key": bk,
                    "pubpub_uuid": uuid,
                    "pubpub_slug": (front.get("article") or {}).get("elocation-id"),
                    "title": re.sub(r"\s+", " ", str(front.get("title", ""))).strip() or bib.get("title"),
                    "authors": authors,
                    "doi": bib.get("doi"),
                    "track": bib.get("track"),
                    "presentation_video": bib.get("presentation-video"),
                    "date": front.get("date"),
                    "license": (front.get("copyright") or {}).get("type"),
                    "exports": exports,
                    "exports_missing": [e for e, ok in exports.items() if not ok],
                    "extra_pdfs": extra_pdfs,
                    "local_media": local_media,
                    "local_media_bytes": sum(m["bytes"] for m in local_media),
                    "incomplete_downloads": incomplete,
                    "stray_files": stray,
                    "url_list_file": url_list,
                    "remote_assets": by_type,
                    "remote_embeds": embeds,
                    "n_remote_images": len(by_type.get("image", [])),
                    "n_remote_videos": len(by_type.get("video", [])),
                    "n_remote_audio": len(by_type.get("audio", [])),
                    "n_remote_other": len(by_type.get("other", [])),
                    "n_local_videos": n_local_vid,
                    "n_local_audio": n_local_aud,
                    "n_embeds": len(embeds),
                })

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "manifest.json").write_text(json.dumps(items, indent=1, ensure_ascii=False, default=str))
cols = ["year","category","collection","folder","bib_key","pubpub_slug","doi","title","authors","track",
        "exports_missing","n_local_videos","n_local_audio","local_media_bytes",
        "n_remote_images","n_remote_videos","n_remote_audio","n_remote_other","n_embeds",
        "incomplete_downloads","extra_pdfs","stray_files","presentation_video"]
with open(OUT / "manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for it in items:
        row = dict(it)
        for k in ("authors","exports_missing","incomplete_downloads","extra_pdfs","stray_files"):
            row[k] = "; ".join(row[k])
        w.writerow(row)
print(f"{len(items)} items written to {OUT}")
