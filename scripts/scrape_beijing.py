"""
爬取北京分数线数据
复用 run_full_pipeline.py 的爬取逻辑，专门针对北京省份
"""

import json
import os
import time
import random
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def main():
    log("=" * 60)
    log("爬取北京分数线数据")
    log("=" * 60)

    # 加载已有数据
    scores_path = os.path.join(DATA_DIR, "eol_scores.json")
    with open(scores_path, "r", encoding="utf-8") as f:
        all_scores = json.load(f)

    # 加载学校名单和ID映射
    ranking_path = os.path.join(DATA_DIR, "shanghairanking_cleaned.json")
    with open(ranking_path, "r", encoding="utf-8") as f:
        schools = json.load(f)

    id_map_path = os.path.join(DATA_DIR, "eol_school_ids.json")
    with open(id_map_path, "r", encoding="utf-8") as f:
        id_map = json.load(f)

    # 构建学校列表
    school_list = []
    for s in schools:
        name = s["name"]
        sid = id_map.get(name)
        if not sid:
            for k, v in id_map.items():
                if name in k or k in name:
                    sid = v
                    break
        if sid:
            school_list.append((name, sid))

    log(f"共 {len(school_list)} 所大学待检查")

    from playwright.sync_api import sync_playwright

    def parse_score_responses(score_responses, school_name, school_id):
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
                # 只要北京数据
                if "北京" not in province:
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

    def scrape_school_beijing(page, school_id, school_name):
        school_scores = []
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

            # 先检查默认页面是否是北京
            initial = parse_score_responses(score_responses, school_name, school_id)
            school_scores.extend(initial)
            score_responses.clear()

            # 遍历省份切换按钮，找北京
            province_count = page.locator("[class*='province-switch_item']").count()
            for idx in range(province_count):
                try:
                    text = page.locator("[class*='province-switch_item']").nth(idx).text_content()
                    if "北京" in text:
                        score_responses.clear()
                        page.locator("[class*='province-switch_item']").nth(idx).dispatch_event("click")
                        time.sleep(1.5)
                        new_scores = parse_score_responses(score_responses, school_name, school_id)
                        school_scores.extend(new_scores)
                        break
                except:
                    continue
        except Exception as e:
            log(f"    爬取失败: {e}")

        page.remove_listener("response", on_response)

        # 去重
        seen = set()
        unique = []
        for s in school_scores:
            key = (s["school_id"], s.get("year"), s.get("province"), s.get("category"), s.get("min_score"))
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique

    # 检查哪些学校已有北京数据
    existing_beijing = set()
    for s in all_scores:
        if s.get("province") == "北京":
            existing_beijing.add(s["school_id"])

    schools_to_scrape = [(name, sid) for name, sid in school_list if sid not in existing_beijing]
    log(f"已有北京数据: {len(existing_beijing)} 所")
    log(f"待爬取: {len(schools_to_scrape)} 所")

    if not schools_to_scrape:
        log("所有学校已有北京数据！")
        return

    new_scores = []

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

        total = len(schools_to_scrape)
        log(f"开始爬取 {total} 所大学的北京数据...")

        for i, (name, sid) in enumerate(schools_to_scrape):
            log(f"  [{i+1}/{total}] {name} (id={sid})")
            try:
                scores = scrape_school_beijing(page, sid, name)
                new_scores.extend(scores)
                if scores:
                    log(f"    获取 {len(scores)} 条北京数据")
                else:
                    log(f"    无北京数据")

                # 每10所学校保存一次
                if (i + 1) % 10 == 0:
                    combined = all_scores + new_scores
                    with open(scores_path, "w", encoding="utf-8") as f:
                        json.dump(combined, f, ensure_ascii=False, indent=2)
                    log(f"  已保存 {len(new_scores)} 条新数据")

                delay = random.uniform(2, 4)
                time.sleep(delay)

                # 每50所休息
                if (i + 1) % 50 == 0 and i + 1 < total:
                    rest = random.uniform(30, 60)
                    log(f"  已完成 {i+1}/{total}，休息 {rest:.0f} 秒...")
                    time.sleep(rest)

            except Exception as e:
                log(f"    异常: {e}")
                continue

        browser.close()

    # 最终保存
    combined = all_scores + new_scores
    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    log(f"爬取完成: 新增 {len(new_scores)} 条北京数据")
    log(f"总计: {len(combined)} 条数据")


if __name__ == "__main__":
    main()
