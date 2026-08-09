#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_fetch.py — GitHub Action: 定期抓取官方证件照规格页, 自动刷新 spec_dataset 核验日期

机制 (与 web_app 侧 spec_watch.py 同源逻辑, 输出改写到数据集仓库):
  1. 每天抓取各官方源(美/英/加/印度/新加坡/沙特/新西兰) 的证件照规格页;
  2. 抽取"关键事实"(尺寸/头部比例/背景等正则) 做 sha256 比对, 措辞变化不误报;
  3. 事实稳定(OK/COSMETIC) → 该 spec 的 verified_date 更新为当天, last_verified 同步;
  4. 事实变更(CHANGED) → **绝不修改规格数值**(红线: 程序化页面必须真实规格数据),
     保留原核验日期, 追加到 spec_watch/DRIFT.md, workflow 开 issue 人工复核后手动更新;
  5. 页面被移除(404/410) / 结构异常(ANOMALY) / 不可达(超时/403/5xx) → 保留原核验日期,
     连续失败满 FAIL_ALERT 次在报告与 issue 中告警;
  6. 从 JSON 重新生成 CSV(与 JSON 保持同源), 提交即完成一次数据刷新。

产物(仓库内 spec_watch/):
  state.json   每源状态(事实hash/页面hash/核验日期/连续失败) —— 已提交, 跨运行持久化
  REPORT.md    最近一次运行摘要
  DRIFT.md     需人工复核的变更/异常(追加日志; workflow 检测其 git diff 决定是否开 issue)

用法: python3 spec_fetch.py   (workflow: 每日 cron + workflow_dispatch)
env:
  SPEC_FETCH_OVERRIDES  JSON 覆盖源配置, 如 {"uk_passport":{"url":"http://127.0.0.1:8890/a.html"}}
  SPEC_FETCH_FAIL_ALERT 连续失败告警阈值(默认 3)
"""
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import time
import zlib
import urllib.error
import urllib.request
from datetime import date

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FP = os.path.join(APP_DIR, "passport_photo_specs.json")
CSV_FP = os.path.join(APP_DIR, "passport_photo_specs.csv")
OUT_DIR = os.path.join(APP_DIR, "spec_watch")
STATE_FP = os.path.join(OUT_DIR, "state.json")
REPORT_FP = os.path.join(OUT_DIR, "REPORT.md")
DRIFT_FP = os.path.join(OUT_DIR, "DRIFT.md")
FAIL_ALERT = int(os.environ.get("SPEC_FETCH_FAIL_ALERT", "3"))
PROXY = os.environ.get("SPEC_FETCH_PROXY") or None
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 25
CSV_COLS = ["id", "country", "country_code", "document", "photo_size", "output_pixels",
            "file_size", "head_height_rule", "background", "notes", "official_source",
            "official_source_url", "verified_date"]

# 各官方源: key(对应 JSON spec id) / 展示名 / 官方 URL 列表 / 关键事实正则。
# 事实键值变更(正则失配)即判为 CHANGED, 需人工复核后再改 spec 数值。
SOURCES = [
    {"key": "us_passport", "label": "US Passport",
     "urls": ["https://travel.state.gov/en/passports/apply/help/photos.html",
              "https://travel.state.gov/en/passports/renew-replace/online/upload-digital-photo.html"],
     "facts": {"size_2x2": r"2\s*[x×]\s*2", "size_51mm": r"51\s*mm",
               "head_25_35mm": r"25\s*(?:to|–|—|\-)\s*35\s*mm", "bg_white": r"white",
               "px_dims": r"\d{3,4}\s*[x×]\s*\d{3,4}", "head_word": r"head",
               "dig_54kb": r"54\s*kb", "dig_10mb": r"10\s*mb"}},
    {"key": "us_visa", "label": "US Visa (DS-160)",
     "urls": ["https://travel.state.gov/en/passports/apply/help/photos.html",
              "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos.html",
              "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos/digital-image-requirements.html"],
     "facts": {"size_2x2": r"2\s*[x×]\s*2", "size_51mm": r"51\s*mm",
               "px_600": r"600", "px_1200": r"1200", "bg_white": r"white", "age_6mo": r"6\s*months",
               "head_word": r"head", "no_glasses": r"no longer allowed"}},
    {"key": "uk_passport", "label": "UK Passport",
     "urls": ["https://www.gov.uk/photos-for-passports",
              "https://www.gov.uk/photos-for-passports/print"],
     "facts": {"px_600": r"600", "px_750": r"750",
               "file_50kb_10mb": r"50\s*kb[^.]{0,40}10\s*mb",
               "bg_plain_light": r"plain\s*light[- ]colou?red",
               "unaltered": r"unaltered", "age_1mo": r"last\s*month",
               "head_29_34mm": r"29\s*mm[^.]{0,30}34\s*mm",
               "print_45x35mm": r"45\s*(?:mm|millimetres?)[^.]{0,60}35\s*mm"}},
    {"key": "uk_visa", "label": "UK Visa",
     "url": "https://www.gov.uk/guidance/how-to-take-a-photo-for-a-visa-application-or-permission",
     "facts": {"px_600": r"600", "px_750": r"750", "max_6mb": r"6\s*mb",
               "bg_light": r"plain\s*light|light[- ]colou?red", "unaltered": r"unaltered"}},
    {"key": "ca_passport", "label": "Canada Passport",
     "url": "https://www.canada.ca/en/immigration-refugees-citizenship/services/canadian-passports/photos.html",
     "facts": {"px_1200": r"1200", "px_1800": r"1800", "px_3000": r"3000", "px_4500": r"4500",
               "head_pct_45_50": r"45\s*%\s*(?:and|to|–|—|\-)\s*50\s*%",
               "bg_white": r"white", "no_alter": r"alter"}},
    {"key": "ca_visa", "label": "Canada Visa (IRCC)",
     "urls": ["https://www.canada.ca/en/immigration-refugees-citizenship/services/application/application-forms-guides/guide-5256-applying-visa-immigration-canada.html",
              "https://www.canada.ca/en/immigration-refugees-citizenship/corporate/publications-manuals/operational-bulletins-manuals/service-delivery/photo-specifications.html"],
     "facts": {"size_35x45mm": r"35\s*mm[^.]{0,20}45\s*mm",
               "head_31_36mm": r"31\s*(?:to|–|—|\-)\s*36\s*mm",
               "head_pct_69_80": r"69\s*(?:to|–|—|\-)\s*80\s*(?:%|percent)", "bg_white": r"white"}},
    {"key": "in_evisa", "label": "India e-Visa",
     "url": "https://indianvisaonline.gov.in/evisa/tvoa.html",
     "facts": {"jpeg": r"Format - JPEG", "min_10kb": r"Minimum 10 KB", "max_1mb": r"Maximum 1 MB",
               "square": r"The height and width of the Photo must be equal",
               "no_spectacles": r"without spectacles", "head_full": r"full head from top of hair to bottom of chin",
               "bg_plain_light": r"plain light colored or white background",
               "no_shadows": r"No shadows on the face or on the background", "no_borders": r"Without borders"}},
    {"key": "sg_passport", "label": "Singapore Passport (ICA)",
     "url": "https://www.ica.gov.sg/photo-guidelines",
     "facts": {"px_400x514": r"400\s*[x×]\s*514\s*pixels",
               "formats": r"jpg,?\s*jpeg",
               "max_8mb": r"8\s*mb", "matte": r"matte or semi matte",
               "iso_icao": r"international standards organisation"}},
    {"key": "sa_evisa", "label": "Saudi Arabia e-Visa",
     "url": "https://visa.visitsaudi.com/Home/PhotoSpecifications",
     "facts": {"size_200": r"200\s*[x×]\s*200", "kb_5_100": r"5 to 100\s*kb",
               "face_70_80": r"70%\s*-\s*80%", "age_6mo": r"six months",
               "bg_white": r"background should be white", "no_shadows": r"no shadows"}},
    {"key": "nz_visa_online", "label": "New Zealand Visa / NZeTA",
     "url": "https://www.immigration.govt.nz/new-zealand-visas/apply-for-a-visa/tools-and-information/acceptable-photos",
     "facts": {"age_6mo": r"within the last 6 months",
               "kb_512_3_14mb": r"512\s*kb and 3\.14\s*mb",
               "portrait_3_4": r"portrait mode with 3:4 aspect ratio",
               "jpg_jpeg": r"jpg or jpeg",
               "no_shadows": r"no shadows on your face",
               "good_contrast": r"good contrast between your face and the background"}},
]


def load_json(fp, default):
    try:
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(fp, obj):
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, fp)


def sha(s):
    return hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest()[:24]


def normalize_text(raw):
    raw = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def extract_facts(text, facts):
    """返回 (matched_keys, {key: 首个匹配原文}) — 用事实键做比对, 措辞变化不误报。"""
    low = text.lower()
    matched, samples = [], {}
    for key, p in facts.items():
        m = re.search(p, low)
        if m:
            matched.append(key)
            samples[key] = m.group(0).strip()[:60]
    return sorted(matched), samples


def fetch(url):
    """返回 (http_code, normalized_text); 网络层失败抛 urllib 异常。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    })
    opener = urllib.request.build_opener()
    if PROXY:
        opener.add_handler(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    last = None
    for attempt in (0, 1):
        try:
            with opener.open(req, timeout=TIMEOUT) as r:
                raw = r.read()
                ce = (r.headers.get("Content-Encoding") or "").lower()
                if "gzip" in ce:
                    raw = gzip.decompress(raw)
                elif "deflate" in ce:
                    try:
                        raw = zlib.decompress(raw)
                    except Exception:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                enc = (r.headers.get_content_charset() or "utf-8")
                try:
                    html = raw.decode(enc, "ignore")
                except Exception:
                    html = raw.decode("utf-8", "ignore")
                return r.status, normalize_text(html)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return e.code, ""
            last = e
            time.sleep(2)
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def write_csv(ds):
    with open(CSV_FP, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")  # 保持仓库现有 CRLF
        w.writerow(CSV_COLS)
        for s in ds.get("specs", []):
            w.writerow([s.get(c) or "" for c in CSV_COLS])


def run():
    os.makedirs(OUT_DIR, exist_ok=True)
    state = load_json(STATE_FP, {})
    ds = load_json(DATASET_FP, {"specs": []})
    specs = {s["id"]: s for s in ds.get("specs", [])}
    try:
        overrides = json.loads(os.environ.get("SPEC_FETCH_OVERRIDES") or "{}")
    except Exception:
        overrides = {}

    today = date.today().isoformat()
    lines, drift = [], []
    all_ok = True
    updated = []

    for src in SOURCES:
        key = src["key"]
        spec = specs.get(key)
        if spec is None:
            lines.append(f"SKIP      {key} — 数据集无此 id")
            continue
        ov = overrides.get(key, {})
        urls = ov.get("urls") or ov.get("url") or src.get("urls") or [src["url"]]
        if isinstance(urls, str):
            urls = [urls]
        facts_re = ov.get("facts", src["facts"])
        st = state.get(key, {"consecutive_failures": 0})
        facts_hash = st.get("facts_hash", "")
        page_hash = st.get("page_hash", "")
        old_date = spec.get("verified_date") or ""

        texts, code_notes = [], []
        removed = False
        try:
            for u in urls:
                code, text = fetch(u)
                code_notes.append(f"HTTP {code}")
                if code in (404, 410):
                    removed = True
                    text = ""
                texts.append(text)
            code = 200
            text = "\n---PAGE---\n".join(texts)
            reason = "; ".join(code_notes)
        except urllib.error.HTTPError as e:
            code = e.code
            text = ""
            reason = f"HTTP {e.code}"
        except Exception as e:
            code = 0
            text = ""
            reason = f"{type(e).__name__}: {e}"
        if removed:
            code = 404

        if code in (404, 410):
            status = "REMOVED"
            note = f"HTTP {code} — 官方页面已移除/失效, 需人工核对新 URL"
            st["consecutive_failures"] = 0
            all_ok = False
            if st.get("last_status") != "REMOVED":
                drift.append(f"- **{src['label']}** ({key}): 官方页面 **{status}** — {note} (URL: {urls[0]})")
            st["last_status"] = status
            st["last_note"] = note
            st["last_checked"] = today
            lines.append(f"{status:<11} {key} — {note}")
        elif code == 0 or code in (403, 500, 502, 503, 504):
            status = "UNREACHABLE"
            st["consecutive_failures"] = st.get("consecutive_failures", 0) + 1
            st["last_status"] = status
            st["last_checked"] = today
            st["last_note"] = reason
            all_ok = False
            if st["consecutive_failures"] >= FAIL_ALERT and st["consecutive_failures"] % FAIL_ALERT == 0:
                drift.append(f"- **{src['label']}** ({key}): 已连续 **{st['consecutive_failures']}** 次不可达"
                             f" (最近: {st['last_note']}) — 保留核验日期 {old_date or '无'}, 需检查网络/代理")
            lines.append(f"{status:<11} {key} — {st['last_note']} (连续失败 {st['consecutive_failures']})")
        else:
            fact_keys, fact_samples = extract_facts(text, facts_re)
            new_facts_hash = sha(json.dumps(fact_keys, ensure_ascii=False))
            new_page_hash = sha(text)
            if not fact_keys:
                status = "ANOMALY"
                st["consecutive_failures"] = 0
                st["last_status"] = status
                st["last_checked"] = today
                st["last_note"] = "页面 200 但未提取到任何关键事实 — 页面结构可能已改, 需人工核对"
                all_ok = False
                if st.get("page_hash") != new_page_hash:
                    drift.append(f"- **{src['label']}** ({key}): **ANOMALY** — 页面可达但提取不到规格事实"
                                 f" (hash {st.get('page_hash','-')} → {new_page_hash}), 需人工核对 {urls[0]}")
                lines.append(f"{status:<11} {key} — {st['last_note']}")
            elif new_facts_hash != facts_hash and facts_hash:
                status = "CHANGED"
                st["consecutive_failures"] = 0
                st["last_status"] = status
                st["last_checked"] = today
                st["last_note"] = f"规格事实变更 {facts_hash} → {new_facts_hash}"
                old_keys = st.get("last_facts", [])
                new_keys = [k for k in fact_keys if k not in old_keys]
                gone_keys = [k for k in old_keys if k not in fact_keys]
                old_samp = st.get("last_samples", {})
                new_f = [f"{k} ({fact_samples.get(k)})" for k in new_keys]
                gone_f = [f"{k} ({old_samp.get(k)})" for k in gone_keys]
                drift.append(
                    f"- **{src['label']}** ({key}): **规格变更** — 官方页 {urls[0]}\n"
                    f"  - 新增/变化事实: {new_f or '—'}\n  - 消失事实: {gone_f or '—'}\n"
                    f"  - **数值与核验日期未自动修改**(红线: 真实规格数据), 请人工复核后手动更新 JSON + 日期")
                all_ok = False
                lines.append(f"{status:<11} {key} — 事实变更, 需人工复核(数值/日期未动)")
            else:
                if facts_hash:
                    status = "OK" if new_page_hash == page_hash else "COSMETIC"
                else:
                    status = "OK"  # 首次成功建立基线
                st["consecutive_failures"] = 0
                st["last_status"] = status
                st["last_checked"] = today
                st["last_note"] = "页面措辞变化, 规格事实未变" if status == "COSMETIC" else "OK"
                spec["verified_date"] = today  # 事实稳定 = 今日对官方页复核通过, 刷新核验日期
                updated.append(key)
                lines.append(f"{status:<11} {key} — {'规格未变, 仅措辞更新' if status == 'COSMETIC' else 'OK'} → 核验日期 {spec['verified_date']}")

            st["facts_hash"] = new_facts_hash
            st["page_hash"] = new_page_hash
            st["last_facts"] = fact_keys
            st["last_samples"] = fact_samples

        state[key] = st

    if all_ok:
        ds["last_verified"] = today

    save_json(DATASET_FP, ds)
    write_csv(ds)
    save_json(STATE_FP, state)

    if drift:
        with open(DRIFT_FP, "a", encoding="utf-8") as f:
            f.write(f"\n## {today} — 需人工复核\n")
            for d in drift:
                f.write(d + "\n")

    with open(REPORT_FP, "w", encoding="utf-8") as f:
        f.write(f"# spec_fetch — 最近一次运行: {today}\n\n"
                f"- 完整复核(全部源可达): {'是 ✅' if all_ok else '否(部分源不可达, 保留各自核验日期)'}\n"
                f"- 本轮刷新核验日期: {', '.join(updated) if updated else '无'}\n"
                f"- 连续失败告警阈值: {FAIL_ALERT} 次\n\n")
        for key, st in state.items():
            f.write(f"- `{key}`: {st.get('last_status','-')} — 核验日期 "
                    f"{specs.get(key, {}).get('verified_date') or st.get('verified_date') or '未设置'} "
                    f"(last_checked {st.get('last_checked','-')})\n")

    print("\n".join(lines))
    print(f"verified_date refreshed: {len(updated)} source(s)")
    print(f"drift entries this run: {len(drift)}")
    print(f"dataset -> {DATASET_FP}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
