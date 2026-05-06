"""
全自动数据扩展 + 索引重建管道
运行方式: py scripts\run_full_pipeline.py
预计耗时: 4-8 小时（取决于待爬取学校数量）
支持断点续爬，可随时 Ctrl+C 中断，下次运行自动继续
"""

import json
import os
import sys
import time
import random
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def step1_add_policy_qa():
    """步骤1：合并政策问答数据"""
    log("=" * 60)
    log("步骤 1/4：合并政策问答数据")
    log("=" * 60)

    policy_path = os.path.join(DATA_DIR, "gaokao_policy_qa.json")
    if not os.path.exists(policy_path):
        log("  政策问答文件不存在，跳过")
        return

    with open(policy_path, "r", encoding="utf-8") as f:
        policy_qa = json.load(f)

    log(f"  政策问答: {len(policy_qa)} 条")

    # 合并到 gaokao_qa_all.json
    qa_path = os.path.join(DATA_DIR, "gaokao_qa_all.json")
    if os.path.exists(qa_path):
        with open(qa_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    # 去重（按 question 去重）
    existing_questions = set(item.get("question", "") for item in existing)
    new_count = 0
    for item in policy_qa:
        if item["question"] not in existing_questions:
            existing.append(item)
            existing_questions.add(item["question"])
            new_count += 1

    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    log(f"  新增 {new_count} 条，总计 {len(existing)} 条问答")


def step2_scrape_scores():
    """步骤2：爬取剩余大学的录取分数线"""
    log("=" * 60)
    log("步骤 2/4：爬取录取分数线")
    log("=" * 60)

    # 加载已有数据
    scores_path = os.path.join(DATA_DIR, "eol_scores.json")
    if os.path.exists(scores_path):
        with open(scores_path, "r", encoding="utf-8") as f:
            all_scores = json.load(f)
        scraped_ids = set(s["school_id"] for s in all_scores)
        log(f"  已有数据: {len(all_scores)} 条, {len(scraped_ids)} 所大学")
    else:
        all_scores = []
        scraped_ids = set()

    # 加载学校名单
    ranking_path = os.path.join(DATA_DIR, "shanghairanking_cleaned.json")
    with open(ranking_path, "r", encoding="utf-8") as f:
        schools = json.load(f)

    id_map_path = os.path.join(DATA_DIR, "eol_school_ids.json")
    with open(id_map_path, "r", encoding="utf-8") as f:
        id_map = json.load(f)

    # 匹配待爬取学校
    school_list = []
    for s in schools:
        name = s["name"]
        sid = id_map.get(name)
        if not sid:
            for k, v in id_map.items():
                if name in k or k in name:
                    sid = v
                    break
        if sid and sid not in scraped_ids:
            school_list.append((name, sid))

    log(f"  待爬取: {len(school_list)} 所大学")

    if not school_list:
        log("  所有学校已爬取完毕！")
        return

    # 启动 Playwright
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

    def scrape_school(page, school_id, school_name):
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

            initial = parse_score_responses(score_responses, school_name, school_id)
            school_scores.extend(initial)
            score_responses.clear()

            province_count = page.locator("[class*='province-switch_item']").count()
            for idx in range(1, min(province_count, 31)):
                try:
                    score_responses.clear()
                    page.locator("[class*='province-switch_item']").nth(idx).dispatch_event("click")
                    time.sleep(1.0)
                    new_scores = parse_score_responses(score_responses, school_name, school_id)
                    school_scores.extend(new_scores)
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

        total = len(school_list)
        log(f"  开始爬取 {total} 所大学...")

        for i, (name, sid) in enumerate(school_list):
            log(f"  [{i+1}/{total}] {name} (id={sid})")
            try:
                scores = scrape_school(page, sid, name)
                all_scores.extend(scores)
                log(f"    获取 {len(scores)} 条数据")

                # 每所学校保存一次
                with open(scores_path, "w", encoding="utf-8") as f:
                    json.dump(all_scores, f, ensure_ascii=False, indent=2)

                # 学校间延迟
                delay = random.uniform(2, 4)
                time.sleep(delay)

                # 每 20 所休息一下
                if (i + 1) % 20 == 0 and i + 1 < total:
                    rest = random.uniform(30, 60)
                    log(f"  已完成 {i+1}/{total}，休息 {rest:.0f} 秒...")
                    time.sleep(rest)

                # 每 50 所报告进度
                if (i + 1) % 50 == 0:
                    scraped_now = len(set(s["school_id"] for s in all_scores))
                    log(f"  === 进度: {i+1}/{total} 所完成, 共 {len(all_scores)} 条数据, 覆盖 {scraped_now} 所大学 ===")

            except Exception as e:
                log(f"    异常: {e}")
                # 保存已爬数据
                with open(scores_path, "w", encoding="utf-8") as f:
                    json.dump(all_scores, f, ensure_ascii=False, indent=2)
                continue

        browser.close()

    # 最终保存
    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(all_scores, f, ensure_ascii=False, indent=2)

    scraped_total = len(set(s["school_id"] for s in all_scores))
    log(f"  爬取完成: {len(all_scores)} 条数据, 覆盖 {scraped_total} 所大学")


def step3_clean_and_merge():
    """步骤3：数据清洗 + 合并"""
    log("=" * 60)
    log("步骤 3/4：数据清洗与合并")
    log("=" * 60)

    qa_all = []

    # 1. 软科排名 → QA
    ranking_path = os.path.join(DATA_DIR, "shanghairanking_cleaned.json")
    if os.path.exists(ranking_path):
        with open(ranking_path, "r", encoding="utf-8") as f:
            schools = json.load(f)
        for s in schools:
            name = s.get("name", "")
            rank = s.get("rank", "")
            province = s.get("province", "")
            tags = "、".join(s.get("tags", [])) or "普通本科"
            school_type = s.get("type", "")
            if not name:
                continue
            qa_all.append({"question": f"{name}在2025年软科排名中排第几？", "answer": f"{name}在2025年软科中国大学排名中位列第{rank}名，位于{province}，属于{tags}高校。"})
            if "985" in tags:
                qa_all.append({"question": f"{name}是985大学吗？", "answer": f"是的，{name}是985大学，同时也是{tags}高校，位于{province}。"})
            elif "211" in tags:
                qa_all.append({"question": f"{name}是985大学吗？", "answer": f"{name}不是985大学，但是211大学，属于{tags}高校，位于{province}。"})
            if school_type:
                qa_all.append({"question": f"{name}是什么类型的大学？", "answer": f"{name}是一所{school_type}类大学，位于{province}，属于{tags}高校，2025年软科排名第{rank}名。"})
            qa_all.append({"question": f"{name}在哪个城市？", "answer": f"{name}位于{province}。"})
        log(f"  软科排名: {len(schools)} 所大学 → {len(qa_all)} 条问答")

    # 2. 录取分数线 → QA
    scores_path = os.path.join(DATA_DIR, "eol_scores.json")
    if os.path.exists(scores_path):
        with open(scores_path, "r", encoding="utf-8") as f:
            scores = json.load(f)
        score_qa_count = 0
        for item in scores:
            school = item.get("school", "")
            year = item.get("year", "")
            province = item.get("province", "")
            category = item.get("category", "")
            min_score = item.get("min_score", "")
            min_rank = item.get("min_rank", "")
            avg_score = item.get("avg_score", "")
            if not school or not min_score:
                continue
            answer_parts = [f"{year}年{school}在{province}{category}的最低录取分数线为{min_score}分"]
            if min_rank:
                answer_parts.append(f"最低位次{min_rank}名")
            if avg_score:
                answer_parts.append(f"平均分{avg_score}分")
            answer = "，".join(answer_parts) + "。"
            qa_all.append({"question": f"{year}年{school}在{province}{category}的录取分数线是多少？", "answer": answer})
            qa_all.append({"question": f"{school}{year}年录取分数线是多少？", "answer": f"{year}年{school}在{province}{category}的最低录取分数线为{min_score}分。"})
            score_qa_count += 1
        log(f"  录取分数线: {len(scores)} 条 → {score_qa_count * 2} 条问答")

    # 3. 专业排名 → QA
    subject_path = os.path.join(DATA_DIR, "shanghai_subject_ranking.json")
    if os.path.exists(subject_path):
        with open(subject_path, "r", encoding="utf-8") as f:
            subjects = json.load(f)
        for item in subjects:
            university = item.get("university", "")
            subject = item.get("subject", "")
            ranking = item.get("ranking", "")
            score = item.get("score", "")
            category = item.get("category", "")
            year = item.get("year", "")
            if not university or not subject:
                continue
            qa_all.append({"question": f"{university}{subject}专业排名怎么样？", "answer": f"在{year}年软科中国最好学科排名中，{university}的{subject}学科位列全国第{ranking}名，得分{score}分，属于{category}门类。"})
        log(f"  专业排名: {len(subjects)} 条问答")

    # 4. 就业数据 → QA
    emp_path = os.path.join(DATA_DIR, "employment_data.json")
    if os.path.exists(emp_path):
        with open(emp_path, "r", encoding="utf-8") as f:
            emp_data = json.load(f)
        emp_qa_count = 0
        for item in emp_data:
            school = item.get("school", "")
            year = item.get("year", "")
            emp_rate = item.get("employment_rate", "")
            pg_rate = item.get("postgraduate_rate", "")
            ab_rate = item.get("abroad_rate", "")
            if not school:
                continue
            if emp_rate:
                qa_all.append({"question": f"{school}的就业率怎么样？", "answer": f"{school}{year}年毕业生就业率为{emp_rate}%，考研率为{pg_rate}%，出国率为{ab_rate}%。"})
                emp_qa_count += 1
            if pg_rate and float(str(pg_rate).replace("-", "0")) > 20:
                qa_all.append({"question": f"{school}考研率高吗？", "answer": f"{school}{year}年考研率为{pg_rate}%，就业率为{emp_rate}%。"})
            provinces = item.get("province_distribution", [])
            if provinces and len(provinces) >= 2:
                top = provinces[:3]
                prov_str = "、".join([f"{p['name']}({p['rate']}%)" for p in top if p.get("name")])
                if prov_str:
                    qa_all.append({"question": f"{school}毕业生去哪里工作？", "answer": f"{school}毕业生主要就业地区：{prov_str}。"})
        log(f"  就业数据: {len(emp_data)} 所大学 → ~{emp_qa_count * 2} 条问答")

    # 5. 手动数据
    manual_path = os.path.join(DATA_DIR, "manual_schools.json")
    if os.path.exists(manual_path):
        with open(manual_path, "r", encoding="utf-8") as f:
            manual = json.load(f)
        qa_all.extend(manual)
        log(f"  手动数据: {len(manual)} 条")

    # 6. 政策问答
    policy_path = os.path.join(DATA_DIR, "gaokao_policy_qa.json")
    if os.path.exists(policy_path):
        with open(policy_path, "r", encoding="utf-8") as f:
            policy = json.load(f)
        qa_all.extend(policy)
        log(f"  政策问答: {len(policy)} 条")

    # 保存合并后的 QA 数据
    output_path = os.path.join(DATA_DIR, "gaokao_qa_all.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(qa_all, f, ensure_ascii=False, indent=2)

    log(f"  合并完成: 共 {len(qa_all)} 条问答数据")
    return len(qa_all)


def step4_build_rag():
    """步骤4：重建 FAISS 向量索引"""
    log("=" * 60)
    log("步骤 4/4：重建 FAISS 向量索引")
    log("=" * 60)

    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, "scripts", "03_build_rag.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode == 0:
        log("  RAG 索引重建成功")
        # 输出关键信息
        for line in result.stdout.split("\n"):
            if "条" in line or "完成" in line or "保存" in line:
                log(f"  {line.strip()}")
    else:
        log(f"  RAG 索引重建失败: {result.stderr[:200]}")


def main():
    log("=" * 60)
    log("高考志愿 AI 助手 — 全自动数据扩展管道")
    log(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    start_time = time.time()

    try:
        step1_add_policy_qa()
        step2_scrape_scores()
        total_qa = step3_clean_and_merge()
        step4_build_rag()

        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)

        log("")
        log("=" * 60)
        log("全部完成！")
        log(f"  耗时: {hours} 小时 {minutes} 分钟")
        log(f"  问答总数: {total_qa}")
        log(f"  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log("=" * 60)

    except KeyboardInterrupt:
        log("\n用户中断，已保存已爬取数据。下次运行自动继续。")
    except Exception as e:
        log(f"\n管道出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
