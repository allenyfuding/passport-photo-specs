#!/usr/bin/env python3
"""V421: audit automatic-source coverage and stale verified dates.

Writes spec_watch/STALE_AUDIT.md. Does not change any spec.
Run:
    python3 spec_stale_audit.py
"""
import json
import os
from datetime import date

from spec_fetch import SOURCES

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FP = os.path.join(APP_DIR, "passport_photo_specs.json")
STATE_FP = os.path.join(APP_DIR, "spec_watch", "state.json")
OUT_FP = os.path.join(APP_DIR, "spec_watch", "STALE_AUDIT.md")
STALE_DAYS = int(os.environ.get("SPEC_STALE_DAYS", "60"))


def main():
    with open(DATASET_FP, encoding="utf-8") as f:
        specs = json.load(f).get("specs", [])
    state = {}
    if os.path.exists(STATE_FP):
        with open(STATE_FP, encoding="utf-8") as f:
            state = json.load(f)
    source_keys = {s["key"] for s in SOURCES}
    today = date.today()
    rows = []
    for s in specs:
        d = s.get("verified_date") or ""
        try:
            age = (today - date.fromisoformat(d)).days if d else None
        except ValueError:
            age = None
        rows.append({
            "id": s.get("id", ""),
            "document": s.get("document", ""),
            "date": d or "—",
            "age": age,
            "auto": s.get("id") in source_keys,
            "status": (state.get(s.get("id")) or {}).get("last_status", ""),
        })

    stale = [r for r in rows if r["age"] is None or r["age"] > STALE_DAYS]
    unsourced = [r for r in rows if not r["auto"]]
    failing = [r for r in rows if r["auto"] and r["status"] and r["status"] != "OK"]
    lines = [
        "# Spec source / staleness audit",
        "",
        f"Generated: {today.isoformat()}",
        f"Automatic sources: {len(source_keys)}",
        f"Specs: {len(rows)}",
        f"Stale threshold: {STALE_DAYS} days",
        "",
        f"## Stale ({len(stale)})",
        "",
        "| id | document | verified_date | age_days | auto_source | source_status |",
        "|---|---|---|---:|---|---|",
    ]
    for r in sorted(stale, key=lambda x: (x["date"], x["id"])):
        lines.append(f"| {r['id']} | {r['document']} | {r['date']} | "
                     f"{r['age'] if r['age'] is not None else '?'} | "
                     f"{'yes' if r['auto'] else 'NO'} | {r['status'] or '-'} |")
    lines += [
        "",
        f"## Unsourced ({len(unsourced)})",
        "",
        "These specs cannot advance their verified_date until a source is registered "
        "or a manual verification is recorded.",
        "",
    ]
    lines += [f"- `{r['id']}` — {r['document']} — {r['date']}" for r in sorted(unsourced, key=lambda x: x["id"])]
    lines += [
        "",
        f"## Automatic sources not OK ({len(failing)})",
        "",
    ]
    lines += [f"- `{r['id']}` — {r['status']} — {r['date']}" for r in sorted(failing, key=lambda x: x["id"])] or ["- none"]
    lines += [
        "",
        "## Policy",
        "",
        "- No automatic source = no date advancement.",
        "- Stale dates are shown as `re-check pending` on the site.",
        "- Do not bump a date without an official-source check or a recorded manual verification.",
    ]
    with open(OUT_FP, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {OUT_FP}")


if __name__ == "__main__":
    main()
