#!/usr/bin/env python3
"""Download every remote assets.pubpub.org file referenced by an item's export HTML into
<item>/pubpub_assets/<bucket>/<filename>, skipping media that already exists locally with the same size.
Resumable: existing files with the expected size are skipped. Writes fetch_report.json.
Usage: python3 -I fetch_assets.py ARCHIVE_ROOT manifest.json assets.json"""
import json, sys, pathlib, urllib.request, urllib.error, concurrent.futures as cf, time
ROOT = pathlib.Path(sys.argv[1]); items = json.load(open(sys.argv[2])); assets = json.load(open(sys.argv[3]))
MEDIA = ("mp4","webm","m4v","mov","wav","mp3","m4a")
local_sizes = {i["path"]: {m["bytes"] for m in i["local_media"]} for i in items}
jobs = []
for u, r in assets.items():
    item = r["item"]; size = r.get("bytes")
    ext = u.rsplit(".",1)[-1].lower()
    if ext in MEDIA and (size is None or size in local_sizes.get(item, set())):
        continue  # already have an identical local copy (or size unknown: handled manually)
    dest = ROOT / item / "pubpub_assets" / u.split("assets.pubpub.org/",1)[1]
    jobs.append((u, dest, size))
def fetch(job):
    u, dest, size = job
    if dest.exists() and size and dest.stat().st_size == size:
        return (u, "skip", size)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(4):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk: break
                    f.write(chunk)
            got = tmp.stat().st_size
            if size and got != size:
                raise IOError(f"size mismatch {got} != {size}")
            tmp.rename(dest)
            return (u, "ok", got)
        except Exception as e:
            err = str(e); time.sleep(5 * (attempt + 1))
    return (u, "fail", err)
print(len(jobs), "files to fetch,", round(sum(s or 0 for *_, s in jobs)/1e9, 2), "GB", flush=True)
report = []
with cf.ThreadPoolExecutor(6) as ex:
    for n, res in enumerate(ex.map(fetch, jobs)):
        report.append(res)
        if n % 100 == 0: print(n, flush=True)
json.dump(report, open("fetch_report.json", "w"), indent=1)
import collections
print("done", collections.Counter(r[1] for r in report), flush=True)
for r in report:
    if r[1] == "fail": print("FAIL", r)
