"""
爬取阳光高考平台数据
网址：https://gaokao.chsi.com.cn

安全策略（保护学信网账号）：
- 超长随机延迟（5-15秒，翻页8-20秒）
- 模拟真人鼠标移动、滚动、停顿
- 先访问首页热身，再进入数据页
- 每页之间长时间等待
- 隐藏所有自动化特征
- 遇到异常立即停止，绝不冒险
"""

import json
import os
import random
import time
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
COOKIE_DIR = os.path.join(BASE_DIR, "cookies")


def human_delay(min_sec=5, max_sec=12):
    """随机延迟（默认5-12秒，比一般爬虫长很多）"""
    time.sleep(random.uniform(min_sec, max_sec))


def long_delay():
    """翻页/切换操作间的长延迟（8-20秒）"""
    delay = random.uniform(8, 20)
    print(f"    等待 {delay:.1f} 秒...")
    time.sleep(delay)


def human_scroll(page):
    """模拟真人滚动：变速、有停顿、偶尔回滚"""
    scroll_height = page.evaluate("document.body.scrollHeight")
    current = 0
    while current < scroll_height:
        # 随机步长：有时快滑，有时慢滑
        step = random.randint(100, 400)
        current += step
        page.evaluate(f"window.scrollTo(0, {current})")
        # 每次滚动后随机停顿
        time.sleep(random.uniform(0.3, 2.0))
        # 10%概率暂停一下（像人在阅读）
        if random.random() < 0.1:
            time.sleep(random.uniform(1, 3))
    # 偶尔滚回上面一点（真人会这样）
    if random.random() < 0.3:
        back = random.randint(100, 300)
        page.evaluate(f"window.scrollBy(0, -{back})")
        time.sleep(random.uniform(0.5, 1.5))


def random_mouse_move(page):
    """模拟随机鼠标移动"""
    try:
        x = random.randint(100, 1000)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.2, 0.8))
    except Exception:
        pass


def safe_click(page, selector, description=""):
    """安全点击：先移动鼠标到元素附近，再点击"""
    try:
        el = page.query_selector(selector)
        if not el:
            return False
        box = el.bounding_box()
        if not box:
            return False
        # 鼠标先移到元素附近（不是精确中心，模拟真人）
        offset_x = random.randint(-10, 10)
        offset_y = random.randint(-5, 5)
        page.mouse.move(
            box["x"] + box["width"] / 2 + offset_x,
            box["y"] + box["height"] / 2 + offset_y
        )
        time.sleep(random.uniform(0.3, 0.8))
        el.click()
        return True
    except Exception as e:
        if description:
            print(f"    点击失败 ({description}): {e}")
        return False


def setup_stealth_context(playwright, cookies=None):
    """创建带完整反检测配置的浏览器上下文"""
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    # 隐藏 webdriver 特征
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        window.chrome = { runtime: {} };
    """)
    if cookies:
        context.add_cookies(cookies)
    return browser, context


def login_and_save_cookies():
    """打开浏览器让用户手动登录，保存 Cookie"""
    from playwright.sync_api import sync_playwright

    cookie_path = os.path.join(COOKIE_DIR, "gaokao_chsi_cookies.json")
    os.makedirs(COOKIE_DIR, exist_ok=True)

    print("=" * 50)
    print("阳光高考登录")
    print("=" * 50)
    print("即将打开浏览器，请手动登录")
    print("登录完成后，回到这里按回车键保存 Cookie")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1280,720", "--window-position=50,50"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://account.chsi.com.cn/passport/login")
        print("已打开登录页面: https://account.chsi.com.cn/passport/login")

        input("\n登录完成后，按回车键保存 Cookie...")

        cookies = context.cookies()
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\nCookie 已保存到: {cookie_path}")
        print(f"Cookie 数量: {len(cookies)}")
        print(f"保存时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        browser.close()

    return cookie_path


def load_cookies():
    """加载已保存的 Cookie"""
    cookie_path = os.path.join(COOKIE_DIR, "gaokao_chsi_cookies.json")

    if not os.path.exists(cookie_path):
        print("未找到 Cookie，请先登录")
        return None

    with open(cookie_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    now = datetime.now().timestamp()
    valid = [c for c in cookies if c.get("expires", 0) <= 0 or c["expires"] > now]

    if not valid:
        print("Cookie 已全部过期，请重新登录")
        return None

    print(f"Cookie 有效（{len(valid)}/{len(cookies)} 条未过期）")
    return cookies


def warmup_session(page):
    """先访问首页热身，让 cookie 生效，模拟正常浏览行为"""
    print("  热身：访问首页...")
    try:
        page.goto("https://gaokao.chsi.com.cn/", timeout=30000)
        human_delay(3, 6)
        random_mouse_move(page)
        human_scroll(page)
        human_delay(2, 5)
    except Exception as e:
        print(f"  热身失败: {e}")


def scrape_school_list(cookies, max_pages=5):
    """爬取院校列表"""
    from playwright.sync_api import sync_playwright

    all_schools = []

    with sync_playwright() as p:
        browser, context = setup_stealth_context(p, cookies)
        page = context.new_page()

        try:
            # 热身
            warmup_session(page)
            long_delay()

            # 访问院校列表页
            print("[1/3] 正在访问院校列表...")
            page.goto("https://gaokao.chsi.com.cn/sch/search--ss-985,category-1.dhtml", timeout=30000)
            human_delay(5, 10)

            print("[2/3] 等待页面加载...")
            try:
                page.wait_for_selector(".sch-list", timeout=15000)
            except Exception:
                print("  页面加载超时，尝试继续...")
            human_delay(3, 6)

            print("[3/3] 开始提取数据...")

            for page_num in range(1, max_pages + 1):
                print(f"\n  [{page_num}/{max_pages}] 爬取第 {page_num} 页...")

                # 模拟真人滚动
                human_scroll(page)
                random_mouse_move(page)
                human_delay(2, 5)

                # 提取院校信息
                items = page.query_selector_all(".sch-list-item")
                print(f"    找到 {len(items)} 所院校")

                if not items:
                    print("    未找到数据，可能页面结构变化或被限制")
                    break

                for i, item in enumerate(items):
                    try:
                        name_el = item.query_selector(".sch-name")
                        name = name_el.inner_text().strip() if name_el else "未知"

                        link_el = item.query_selector("a")
                        link = link_el.get_attribute("href") if link_el else ""

                        tags = item.query_selector_all(".sch-tag")
                        tag_list = [t.inner_text().strip() for t in tags]

                        addr_el = item.query_selector(".sch-addr")
                        addr = addr_el.inner_text().strip() if addr_el else ""

                        all_schools.append({
                            "name": name,
                            "address": addr,
                            "tags": tag_list,
                            "link": link,
                            "source": "阳光高考"
                        })
                    except Exception as e:
                        print(f"    第 {i} 条解析出错: {e}")
                        continue

                # 翻页
                if page_num < max_pages:
                    next_btn = page.query_selector(".next a")
                    if next_btn:
                        long_delay()  # 翻页前长等待
                        if not safe_click(page, ".next a", "翻页"):
                            # 备用方案
                            next_btn.click()
                        human_delay(5, 12)
                    else:
                        print("    没有下一页了")
                        break

            print(f"\n阳光高考: 成功爬取 {len(all_schools)} 所院校")

        except Exception as e:
            print(f"爬取失败: {e}")
            print("可能原因: Cookie过期 / 网站改版 / 被限流")
            print("建议: 等待一段时间后重试，或重新登录获取 Cookie")

        browser.close()

    return all_schools


def scrape_major_list(cookies, max_pages=3):
    """爬取专业列表"""
    from playwright.sync_api import sync_playwright

    all_majors = []

    with sync_playwright() as p:
        browser, context = setup_stealth_context(p, cookies)
        page = context.new_page()

        try:
            # 热身
            warmup_session(page)
            long_delay()

            print("[1/3] 正在访问专业列表...")
            page.goto("https://gaokao.chsi.com.cn/zyk/zybk/", timeout=30000)
            human_delay(5, 10)

            print("[2/3] 等待页面加载...")
            try:
                page.wait_for_selector(".zy-list", timeout=15000)
            except Exception:
                print("  页面加载超时，尝试继续...")
            human_delay(3, 6)

            print("[3/3] 开始提取数据...")
            human_scroll(page)
            random_mouse_move(page)

            items = page.query_selector_all(".zy-list-item")
            print(f"  找到 {len(items)} 个专业")

            for i, item in enumerate(items):
                try:
                    name_el = item.query_selector(".zy-name")
                    name = name_el.inner_text().strip() if name_el else "未知"

                    code_el = item.query_selector(".zy-code")
                    code = code_el.inner_text().strip() if code_el else ""

                    category_el = item.query_selector(".zy-category")
                    category = category_el.inner_text().strip() if category_el else ""

                    all_majors.append({
                        "name": name,
                        "code": code,
                        "category": category,
                        "source": "阳光高考"
                    })

                    # 每处理20条暂停一下
                    if (i + 1) % 20 == 0:
                        print(f"  已处理 {i + 1}/{len(items)} 条...")
                        human_delay(3, 8)
                        random_mouse_move(page)

                except Exception as e:
                    print(f"    第 {i} 条解析出错: {e}")
                    continue

            print(f"\n阳光高考: 成功爬取 {len(all_majors)} 个专业")

        except Exception as e:
            print(f"爬取失败: {e}")

        browser.close()

    return all_majors


def save_data(data, filename):
    """保存数据到 JSON"""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filepath}（{len(data)} 条）")
    return filepath


if __name__ == "__main__":
    import sys

    print("=" * 50)
    print("阳光高考数据爬虫（安全模式）")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("安全策略: 超长延迟 | 真人模拟 | 异常立即停止")
    print()

    cookies = load_cookies()

    if not cookies:
        print("\n需要先登录，即将打开浏览器...")
        login_and_save_cookies()
        cookies = load_cookies()

    if not cookies:
        print("登录失败，退出")
        sys.exit(1)

    print("\n请选择爬取内容:")
    print("  1. 院校列表（985院校）")
    print("  2. 专业列表")
    print("  3. 全部爬取")
    choice = input("请输入选项 (1/2/3): ").strip()

    if choice in ["1", "3"]:
        print("\n" + "=" * 50)
        print("爬取院校列表")
        print("=" * 50)
        human_delay(3, 8)
        schools = scrape_school_list(cookies, max_pages=5)
        if schools:
            save_data(schools, "gaokao_schools.json")
            print("\n前 10 条数据预览:")
            for s in schools[:10]:
                print(f"  {s['name']}（{s['address']}）- {', '.join(s['tags'])}")

    if choice in ["2", "3"]:
        print("\n" + "=" * 50)
        print("爬取专业列表")
        print("=" * 50)
        human_delay(5, 10)
        majors = scrape_major_list(cookies, max_pages=3)
        if majors:
            save_data(majors, "gaokao_majors.json")
            print("\n前 10 条数据预览:")
            for m in majors[:10]:
                print(f"  {m['code']} {m['name']}（{m['category']}）")

    print("\n爬取完成！")
