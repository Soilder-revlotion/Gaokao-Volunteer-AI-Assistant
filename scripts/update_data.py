"""
年度数据更新流程（一键运行）
每年高考后运行一次，更新数据并重建知识库

流程：
1. 检查 Cookie 是否有效
2. 爬取最新数据
3. 重建 RAG 知识库
4. 测试效果
"""

import os
import sys
import subprocess

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS_DIR = os.path.dirname(__file__)


def run_script(script_name):
    """运行指定脚本"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    print(f"\n{'='*50}")
    print(f"运行: {script_name}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=BASE_DIR
    )
    return result.returncode == 0


def main():
    print("=" * 50)
    print("高考志愿 AI 助手 — 年度数据更新")
    print("=" * 50)

    # 第一步：检查 Cookie
    print("\n[步骤 1] 检查登录状态...")
    from scripts.login_save_cookies import check_cookies

    sites_ok = True
    for site in ["gaokao", "eol"]:
        if not check_cookies(site):
            sites_ok = False

    if not sites_ok:
        print("\n部分网站 Cookie 已过期，需要重新登录")
        print("运行: python scripts/01_login_save_cookies.py gaokao")
        print("运行: python scripts/01_login_save_cookies.py eol")
        print("\n是否跳过爬取，直接使用现有数据？(y/n)")
        choice = input().strip().lower()
        if choice != "y":
            return

    # 第二步：爬取数据
    print("\n[步骤 2] 爬取最新数据...")
    run_script("02_scrape_data.py")

    # 第三步：重建 RAG
    print("\n[步骤 3] 重建 RAG 知识库...")
    run_script("03_build_rag.py")

    # 完成
    print("\n" + "=" * 50)
    print("数据更新完成！")
    print("=" * 50)
    print("\n下一步：")
    print("  测试效果: python scripts/04_query.py")
    print("  启动网页: python scripts/05_web.py")


if __name__ == "__main__":
    main()
