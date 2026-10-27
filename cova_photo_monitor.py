#!/usr/bin/env python3
"""Monitor the official COVA China-visa photo requirement images.

The COVA requirements are published as two PNG images, not as a text page.
This monitor hashes those images:
- unchanged -> refresh cn_visa_online.verified_date to today
- changed   -> keep the old date and append a manual-review entry to DRIFT.md

It is intentionally conservative: it never changes the spec values.
"""
import csv
import hashlib
import json
import os
import sys
import urllib.request
from datetime import date

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FP = os.path.join(APP_DIR, "passport_photo_specs.json")
CSV_FP = os.path.join(APP_DIR, "passport_photo_specs.csv")
STATE_FP = os.path.join(APP_DIR, "spec_watch", "cova_photos.json")
DRIFT_FP = os.path.join(APP_DIR, "spec_watch", "DRIFT.md")
URLS = {
    "zpyq1": "https://consular.mfa.gov.cn/VISA/img/zpyq1_zh_CN.f7c96ced.png",
    "zpyq2": "https://consular.mfa.gov.cn/VISA/img/zpyq2_zh_CN.53de805e.png",
}
COLS = ["id", "country", "country_code", "document", "photo_size", "output_pixels",
        "file_size", "head_height_rule", "background", "notes", "official_source",
        "official_source_url", "verified_date"]


def load(fp, default):
    try:
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(fp, obj):
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, fp)


def fetch_hash(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
        "Accept": "image/png,image/*;q=0.9,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read()
    if not raw.startswith(b"\x89PNG"):
        raise RuntimeError("not a PNG")
    return hashlib.sha256(raw).hexdigest()[:32]


def write_csv(ds):
    with open(CSV_FP, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(COLS)
        for s in ds.get("specs", []):
            w.writerow([s.get(c) or "" for c in COLS])


def main():
    hashes = {}
    try:
        for name, url in URLS.items():
            hashes[name] = fetch_hash(url)
    except Exception as e:
        print(f"COVA image fetch failed: {e}")
        return 0

    state = load(STATE_FP, {})
    old = {k: state.get("hashes", {}).get(k, "") for k in URLS}
    changed = [k for k in URLS if old.get(k) and old.get(k) != hashes[k]]

    if changed:
        with open(DRIFT_FP, "a", encoding="utf-8") as f:
            f.write(f"\n## {date.today().isoformat()} — COVA 图片变更\n")
            for k in changed:
                f.write(f"- COVA `{k}` image hash {old.get(k)} → {hashes[k]}; "
                        "need human review before changing cn_visa_online specs/date.\n")
        print("COVA images changed; manual review required: " + ", ".join(changed))
        state["hashes"] = hashes
        state["last_checked"] = date.today().isoformat()
        state["last_change"] = date.today().isoformat()
        save(STATE_FP, state)
        return 0

    ds = load(DATASET_FP, {"specs": []})
    spec = next((s for s in ds.get("specs", []) if s.get("id") == "cn_visa_online"), None)
    if spec:
        spec["verified_date"] = date.today().isoformat()
        spec["official_page_verified"] = True
        save(DATASET_FP, ds)
        write_csv(ds)
        print("COVA images unchanged; refreshed cn_visa_online -> " + spec["verified_date"])
    else:
        print("cn_visa_online not found in dataset")

    state["hashes"] = hashes
    state["last_checked"] = date.today().isoformat()
    save(STATE_FP, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
