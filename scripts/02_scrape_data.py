"""
第二步：使用保存的 Cookie 自动爬取数据
用途：登录后自动采集高考数据，保存为 JSON
每年运行一次即可更新数据

重要：所有操作都加了真人延迟，避免被网站封禁
"""

import json
import os
import sys
import time
import random
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
COOKIE_DIR = os.path.join(BASE_DIR, "cookies")
DATA_DIR = os.path.join(BASE_DIR, "data")


# ============================================================
# 真人延迟工具（必须用，不然会被封）
# ============================================================

def human_delay(min_sec=1, max_sec=3):
    """随机延迟，模拟真人操作间隔"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

def page_load_delay():
    """页面加载后等待，模拟真人阅读页面"""
    time.sleep(random.uniform(2, 5))

def scroll_delay():
    """滚动页面后等待，模拟真人浏览"""
    time.sleep(random.uniform(0.5, 1.5))

def click_delay():
    """点击操作后等待，模拟真人点击"""
    time.sleep(random.uniform(0.8, 2.0))

def between_pages_delay():
    """翻页之间等待，模拟真人翻页"""
    time.sleep(random.uniform(3, 7))


def human_scroll(page):
    """模拟真人滚动页面（不是一下到底，而是分段滚动）"""
    scroll_height = page.evaluate("document.body.scrollHeight")
    current = 0
    while current < scroll_height:
        # 每次滚动 200-500 像素
        step = random.randint(200, 500)
        current += step
        page.evaluate(f"window.scrollTo(0, {current})")
        scroll_delay()
        # 偶尔停一下，模拟真人在看内容
        if random.random() < 0.3:
            time.sleep(random.uniform(1, 3))


def load_cookies(site_name):
    """加载已保存的 Cookie"""
    cookie_path = os.path.join(COOKIE_DIR, f"{site_name}_cookies.json")
    if not os.path.exists(cookie_path):
        print(f"错误：未找到 Cookie 文件 {cookie_path}")
        print(f"请先运行 01_login_save_cookies.py 登录")
        return None
    with open(cookie_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_browser_context(playwright, cookies=None):
    """
    创建浏览器上下文，带反检测措施
    """
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",  # 隐藏自动化特征
        ]
    )

    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    )

    # 注入 Cookie
    if cookies:
        context.add_cookies(cookies)

    # 隐藏 Playwright 特征
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    return browser, context


def scrape_schools():
    """
    爬取院校基本信息
    """
    from playwright.sync_api import sync_playwright

    cookies = load_cookies("gaokao")
    if not cookies:
        return []

    schools = []

    with sync_playwright() as p:
        browser, context = create_browser_context(p, cookies)
        page = context.new_page()

        try:
            # 访问院校列表页
            print("  正在访问阳光高考院校列表...")
            page.goto("https://gaokao.chsi.com.cn/sch/search--ss-985,category-1.dhtml", timeout=30000)
            page_load_delay()  # 等页面加载完

            # 模拟真人滚动浏览
            print("  模拟浏览页面...")
            human_scroll(page)

            # 提取院校信息
            items = page.query_selector_all(".sch-list-item")
            print(f"  找到 {len(items)} 个院校条目")

            for i, item in enumerate(items):
                try:
                    name = item.query_selector(".sch-name")
                    name_text = name.inner_text() if name else "未知"

                    location = item.query_selector(".sch-addr")
                    location_text = location.inner_text() if location else "未知"

                    schools.append({
                        "name": name_text.strip(),
                        "location": location_text.strip(),
                        "source": "阳光高考",
                        "year": datetime.now().year
                    })

                    # 每处理几条就延迟一下
                    if i % 5 == 0 and i > 0:
                        human_delay(1, 2)
                        print(f"  已处理 {i}/{len(items)} 条...")

                except Exception as e:
                    print(f"  解析第 {i} 条出错: {e}")
                    continue

            print(f"  阳光高考: 爬取到 {len(schools)} 所院校")

            # 翻页前等待
            if len(items) > 0:
                between_pages_delay()

        except Exception as e:
            print(f"  阳光高考爬取失败: {e}")

        browser.close()

    return schools


def scrape_scores():
    """
    爬取历年分数线数据
    """
    from playwright.sync_api import sync_playwright

    cookies = load_cookies("eol")
    if not cookies:
        return []

    scores = []

    with sync_playwright() as p:
        browser, context = create_browser_context(p, cookies)
        page = context.new_page()

        try:
            print("  正在访问中国教育在线...")
            page.goto("https://gkcx.eol.cn/school/list", timeout=30000)
            page_load_delay()

            # 模拟浏览
            human_scroll(page)

            print("  分数线爬取：需要根据实际网站结构调整选择器")

        except Exception as e:
            print(f"  分数线爬取失败: {e}")

        browser.close()

    return scores


def scrape_with_pagination(base_url, max_pages=10):
    """
    带翻页的爬取（通用模板）
    自动处理翻页，每页之间有真人延迟
    """
    from playwright.sync_api import sync_playwright

    all_data = []

    with sync_playwright() as p:
        browser, context = create_browser_context(p)
        page = context.new_page()

        for page_num in range(1, max_pages + 1):
            url = f"{base_url}?page={page_num}"
            print(f"  爬取第 {page_num} 页: {url}")

            try:
                page.goto(url, timeout=30000)
                page_load_delay()
                human_scroll(page)

                # 提取数据（需要根据实际页面调整）
                # items = page.query_selector_all("选择器")
                # for item in items:
                #     all_data.append({...})

                # 翻页延迟
                if page_num < max_pages:
                    between_pages_delay()

            except Exception as e:
                print(f"  第 {page_num} 页失败: {e}")
                break

        browser.close()

    return all_data


def scrape_manual_data():
    """加载手动整理的数据"""
    manual_file = os.path.join(DATA_DIR, "manual_schools.json")
    if os.path.exists(manual_file):
        with open(manual_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(data, filename):
    """保存数据到 JSON 文件"""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n数据已保存到: {filepath}（{len(data)} 条）")
    return filepath


# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("高考数据爬取工具（带真人延迟防封禁）")
    print("=" * 50)

    # 1. 加载手动整理的数据
    print("\n[1/3] 加载手动整理的数据...")
    manual = scrape_manual_data()
    print(f"  手动数据: {len(manual)} 条")

    # 2. 爬取院校数据
    print("\n[2/3] 爬取院校数据...")
    human_delay(2, 5)  # 操作之间先等一下
    schools = scrape_schools()

    # 3. 爬取分数线数据
    print("\n[3/3] 爬取分数线数据...")
    between_pages_delay()  # 不同网站之间也要等
    scores = scrape_scores()

    # 合并保存
    all_data = manual + schools + scores
    if all_data:
        save_data(all_data, f"gaokao_data_{datetime.now().year}.json")
    else:
        print("\n没有获取到数据，请检查：")
        print("  1. 是否已运行 01_login_save_cookies.py 登录？")
        print("  2. Cookie 是否过期？")
        print("  3. 网站是否改版？")
        print("\n建议：先手动整理数据到 data/manual_schools.json")
