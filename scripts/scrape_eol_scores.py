"""
爬取中国教育在线录取分数线
网址：https://gkcx.eol.cn / https://www.gaokao.cn

流程：
1. 从静态 API 获取 school_id 映射表
2. 用 Playwright 加载分数线页面，拦截 API 响应
3. 逐个点击省份 tab，获取各省份分数线数据
4. 保存为 JSON

防封禁措施：
- 真人延迟（2-5秒随机）
- 隐藏自动化特征
"""

import json
import os
import random
import time
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")


def human_delay(min_sec=2, max_sec=5):
    time.sleep(random.uniform(min_sec, max_sec))


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


def load_school_id_map():
    """从 eol.cn 静态 API 加载 school_id 映射表"""
    import requests as req

    cache_path = os.path.join(DATA_DIR, "eol_school_ids.json")
    if os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        if time.time() - mtime < 7 * 24 * 3600:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

    print("  正在下载学校 ID 映射表...")
    try:
        resp = req.get(
            "https://static-data.gaokao.cn/www/2.0/info/linkage.json?a=www.gaokao.cn",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=30
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
    except Exception as e:
        print(f"  下载失败: {e}")
    return {}


def match_school_id(school_name, id_map):
    """从映射表中匹配 school_id"""
    if school_name in id_map:
        return id_map[school_name]
    for name, sid in id_map.items():
        if school_name in name or name in school_name:
            return sid
    return None


def parse_score_responses(score_responses, school_name, school_id):
    """解析拦截到的 API 响应"""
    scores = []
    seen = set()
    for resp in score_responses:
        items = resp.get("data", {}).get("item", [])
        for item in items:
            min_score = item.get("min")
            province = item.get("local_province_name", "")
            category = item.get("local_type_name", "")
            year = item.get("year")
            if not min_score:
                continue
            key = (school_id, year, province, category, min_score)
            if key in seen:
                continue
            seen.add(key)
            scores.append({
                "school": school_name,
                "school_id": school_id,
                "year": year,
                "province": province,
                "category": category,
                "batch": item.get("local_batch_name", ""),
                "min_score": min_score,
                "min_rank": item.get("min_section"),
                "avg_score": item.get("proscore"),
                "source": "中国教育在线"
            })
    return scores


def scrape_school_scores(page, school_id, school_name):
    """爬取一所大学的录取分数线（通过 API 拦截 + 省份 tab 点击）"""
    all_scores = []
    score_responses = []

    def on_response(response):
        try:
            if response.status == 200 and "province_score" in response.url:
                score_responses.append(response.json())
        except:
            pass

    page.on("response", on_response)

    try:
        url = f"https://www.gaokao.cn/school/{school_id}/provinceline"
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)

        # 收集初始页面加载的数据
        initial = parse_score_responses(score_responses, school_name, school_id)
        all_scores.extend(initial)
        score_responses.clear()

        # 点击各省份 tab
        province_count = page.locator("[class*='province-switch_item']").count()

        for idx in range(1, min(province_count, 31)):
            try:
                score_responses.clear()
                page.locator("[class*='province-switch_item']").nth(idx).dispatch_event("click")
                time.sleep(1.0)
                new_scores = parse_score_responses(score_responses, school_name, school_id)
                all_scores.extend(new_scores)
            except Exception:
                continue

    except Exception as e:
        print(f"    爬取失败: {e}")

    page.remove_listener("response", on_response)

    # 去重
    seen = set()
    unique = []
    for s in all_scores:
        key = (s["school_id"], s.get("year"), s.get("province"), s.get("category"), s.get("min_score"))
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def load_existing_scores():
    """加载已有的分数线数据，用于断点续爬"""
    filepath = os.path.join(DATA_DIR, "eol_scores.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        scraped_ids = set(s["school_id"] for s in data)
        print(f"  已有数据: {len(data)} 条, {len(scraped_ids)} 所大学")
        return data, scraped_ids
    return [], set()


def save_scores(scores):
    """增量保存分数线数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, "eol_scores.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


def scrape_eol_scores(max_schools=50, debug=False):
    """主爬取函数（支持断点续爬）"""
    from playwright.sync_api import sync_playwright

    school_names = load_school_names()
    if not school_names:
        print("错误：没有找到大学名单")
        return []

    school_names = school_names[:max_schools]
    print(f"目标: {len(school_names)} 所大学的录取分数线")

    print("[1/4] 加载学校 ID 映射表...")
    id_map = load_school_id_map()
    if not id_map:
        print("  无法加载映射表")
        return []

    # 预匹配
    school_list = []
    for name in school_names:
        sid = match_school_id(name, id_map)
        if sid:
            school_list.append((name, sid))
    print(f"  匹配: {len(school_list)}/{len(school_names)} 所学校")

    if not school_list:
        return []

    # 断点续爬：加载已有数据，跳过已爬学校
    all_scores, scraped_ids = load_existing_scores()
    school_list = [(name, sid) for name, sid in school_list if sid not in scraped_ids]
    print(f"  待爬取: {len(school_list)} 所（跳过已有的 {len(scraped_ids)} 所）")

    if not school_list:
        print("  所有学校已爬取完毕！")
        return all_scores

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = context.new_page()

        try:
            total = len(school_list)
            print(f"\n[2/4] 开始爬取 {total} 所大学...")

            for i, (name, sid) in enumerate(school_list):
                print(f"\n  [{i+1}/{total}] {name} (id={sid})")
                scores = scrape_school_scores(page, sid, name)
                all_scores.extend(scores)
                print(f"    获取 {len(scores)} 条数据")

                # 每爬完一所就保存（断点续爬）
                save_scores(all_scores)

                # 学校间延迟
                delay = random.uniform(2, 4)
                time.sleep(delay)

                # 每20所休息一下
                if (i + 1) % 20 == 0 and i + 1 < total:
                    rest = random.uniform(15, 30)
                    print(f"\n  已完成 {i+1}/{total}，休息 {rest:.0f} 秒...")
                    time.sleep(rest)

        except Exception as e:
            print(f"爬取出错: {e}")
            # 出错也保存已爬数据
            save_scores(all_scores)
            print(f"  已保存 {len(all_scores)} 条数据")

        browser.close()

    print(f"\n[3/4] 共获取 {len(all_scores)} 条分数线数据")

    # 最终保存
    save_scores(all_scores)
    filepath = os.path.join(DATA_DIR, "eol_scores.json")
    print(f"[4/4] 已保存到 {filepath}")

    return all_scores


if __name__ == "__main__":
    print("=" * 50)
    print("中国教育在线录取分数线爬虫")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    import sys
    max_schools = 20
    for arg in sys.argv[1:]:
        if arg == "--debug":
            pass
        else:
            try:
                max_schools = int(arg)
            except:
                pass

    print(f"计划爬取: {max_schools} 所大学")
    print()

    scores = scrape_eol_scores(max_schools=max_schools)

    if scores:
        print("\n前 10 条预览:")
        for s in scores[:10]:
            print(f"  {s['school']} {s.get('year','')} {s.get('province','')} {s.get('category','')} 最低分={s.get('min_score','?')}")
    else:
        print("\n未获取到数据")
