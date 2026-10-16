#!/usr/bin/env python3
"""Re-check assets that refused HEAD using a 1-byte ranged GET; update assets.json in place."""
import json, sys, re, urllib.request, urllib.error, concurrent.futures as cf
a = json.load(open(sys.argv[1]))
todo = [u for u, r in a.items() if r["status"] != 200]
def rget(u):
    req = urllib.request.Request(u, headers={"Range": "bytes=0-0", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            cr = r.headers.get("Content-Range", "")
            m = re.search(r"/(\d+)$", cr)
            return {"status": 200, "bytes": int(m.group(1)) if m else None, "ctype": r.headers.get("Content-Type"), "via": "range-get"}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "via": "range-get"}
    except Exception as e:
        return {"status": None, "error": str(e), "via": "range-get"}
with cf.ThreadPoolExecutor(8) as ex:
    for u, r in zip(todo, ex.map(rget, todo)):
        r["item"] = a[u]["item"]; a[u] = r
json.dump(a, open(sys.argv[1], "w"), indent=1)
import collections
print("statuses:", collections.Counter(r["status"] for r in a.values()), "total GB", round(sum(r.get("bytes") or 0 for r in a.values())/1e9, 2))
