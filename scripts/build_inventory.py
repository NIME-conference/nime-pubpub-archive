#!/usr/bin/env python3
"""Merge manifest + crossref + assets + embeds + fetch report into inventory.json / inventory.csv and print a summary."""
import json, csv, collections, re, pathlib
items=json.load(open("manifest.json")); cr=json.load(open("crossref.json")); assets=json.load(open("assets.json"))
embeds=json.load(open("embeds.json")); slugs=json.load(open("slugs.json")); fetched={u:s for u,s,_ in json.load(open("fetch_report.json"))}
ROOT=pathlib.Path("/Volumes/charles2025/nime-pubpub-backup/extracted/NIME_PubPub_Backup")
wb=set(re.search(r"/pub/([a-z0-9-]+)",l.split()[0]).group(1) for l in open("wayback_cdx.txt") if "/pub/" in l.split()[0])
MEDIA=("mp4","webm","m4v","mov","wav","mp3","m4a")
by_item=collections.defaultdict(list)
for u,r in assets.items(): by_item[r["item"]].append((u,r))
def embed_status(u):
    for nu,r in embeds.items():
        if u in r["raw"]: return r["status"]
    return "?"
inv=[]
for i in items:
    c=cr.get(i["path"],{}); slug=slugs[i["path"]]
    loc={m["bytes"] for m in i["local_media"]}
    rem_media=[(u,r.get("bytes")) for u,r in by_item[i["path"]] if u.rsplit(".",1)[-1].lower() in MEDIA]
    verified=sum(1 for u,b in rem_media if b in loc)
    unverified=[u for u,b in rem_media if b is None]
    missing=[u for u,b in rem_media if b is not None and b not in loc]
    fetched_missing=[u for u in missing if fetched.get(u) in ("ok","skip")]
    n_assets=len(by_item[i["path"]]); n_fetched=sum(1 for u,_ in by_item[i["path"]] if fetched.get(u) in ("ok","skip","ok-svg"))
    ext=[(u,embed_status(u)) for u in i["remote_embeds"]+i["url_list_file"]]
    pv=i["presentation_video"]; pv_status=embed_status(pv) if pv else ""
    inv.append({**{k:i[k] for k in ("year","category","collection","folder","path","bib_key","pubpub_uuid","title","authors","track")},
        "pubpub_slug":slug, "pubpub_url":f"https://nime.pubpub.org/pub/{slug}", "doi":i["doi"] or (c.get("doi") if c.get("found") else None),
        "doi_registered":bool(c.get("found")), "crossref_title":c.get("title"),
        "has_pubpub_pdf":"pdf" not in i["exports_missing"], "author_pdf":i["extra_pdfs"], "exports_missing":i["exports_missing"],
        "local_media":[m["name"] for m in i["local_media"]], "local_media_bytes":i["local_media_bytes"],
        "remote_media_total":len(rem_media), "remote_media_verified_local":verified, "remote_media_unverified":unverified,
        "remote_media_was_missing":missing, "remote_media_fetched":fetched_missing,
        "incomplete_downloads":i["incomplete_downloads"],
        "remote_assets_total":n_assets, "remote_assets_fetched":n_fetched, "n_remote_images":i["n_remote_images"],
        "external_links":ext, "external_dead":[u for u,s in ext if s not in ("live","unchecked")],
        "presentation_video":pv, "presentation_video_status":pv_status,
        "wayback_capture":slug in wb})
json.dump(inv, open("inventory.json","w"), indent=1, ensure_ascii=False)
cols=["year","collection","folder","bib_key","pubpub_slug","doi","doi_registered","title","authors","has_pubpub_pdf","author_pdf",
      "local_media","remote_media_total","remote_media_verified_local","remote_media_was_missing","remote_media_fetched","remote_media_unverified",
      "incomplete_downloads","n_remote_images","remote_assets_total","remote_assets_fetched","external_links","external_dead","presentation_video","presentation_video_status","wayback_capture","pubpub_url"]
with open("inventory.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore"); w.writeheader()
    for r in inv:
        row=dict(r)
        for k in ("authors","author_pdf","local_media","remote_media_was_missing","remote_media_fetched","remote_media_unverified","incomplete_downloads","external_dead"): row[k]="; ".join(row[k])
        row["external_links"]="; ".join(f"{u} [{s}]" for u,s in r["external_links"])
        w.writerow(row)
# summary
S=lambda f: sum(1 for r in inv if f(r))
print("items", len(inv))
print("DOI registered at Crossref:", S(lambda r:r["doi_registered"]), " not:", [r["path"] for r in inv if not r["doi_registered"]])
print("remote media total:", sum(r["remote_media_total"] for r in inv), " verified byte-identical locally:", sum(r["remote_media_verified_local"] for r in inv),
      " were missing (now fetched):", sum(len(r["remote_media_was_missing"]) for r in inv), "/", sum(len(r["remote_media_fetched"]) for r in inv),
      " unverified (size unknown):", sum(len(r["remote_media_unverified"]) for r in inv))
print("remote assets total:", sum(r["remote_assets_total"] for r in inv), " fetched:", sum(r["remote_assets_fetched"] for r in inv))
print("items with external links:", S(lambda r:r["external_links"]), " items with a dead external link:", S(lambda r:r["external_dead"]), " dead links:", sum(len(r["external_dead"]) for r in inv))
print("presentation videos (bib):", S(lambda r:r["presentation_video"]), " dead:", [(r["bib_key"],r["presentation_video"],r["presentation_video_status"]) for r in inv if r["presentation_video"] and r["presentation_video_status"] not in ("live","")])
print("wayback capture exists:", S(lambda r:r["wayback_capture"]))
print("items with incomplete .crdownload:", [(r["folder"], r["remote_media_fetched"]) for r in inv if r["incomplete_downloads"]])
