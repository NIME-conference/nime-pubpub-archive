#!/usr/bin/env python3
"""HEAD every remote asset URL referenced by the exports; record status + size.
Usage: python3 -I check_assets.py manifest.json assets.json"""
import json, sys, urllib.request, urllib.error, concurrent.futures as cf
items = json.load(open(sys.argv[1]))
urls = sorted({(a, it["path"]) for it in items for t in it["remote_assets"].values() for a in t})
def head(u):
    req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return {"status": r.status, "bytes": int(r.headers.get("Content-Length") or 0), "ctype": r.headers.get("Content-Type")}
    except urllib.error.HTTPError as e:
        return {"status": e.code}
    except Exception as e:
        return {"status": None, "error": str(e)}
res = {}
with cf.ThreadPoolExecutor(8) as ex:
    futs = {ex.submit(head, u): (u, p) for u, p in urls}
    for i, f in enumerate(cf.as_completed(futs)):
        u, p = futs[f]; r = f.result(); r["item"] = p; res[u] = r
        if i % 100 == 0: print(i, flush=True)
json.dump(res, open(sys.argv[2], "w"), indent=1)
ok = sum(1 for r in res.values() if r["status"] == 200)
print("done", ok, "ok of", len(res), "total bytes", sum(r.get("bytes", 0) for r in res.values()))
