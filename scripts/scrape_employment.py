"""
爬取高校就业质量数据
数据源：eol.cn 静态 API（无需 Playwright）

API: https://static-data.gaokao.cn/www/2.0/school/{school_id}/pc_jobdetail.json
数据包括：就业率、考研率、出国率、就业地区分布、就业行业分布
"""

import json
import os
import time
import requests
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def load_school_id_map():
    """加载学校 ID 映射表"""
    cache_path = os.path.join(DATA_DIR, "eol_school_ids.json")
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print("  正在下载学校 ID 映射表...")
    resp = requests.get(
        "https://static-data.gaokao.cn/www/2.0/info/linkage.json?a=www.gaokao.cn",
        headers=HEADERS, timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        school_list = data.get("data", {}).get("school", [])
        id_map = {}
        for item in school_list:
            name = item.get("name", "")
            sid = item.get("school_id", "")
            if name and sid:
                id_map[name] = sid
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(id_map, f, ensure_ascii=False, indent=2)
        print(f"  下载完成，共 {len(id_map)} 所学校")
        return id_map
    return {}


def load_school_names():
    """从已有数据中提取大学名单"""
    names = set()
    for filename in ["shanghairanking_cleaned.json", "shanghairanking_2025.json"]:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            name = item.get("name", "")
            if name and "\n" not in name:
                names.add(name)
            elif name:
                chinese = name.split("\n")[0].strip()
                if chinese:
                    names.add(chinese)
    return sorted(names)


def scrape_employment(school_id, school_name):
    """爬取一所大学的就业数据"""
    url = f"https://static-data.gaokao.cn/www/2.0/school/{school_id}/pc_jobdetail.json?a=www.gaokao.cn"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json().get("data", {})
        if not data:
            return None

        # 提取就业率
        job_rate = data.get("jobrate", {})
        job_year = data.get("jobrateyear", "")
        employment_rate = None
        postgraduate_rate = None
        abroad_rate = None

        if job_rate:
            job_data = job_rate.get("job", {})
            if job_data:
                employment_rate = list(job_data.values())[0] if job_data else None
            pg_data = job_rate.get("postgraduate", {})
            if pg_data:
                postgraduate_rate = list(pg_data.values())[0] if pg_data else None
            ab_data = job_rate.get("abroad", {})
            if ab_data:
                abroad_rate = list(ab_data.values())[0] if ab_data else None

        # 提取地区分布
        provinces = []
        for p in data.get("province", []):
            provinces.append({
                "name": p.get("province", ""),
                "rate": p.get("rate", "")
            })

        # 提取行业分布
        industries = []
        for ind in data.get("industry", []):
            industries.append({
                "name": ind.get("industry", ""),
                "rate": ind.get("rate", "")
            })

        return {
            "school": school_name,
            "school_id": school_id,
            "year": job_year,
            "employment_rate": employment_rate,
            "postgraduate_rate": postgraduate_rate,
            "abroad_rate": abroad_rate,
            "province_distribution": provinces,
            "industry_distribution": industries,
            "source": "中国教育在线"
        }

    except Exception:
        return None


def scrape_all(max_schools=None):
    """爬取所有大学的就业数据"""
    school_names = load_school_names()
    if not school_names:
        print("错误：没有找到大学名单")
        return []

    id_map = load_school_id_map()
    if not id_map:
        print("错误：无法加载学校 ID 映射表")
        return []

    # 匹配 school_id
    school_list = []
    for name in school_names:
        sid = id_map.get(name)
        if not sid:
            for map_name, map_sid in id_map.items():
                if name in map_name or map_name in name:
                    sid = map_sid
                    break
        if sid:
            school_list.append((name, sid))

    if max_schools:
        school_list = school_list[:max_schools]

    print(f"准备爬取 {len(school_list)} 所大学的就业数据")

    all_data = []
    for i, (name, sid) in enumerate(school_list):
        result = scrape_employment(sid, name)
        if result:
            all_data.append(result)

        if (i + 1) % 50 == 0:
            print(f"  已处理 {i+1}/{len(school_list)}...")

        time.sleep(0.3)  # 轻量延迟

    print(f"共获取 {len(all_data)} 所大学的就业数据")
    return all_data


def save_data(data, filename="employment_data.json"):
    """保存数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存到: {filepath}")
    return filepath


if __name__ == "__main__":
    print("=" * 50)
    print("高校就业数据爬虫（eol.cn 静态 API）")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    import sys
    max_schools = None
    for arg in sys.argv[1:]:
        try:
            max_schools = int(arg)
        except:
            pass

    data = scrape_all(max_schools=max_schools)

    if data:
        save_data(data)
        print(f"\n前 5 条预览:")
        for d in data[:5]:
            print(f"  {d['school']} 就业率={d['employment_rate']}% 考研率={d['postgraduate_rate']}% 出国率={d['abroad_rate']}%")
    else:
        print("\n未获取到数据")
