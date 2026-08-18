#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""manual_verify.py — 官方源被 Cloudflare 硬拦时的标准人工核验流程

背景: travel.state.gov 对非美国住宅 IP(含 GitHub Action/本机 VPN 出口) 一律 Cloudflare 拦截
("Attention Required"/"Just a moment"), 自动核验不可行。us_passport 的 2026-08-12 日期即人工核验产物。

用法:
  1) 生成核对清单:  python3 manual_verify.py list us_passport        (打印 facts 正则 + 官方 URL)
  2) 人工核验通过后刷新日期:  python3 manual_verify.py set us_passport 2026-08-18
     (更新 passport_photo_specs.json / .csv / spec_watch/state.json, 提交推送后部署 iMac)

交叉验证(辅助): www.state.gov 子域可自动访问(200), 可先自动抓取比对正文关键词,
再人工打开 travel.state.gov 确认版本一致后执行 set。
"""
import csv
import io
import json
import os
import re
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FP = os.path.join(APP_DIR, "passport_photo_specs.json")
CSV_FP = os.path.join(APP_DIR, "passport_photo_specs.csv")
STATE_FP = os.path.join(APP_DIR, "spec_watch", "state.json")
CSV_COLS = ["id", "country", "country_code", "document", "photo_size", "output_pixels",
            "file_size", "head_height_rule", "background", "notes", "official_source",
            "official_source_url", "verified_date"]

# 与 spec_fetch.py SOURCES 一致的 facts 正则(仅列出常见被拦源, 可扩展)
FACTS = {
    "us_passport": {"size_2x2": r"2\s*[x×]\s*2", "size_51mm": r"51\s*mm",
                    "head_25_35mm": r"25\s*(?:to|–|—|-)\s*35\s*mm", "bg_white": r"white",
                    "unaltered": r"do not change your photo", "age_6mo": r"6\s*months"},
    "us_visa": {"size_2x2": r"2\s*[x×]\s*2", "size_51mm": r"51\s*mm",
                "px_600": r"600", "bg_white": r"white", "no_glasses": r"no longer allowed"},
    "us_dv_lottery": {"px_600": r"600", "kb_240": r"240", "bg_white": r"white"},
}


def load(fp, default):
    try:
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(fp, obj):
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def cmd_list(key):
    ds = load(DATASET_FP, {"specs": []})
    spec = next((s for s in ds["specs"] if s["id"] == key), None)
    if not spec:
        print(f"未找到 {key}")
        return 1
    print(f"== 人工核验清单: {key} ==")
    print(f"官方 URL: {spec.get('official_source_url')}")
    print(f"当前核验日期: {spec.get('verified_date')}")
    print("确认以下 facts 在官方页出现(正则):")
    for name, pat in FACTS.get(key, {}).items():
        print(f"  {name:<14} {pat}")
    print("提示: 用真实浏览器打开官方 URL 人工比对; 若一致执行: python3 manual_verify.py set %s 今天" % key)


def cmd_set(key, date):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
        print("日期格式应为 YYYY-MM-DD")
        return 1
    ds = load(DATASET_FP, {"specs": []})
    for s in ds["specs"]:
        if s["id"] == key:
            s["verified_date"] = date
            break
    else:
        print(f"未找到 {key}")
        return 1
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s.get("verified_date", "")) for s in ds["specs"]):
        ds["last_verified"] = date
    save(DATASET_FP, ds)
    with open(CSV_FP, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(CSV_COLS)
        for s in ds["specs"]:
            w.writerow([s.get(c) or "" for c in CSV_COLS])
    st = load(STATE_FP, {})
    st[key] = {**(st.get(key) or {}), "last_status": "MANUAL",
               "last_checked": date, "last_note": "人工核验(官方页 Cloudflare 拦截, 浏览器人工比对 facts 后手动刷新)",
               "consecutive_failures": 0}
    save(STATE_FP, st)
    print(f"{key} 核验日期 -> {date} (JSON/CSV/state 已更新)")
    print("后续: git add/commit/push; 同步 iMac ~/cutout_demo/spec_dataset/; 无需重启 web(渲染时读数据)")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "list" and len(a) == 2:
        sys.exit(cmd_list(a[1]))
    if a and a[0] == "set" and len(a) == 3:
        sys.exit(cmd_set(a[1], a[2]))
    print(__doc__)
    sys.exit(1)
