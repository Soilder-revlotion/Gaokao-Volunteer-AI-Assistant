"""
第一步：打开浏览器，手动登录，保存 Cookie
用途：首次使用时运行，登录目标网站，保存 Cookie 供后续自动爬取使用
每年更新数据时，如果 Cookie 过期，重新运行此脚本即可
"""

import json
import os
import sys
from datetime import datetime

# 项目路径
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
COOKIE_DIR = os.path.join(BASE_DIR, "cookies")

def login_and_save_cookies(site_name, login_url):
    """
    打开浏览器让用户手动登录，登录完成后保存 Cookie

    参数:
        site_name: 网站名称（如 "gaokao"），用于 Cookie 文件命名
        login_url: 登录页面的 URL
    """
    from playwright.sync_api import sync_playwright

    cookie_path = os.path.join(COOKIE_DIR, f"{site_name}_cookies.json")

    print(f"=" * 50)
    print(f"正在打开: {login_url}")
    print(f"请在浏览器中手动登录")
    print(f"登录完成后，回到这里按回车键保存 Cookie")
    print(f"=" * 50)

    with sync_playwright() as p:
        # 启动浏览器（有头模式，方便手动操作）
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 打开登录页面
        page.goto(login_url)

        # 等待用户手动登录
        input("\n登录完成后，按回车键保存 Cookie...")

        # 保存 Cookie
        cookies = context.cookies()
        os.makedirs(COOKIE_DIR, exist_ok=True)
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\nCookie 已保存到: {cookie_path}")
        print(f"Cookie 数量: {len(cookies)}")
        print(f"保存时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        browser.close()

    return cookie_path


def check_cookies(site_name):
    """检查 Cookie 是否存在且未过期"""
    cookie_path = os.path.join(COOKIE_DIR, f"{site_name}_cookies.json")

    if not os.path.exists(cookie_path):
        print(f"未找到 {site_name} 的 Cookie，请先运行登录")
        return False

    with open(cookie_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    # 检查是否有过期的 Cookie
    now = datetime.now().timestamp()
    expired = [c for c in cookies if c.get("expires", 0) > 0 and c["expires"] < now]

    if len(expired) == len(cookies):
        print(f"{site_name} 的 Cookie 已全部过期，请重新登录")
        return False

    print(f"{site_name} 的 Cookie 有效（{len(cookies) - len(expired)}/{len(cookies)} 未过期）")
    return True


# ============================================================
# 配置你要登录的网站
# ============================================================
SITES = {
    "gaokao": {
        "name": "阳光高考",
        "login_url": "https://account.chsi.com.cn/passport/login",
        "note": "教育部官方平台，最权威的高考数据"
    },
    "eol": {
        "name": "中国教育在线",
        "login_url": "https://gkcx.eol.cn",
        "note": "高校信息库，专业介绍"
    },
    "zjzw": {
        "name": "掌上高考",
        "login_url": "https://www.gaokao.cn",
        "note": "综合高考数据平台"
    }
}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 指定网站登录
        site = sys.argv[1]
        if site in SITES:
            login_and_save_cookies(site, SITES[site]["login_url"])
        else:
            print(f"未知网站: {site}")
            print(f"可选: {', '.join(SITES.keys())}")
    else:
        # 显示所有可登录的网站
        print("可登录的网站：")
        for key, info in SITES.items():
            print(f"  {key}: {info['name']} - {info['note']}")
        print(f"\n用法: python {__file__} <网站名>")
        print(f"示例: python {__file__} gaokao")
