#!/usr/bin/env python3
"""Make web-optimised images and video poster frames for the static site.
Usage: python3 -I optimise_media.py ARCHIVE_ROOT manifest.json assets.json OUT_DIR
Writes OUT_DIR/<bucket>/<name>.<ext> (max 1600px, photos as JPEG q82) and OUT_DIR/posters/<bucket>/<name>.jpg,
plus OUT_DIR/media_map.json {original_url: {"web": relpath, "bytes": n}}."""
import json, sys, pathlib, subprocess, concurrent.futures as cf
ROOT, MAN, ASSETS, OUT = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
items = json.load(open(MAN)); assets = json.load(open(ASSETS))
IMG = {"png","jpg","jpeg","gif","webp","tif","tiff"}; VID = {"mp4","webm","m4v","mov"}
local_by_item_size = {}
for i in items:
    for m in i["local_media"]:
        local_by_item_size[(i["path"], m["bytes"])] = ROOT / i["path"] / m["name"]
def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)
def do_image(u, r):
    rel = u.split("assets.pubpub.org/", 1)[1]; src = ROOT / r["item"] / "pubpub_assets" / rel
    ext = rel.rsplit(".", 1)[-1].lower()
    if not src.exists(): return u, {"error": "missing local"}
    if ext == "svg":
        dst = OUT / rel; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(src.read_bytes())
        return u, {"web": rel, "bytes": dst.stat().st_size}
    if ext == "gif":
        dst = OUT / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        run(["magick", str(src), "-coalesce", "-resize", "1200x1200>", "-layers", "Optimize", str(dst)])
        if not dst.exists() or dst.stat().st_size > src.stat().st_size: dst.write_bytes(src.read_bytes())
        return u, {"web": rel, "bytes": dst.stat().st_size}
    base = rel.rsplit(".", 1)[0]
    has_alpha = ext == "png" and "True" in run(["magick", "identify", "-format", "%[opaque]", str(src)]).stdout.replace("True","X").replace("False","True").replace("X","False")  # opaque False => alpha
    cands = []
    if ext == "png":
        p = OUT / f"{base}.png"; p.parent.mkdir(parents=True, exist_ok=True)
        run(["magick", str(src), "-resize", "1600x1600>", "-strip", "-define", "png:compression-level=9", str(p)]); cands.append(p)
    if not has_alpha:
        j = OUT / f"{base}.jpg"; j.parent.mkdir(parents=True, exist_ok=True)
        run(["magick", str(src), "-resize", "1600x1600>", "-strip", "-background", "white", "-flatten", "-quality", "82", str(j)]); cands.append(j)
    cands = [c for c in cands if c.exists() and c.stat().st_size > 0]
    if not cands: return u, {"error": "convert failed"}
    best = min(cands, key=lambda c: c.stat().st_size)
    for c in cands:
        if c != best: c.unlink()
    return u, {"web": str(best.relative_to(OUT)), "bytes": best.stat().st_size}
def do_video(u, r):
    rel = u.split("assets.pubpub.org/", 1)[1]; base = rel.rsplit(".", 1)[0]
    src = local_by_item_size.get((r["item"], r.get("bytes"))) or (ROOT / r["item"] / "pubpub_assets" / rel)
    if not src.exists():
        # fall back: any local video in the item folder with same size unknown -> first videoN
        return u, {"error": "no local video"}
    dst = OUT / "posters" / f"{base}.jpg"; dst.parent.mkdir(parents=True, exist_ok=True)
    for t in ("3", "0.5"):
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", t, "-i", str(src), "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", "-q:v", "4", str(dst)])
        if dst.exists() and dst.stat().st_size > 0: break
    dur = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)]).stdout.strip()
    return u, {"poster": str(dst.relative_to(OUT)) if dst.exists() else None, "bytes": dst.stat().st_size if dst.exists() else 0, "duration": dur, "source_file": str(src.relative_to(ROOT))}
jobs = []
for u, r in assets.items():
    ext = u.rsplit(".", 1)[-1].lower()
    if ext in IMG or ext == "svg": jobs.append(("img", u, r))
    elif ext in VID: jobs.append(("vid", u, r))
print(len(jobs), "jobs", flush=True)
out = {}
with cf.ThreadPoolExecutor(6) as ex:
    futs = [ex.submit(do_image if k == "img" else do_video, u, r) for k, u, r in jobs]
    for n, f in enumerate(cf.as_completed(futs)):
        u, res = f.result(); out[u] = res
        if n % 100 == 0: print(n, flush=True)
json.dump(out, open(OUT / "media_map.json", "w"), indent=1)
tot = sum(v.get("bytes", 0) for v in out.values()); errs = [u for u, v in out.items() if "error" in v]
print("done; total MB", round(tot / 1e6), "errors", len(errs), errs[:10], flush=True)
