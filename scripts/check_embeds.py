#!/usr/bin/env python3
"""Check liveness of external embeds (YouTube/Vimeo/SoundCloud) and bib presentation videos via oEmbed.
Usage: python3 -I check_embeds.py manifest.json embeds.json"""
import json, sys, re, urllib.request, urllib.error, urllib.parse, concurrent.futures as cf
items = json.load(open(sys.argv[1]))
def norm(u):
    m = re.search(r"(?:youtu\.be/|youtube\.com/(?:embed/|watch\?v=))([\w\-]{11})", u)
    if m: return "youtube", f"https://www.youtube.com/watch?v={m.group(1)}"
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", u)
    if m: return "vimeo", f"https://vimeo.com/{m.group(1)}"
    if "soundcloud.com" in u: return "soundcloud", u.split("?")[0]
    return "other", u
targets = {}
for i in items:
    for u in i["remote_embeds"] + i["url_list_file"] + ([i["presentation_video"]] if i["presentation_video"] else []):
        kind, nu = norm(u)
        targets.setdefault(nu, {"kind": kind, "items": set(), "raw": set()})
        targets[nu]["items"].add(i["path"]); targets[nu]["raw"].add(u)
OEMBED = {"youtube": "https://www.youtube.com/oembed?format=json&url=", "vimeo": "https://vimeo.com/api/oembed.json?url=", "soundcloud": "https://soundcloud.com/oembed?format=json&url="}
def check(nu):
    kind = targets[nu]["kind"]
    if kind not in OEMBED: return nu, {"status": "unchecked"}
    req = urllib.request.Request(OEMBED[kind] + urllib.parse.quote(nu, safe=""), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r); return nu, {"status": "live", "title": d.get("title"), "author": d.get("author_name")}
    except urllib.error.HTTPError as e:
        return nu, {"status": f"http {e.code}"}
    except Exception as e:
        return nu, {"status": "error", "error": str(e)}
out = {}
with cf.ThreadPoolExecutor(6) as ex:
    for nu, r in ex.map(check, list(targets)):
        r.update({"kind": targets[nu]["kind"], "items": sorted(targets[nu]["items"]), "raw": sorted(targets[nu]["raw"])}); out[nu] = r
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
import collections
print("done", len(out), "urls;", collections.Counter((r["kind"], r["status"]) for r in out.values()))
