#!/usr/bin/env python3
"""Run make_pdf.py over a list of bib keys. Usage: python3 -I run_batch.py ARCHIVE_ROOT OUT_DIR key [key...]
Writes OUT_DIR/<key>/ and OUT_DIR/batch_results.json (merged with earlier results)."""
import sys, json, pathlib, subprocess
ROOT, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); keys = sys.argv[3:]
here = pathlib.Path(__file__).resolve().parent
resfile = OUT / "batch_results.json"; results = json.load(open(resfile)) if resfile.exists() else {}
for k in keys:
    item = next(ROOT.glob(f"*/*/*/{k}"))
    r = subprocess.run([sys.executable, "-I", str(here / "make_pdf.py"), str(item), str(OUT / k)], capture_output=True, text=True)
    try: results[k] = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: results[k] = {"item": k, "crash": (r.stderr or r.stdout)[-800:]}
    results[k]["src"] = str(item)
    print(k, results[k].get("pages"), results[k].get("latex_errors") or results[k].get("crash", "")[:200], flush=True)
json.dump(results, open(resfile, "w"), indent=1)
