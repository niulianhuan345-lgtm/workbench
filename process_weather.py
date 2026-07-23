#!/usr/bin/env python3
"""Process weather + delivery fee CSV for Lark sheets."""
import csv
import json
import sys
from collections import defaultdict

TIER_ORDER = {
    "一线城市": 0, "新一线城市": 1, "二线城市": 2,
    "三线城市": 3, "四线城市": 4, "五线城市": 5,
}
TIER_ORDER_DEFAULT = 99

PROVINCE_REGION = {
    "广东": "华南", "广西": "华南", "海南": "华南",
    "上海": "华东", "江苏": "华东", "浙江": "华东", "安徽": "华东",
    "福建": "华东", "江西": "华东", "山东": "华东",
    "北京": "华北", "天津": "华北", "河北": "华北", "山西": "华北", "内蒙古": "华北",
    "河南": "华中", "湖北": "华中", "湖南": "华中",
    "重庆": "西南", "四川": "西南", "贵州": "西南", "云南": "西南", "西藏": "西南",
    "陕西": "西北", "甘肃": "西北", "青海": "西北", "宁夏": "西北", "新疆": "西北",
    "辽宁": "东北", "吉林": "东北", "黑龙江": "东北",
}

REGION_ORDER = ["华南", "华东", "华北", "华中", "西南", "西北", "东北"]

def get_region(p):
    return PROVINCE_REGION.get(p.strip(), "未知")

def weather_cat(w):
    w = w.strip() if w else ""
    if not w: return "未知"
    if "暴雨" in w: return "暴雨+"
    if "大雨" in w: return "大雨+"
    if "雨" in w: return "小雨/阵雨"
    if any(k in w for k in ["晴", "多云", "阴", "雾", "霾"]): return "晴好"
    return "其他"

def istemp(t):
    try: return float(t) >= 35
    except: return False

def main():
    with open("/private/tmp/workbench/weather_data.csv", "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Total: {len(rows)}")

    # Filter to today's data only (2026-07-22)
    today_rows = [r for r in rows if r.get("日期","").strip() == "2026-07-22"]
    print(f"Today rows: {len(today_rows)}")

    def sk(r):
        t = r.get("城市分层","").strip()
        return (TIER_ORDER.get(t, TIER_ORDER_DEFAULT), r.get("城市","").strip())
    today_rows.sort(key=sk)

    # Write sorted CSV
    fields = ["城市","城市分层","省份","天气","温度","众数配送费","众数配送费门店占比"]
    outpath = "/private/tmp/workbench/weather_sorted.csv"
    with open(outpath, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for r in today_rows:
            w.writerow({k: r.get(k,"") for k in fields})
    print(f"Sorted: {outpath} ({len(today_rows)} rows)")

    # --- Analysis ---
    reg = defaultdict(lambda: {
        "cities": set(), "暴雨+":0, "大雨+":0, "小雨/阵雨":0, "晴好":0, "高温":0,
        "免配":0, "half_yuan":0, "other_fee":0,
        "severe": [], "hitemp": [],
    })

    for r in today_rows:
        prov = r.get("省份","").strip()
        city = r.get("城市","").strip()
        weather = r.get("天气","").strip()
        temp = r.get("温度","").strip()
        fee = r.get("众数配送费","").strip()
        region = get_region(prov)
        s = reg[region]
        s["cities"].add(city)

        cat = weather_cat(weather)
        if cat in s:
            s[cat] += 1

        if istemp(temp):
            s["高温"] += 1
            try: tv = float(temp)
            except: tv = 0
            s["hitemp"].append((city, tv, weather))

        try: fv = float(fee) if fee else 0
        except: fv = 0

        if fv > 0:
            if fv < 0.01: s["免配"] += 1
            elif fv <= 0.5: s["half_yuan"] += 1
            else: s["other_fee"] += 1

        if cat in ("暴雨+", "大雨+"):
            s["severe"].append((city, weather, temp))

    total_cities = len(set(r.get("城市","").strip() for r in today_rows))
    summary = []
    for region in REGION_ORDER:
        if region not in reg: continue
        s = reg[region]
        nc = len(s["cities"])
        wp = []
        if s["暴雨+"]: wp.append(f"暴雨+{s['暴雨+']}城")
        if s["大雨+"]: wp.append(f"大雨{s['大雨+']}城")
        if s["小雨/阵雨"]: wp.append(f"小雨{s['小雨/阵雨']}城")
        if s["晴好"]: wp.append(f"晴好{s['晴好']}城")
        if s["高温"]: wp.append(f"高温{s['高温']}城")
        wf = "、".join(wp) if wp else "—"

        if s["暴雨+"] > 0: sev = "⚠️ 严重" if s["暴雨+"] >= 3 else "⚠️ 关注"
        elif s["大雨+"] > 0: sev = "⚠️ 关注"
        elif s["高温"] >= 5: sev = "⚠️ 关注"
        else: sev = "✅ 正常"

        reps = [c[0] for c in (s["severe"] + s["hitemp"])[:5]]
        rep = "、".join(reps) if reps else "—"

        fp = []
        if s["免配"]: fp.append(f"免配{s['免配']}城")
        if s["half_yuan"]: fp.append(f"0.5元{s['half_yuan']}城")
        if s["other_fee"]: fp.append(f"其他{s['other_fee']}城")
        fs = "、".join(fp) if fp else "暂无数据"

        summary.append({
            "region": region, "city_count": nc, "weather_feat": wf,
            "severity": sev, "representative": rep, "fee_summary": fs,
            "暴雨+": s["暴雨+"], "大雨+": s["大雨+"], "高温": s["高温"],
            "免配": s["免配"], "half_yuan": s["half_yuan"], "other_fee": s["other_fee"],
            "severe_cities": s["severe"], "high_temp_cities": s["hitemp"],
        })

    out = {"total_cities": total_cities, "regions": summary}
    with open("/private/tmp/workbench/weather_analysis.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n=== DASHBOARD ===")
    for sl in summary:
        print(f"{sl['region']}: {sl['city_count']}城 | {sl['weather_feat']} | {sl['severity']} | {sl['fee_summary']}")

    # Also print useful info for the WeChat message
    print("\n=== WECHAT DATA ===")
    # All severe cities by region
    for sl in summary:
        if sl["severe_cities"]:
            cities_str = "、".join([f"{c[0]}({c[1]})" for c in sl["severe_cities"]])
            print(f"{sl['region']}暴雨/大雨: {cities_str}")
    for sl in summary:
        if sl["high_temp_cities"]:
            cities_str = "、".join([f"{c[0]}({c[1]}℃)" for c in sl["high_temp_cities"]])
            print(f"{sl['region']}高温: {cities_str}")

    # Fee summary
    free_total = sum(sl["免配"] for sl in summary)
    half_total = sum(sl["half_yuan"] for sl in summary)
    other_total = sum(sl["other_fee"] for sl in summary)
    fee_total = free_total + half_total + other_total
    if fee_total > 0:
        print(f"配送费: 免配{free_total}城({100*free_total/fee_total:.0f}%)、0.5元{half_total}城({100*half_total/fee_total:.0f}%)、其他{other_total}城")
    else:
        print("配送费: 暂无数据")

if __name__ == "__main__":
    main()
