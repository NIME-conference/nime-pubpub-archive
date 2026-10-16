#!/usr/bin/env python3
"""For every item, derive the PubPub DOI (10.21428/92fbeb44.<first 8 hex of pub uuid>) and query Crossref.
Usage: python3 -I crossref_lookup.py manifest.json crossref.json"""
import json, sys, time, urllib.request, urllib.error
items = json.load(open(sys.argv[1]))
out = {}
for n, it in enumerate(items):
    u = it["pubpub_uuid"]
    if not u: continue
    doi = f"10.21428/92fbeb44.{u[:8]}"
    req = urllib.request.Request(f"https://api.crossref.org/works/{doi}", headers={"User-Agent": "nime-archive-check (mailto:charles.martin@anu.edu.au)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            m = json.load(r)["message"]
        out[it["path"]] = {"doi": doi, "found": True, "title": (m.get("title") or [None])[0],
            "url": (m.get("resource") or {}).get("primary", {}).get("URL"), "type": m.get("type"),
            "container": (m.get("container-title") or [None])[0], "issued": m.get("issued", {}).get("date-parts"),
            "author": [f'{a.get("given","")} {a.get("family","")}'.strip() for a in m.get("author", [])]}
    except urllib.error.HTTPError as e:
        out[it["path"]] = {"doi": doi, "found": False, "status": e.code}
    except Exception as e:
        out[it["path"]] = {"doi": doi, "found": False, "error": str(e)}
    if n % 25 == 0: print(n, flush=True)
    time.sleep(0.2)
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print("done", sum(1 for v in out.values() if v["found"]), "found of", len(out))
