"""
爬取软科专业排名（中国最好学科排名）
网址：https://www.shanghairanking.cn/rankings/bcsr/

直接使用公开 JSON API，无需 Playwright
API:
  - 学科列表: /api/pub/v1/bcsr/subj?year=2024
  - 排名数据: /api/pub/v1/bcsr/rank?target_yr=2024&yr=2023&subj_code=XXXX
"""

import json
import os
import time
import requests
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
API_BASE = "https://www.shanghairanking.cn/api/pub/v1/bcsr"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_subject_list(year=2024):
    """获取所有学科分类及学科列表"""
    url = f"{API_BASE}/subj?year={year}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    categories = []
    all_subjects = []

    for cat in data.get("data", []):
        cat_name = cat.get("nameCn", "")
        cat_code = cat.get("code", "")
        categories.append({"code": cat_code, "name": cat_name})

        for subj in cat.get("subjs", []):
            all_subjects.append({
                "code": subj.get("code", ""),
                "name": subj.get("nameCn", ""),
                "category": cat_name,
                "years": subj.get("years", [])
            })

    return categories, all_subjects


def get_subject_ranking(subj_code, year=2024):
    """获取某个学科的排名数据"""
    url = f"{API_BASE}/rank?target_yr={year}&yr={year-1}&subj_code={subj_code}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    rankings = []
    for r in data.get("data", {}).get("rankings", []):
        rankings.append({
            "university": r.get("univNameCn", ""),
            "univ_code": r.get("univCode", ""),
            "ranking": r.get("ranking"),
            "score": r.get("score"),
            "rank_pct": r.get("rankPctTop", ""),
            "top_n": r.get("rankPctTopNum"),
        })

    return rankings


def scrape_all_subjects(year=2024):
    """爬取所有学科的排名数据"""
    print(f"[1/3] 获取 {year} 年学科列表...")
    categories, subjects = get_subject_list(year)
    print(f"  {len(categories)} 个学科门类, {len(subjects)} 个学科")

    all_data = []
    print(f"\n[2/3] 开始爬取 {len(subjects)} 个学科的排名...")

    for i, subj in enumerate(subjects):
        code = subj["code"]
        name = subj["name"]
        cat = subj["category"]

        if year not in subj.get("years", []):
            print(f"  [{i+1}/{len(subjects)}] {name} ({code}) - {year}年无数据，跳过")
            continue

        try:
            rankings = get_subject_ranking(code, year)
            for r in rankings:
                r["subject"] = name
                r["subject_code"] = code
                r["category"] = cat
                r["year"] = year
            all_data.extend(rankings)
            print(f"  [{i+1}/{len(subjects)}] {name} ({code}) - {len(rankings)} 所大学")

            time.sleep(0.5)  # 轻量延迟

        except Exception as e:
            print(f"  [{i+1}/{len(subjects)}] {name} ({code}) - 失败: {e}")
            continue

    print(f"\n[3/3] 共获取 {len(all_data)} 条专业排名数据")
    return all_data


def save_data(data, filename="shanghai_subject_ranking.json"):
    """保存数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存到: {filepath}")
    return filepath


if __name__ == "__main__":
    print("=" * 50)
    print("软科专业排名爬虫（公开 API）")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    import sys
    year = 2024
    for arg in sys.argv[1:]:
        try:
            year = int(arg)
        except:
            pass

    print(f"目标年份: {year}")
    print()

    data = scrape_all_subjects(year=year)

    if data:
        save_data(data)

        print("\n前 10 条预览:")
        for d in data[:10]:
            print(f"  {d['subject']} #{d['ranking']} {d['university']} score={d['score']}")
    else:
        print("\n未获取到数据")
