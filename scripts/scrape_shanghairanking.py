"""
爬取软科中国大学排名
网址：https://www.shanghairanking.cn/rankings/bcur/2025
注意：该网站数据由 JavaScript 渲染，必须用 Playwright

防封禁措施：
- 真人延迟（2-7秒随机）
- 模拟真人滚动
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
    """随机延迟"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_scroll(page):
    """模拟真人滚动"""
    scroll_height = page.evaluate("document.body.scrollHeight")
    current = 0
    while current < scroll_height:
        step = random.randint(200, 500)
        current += step
        page.evaluate(f"window.scrollTo(0, {current})")
        time.sleep(random.uniform(0.5, 1.5))


def scrape_shanghairanking(max_pages=20):
    """
    爬取软科中国大学排名（主榜），支持翻页
    返回格式：[{"rank": "1", "name": "清华大学", "province": "北京", ...}]
    """
    from playwright.sync_api import sync_playwright

    all_schools = []

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
            print("[1/3] 正在访问软科排名页面...")
            page.goto("https://www.shanghairanking.cn/rankings/bcur/2025", timeout=30000)
            human_delay(3, 6)

            print("[2/3] 等待 JavaScript 渲染...")
            page.wait_for_selector("table", timeout=15000)
            human_delay(2, 4)

            print("[3/3] 开始提取数据...")

            for page_num in range(1, max_pages + 1):
                print(f"\n  第 {page_num} 页...")

                # 模拟滚动
                human_scroll(page)
                human_delay(1, 3)

                # 提取当前页数据
                rows = page.query_selector_all("table tbody tr")
                print(f"  找到 {len(rows)} 条记录")

                for i, row in enumerate(rows):
                    try:
                        cells = row.query_selector_all("td")
                        if len(cells) >= 4:
                            rank = cells[0].inner_text().strip()
                            name = cells[1].inner_text().strip()
                            province = cells[2].inner_text().strip() if len(cells) > 2 else ""
                            score = cells[3].inner_text().strip() if len(cells) > 3 else ""

                            all_schools.append({
                                "rank": rank,
                                "name": name,
                                "province": province,
                                "score": score,
                                "year": 2025,
                                "source": "软科排名"
                            })
                    except Exception as e:
                        print(f"  第 {i} 行解析出错: {e}")
                        continue

                # 翻页：查找下一页按钮
                if page_num < max_pages:
                    next_btn = page.query_selector('li.ant-pagination-next:not(.ant-pagination-disabled) button')
                    if not next_btn:
                        next_btn = page.query_selector('.ant-pagination-next:not(.ant-pagination-disabled)')
                    if not next_btn:
                        next_btn = page.query_selector('a[aria-label="next page"]')

                    if next_btn:
                        between_delay = random.uniform(3, 7)
                        print(f"  等待 {between_delay:.1f} 秒后翻页...")
                        time.sleep(between_delay)
                        next_btn.click()
                        human_delay(3, 6)

                        # 等待新数据加载
                        try:
                            page.wait_for_selector("table tbody tr", timeout=10000)
                        except:
                            print("  翻页后数据加载超时，停止翻页")
                            break
                    else:
                        print("  没有下一页了")
                        break

            print(f"\n软科排名: 成功爬取 {len(all_schools)} 所大学")

        except Exception as e:
            print(f"爬取失败: {e}")
            print("可能原因: 网站改版 / 网络问题 / 被封禁")

        browser.close()

    return all_schools


def save_data(data, filename):
    """保存数据到 JSON"""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filepath}（{len(data)} 条）")
    return filepath


if __name__ == "__main__":
    print("=" * 50)
    print("软科中国大学排名爬虫（带真人延迟防封禁）")
    print("=" * 50)
    print(f"目标: https://www.shanghairanking.cn/rankings/bcur/2025")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    schools = scrape_shanghairanking()

    if schools:
        save_data(schools, "shanghairanking_2025.json")
        print("\n前 10 条数据预览:")
        for s in schools[:10]:
            print(f"  {s['rank']}. {s['name']}（{s['province']}）- {s['score']}")
    else:
        print("\n未获取到数据，请检查网络或网站是否改版")
