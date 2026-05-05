"""
数据清洗脚本
处理爬取的原始数据，提取有用信息
"""

import json
import os
import re

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")


def validate_data(data, data_name):
    """
    自动检查数据质量
    返回: (is_valid, issues)
    """
    issues = []

    if not data:
        issues.append(f"[严重] {data_name}: 数据为空")
        return False, issues

    # 检查必要字段
    for i, item in enumerate(data):
        if not item.get("name") and not item.get("question"):
            issues.append(f"[严重] 第 {i+1} 条: 缺少 name 或 question 字段")
            if len(issues) > 5:
                issues.append(f"... 还有更多问题，已省略")
                break

    # 检查重复
    names = [item.get("name", "") for item in data if item.get("name")]
    if names:
        unique_names = set(names)
        if len(unique_names) < len(names) * 0.8:
            issues.append(f"[警告] {data_name}: 存在大量重复数据 ({len(names)} 条, {len(unique_names)} 个唯一)")

    # 检查数据量
    if len(data) < 10:
        issues.append(f"[警告] {data_name}: 数据量过少 ({len(data)} 条)")

    is_valid = len([i for i in issues if "[严重]" in i]) == 0
    return is_valid, issues


def clean_shanghairanking():
    """清洗软科排名数据"""
    filepath = os.path.join(DATA_DIR, "shanghairanking_2025.json")

    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # 检查原始数据
    print(f"\n  原始数据检查:")
    print(f"    条数: {len(raw_data)}")
    if raw_data:
        sample = raw_data[0]
        print(f"    字段: {list(sample.keys())}")
        print(f"    示例 name: {repr(sample.get('name', '')[:50])}")

    cleaned = []
    for item in raw_data:
        name_raw = item.get("name", "")

        # 解析 name 字段：中文名\n英文名\n\n标签
        lines = [l.strip() for l in name_raw.split("\n") if l.strip()]

        chinese_name = lines[0] if lines else ""
        english_name = lines[1] if len(lines) > 1 else ""
        tags_str = lines[2] if len(lines) > 2 else ""

        # 提取标签列表
        tags = [t.strip() for t in tags_str.split("/") if t.strip()]

        # 清洗省份
        province = item.get("province", "").strip()

        # 清洗类型
        school_type = item.get("score", "").strip()

        if chinese_name:
            cleaned.append({
                "rank": item.get("rank", ""),
                "name": chinese_name,
                "english_name": english_name,
                "province": province,
                "tags": tags,
                "type": school_type,
                "year": item.get("year", 2025),
                "source": "软科排名"
            })

    # 保存清洗后的数据
    output_path = os.path.join(DATA_DIR, "shanghairanking_cleaned.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"软科排名数据清洗完成:")
    print(f"  原始: {len(raw_data)} 条")
    print(f"  清洗后: {len(cleaned)} 条")
    print(f"  保存到: {output_path}")

    return cleaned


def convert_to_qa(data, source_name):
    """把清洗后的数据转成问答格式"""
    qa_list = []

    for item in data:
        name = item.get("name", "")
        rank = item.get("rank", "")
        province = item.get("province", "")
        tags = item.get("tags", [])
        school_type = item.get("type", "")

        if not name:
            continue

        tag_str = "、".join(tags) if tags else "普通本科"

        # 问答1：排名
        qa_list.append({
            "question": f"{name}在2025年软科排名中排第几？",
            "answer": f"{name}在2025年软科中国大学排名中位列第{rank}名，位于{province}，属于{tag_str}高校。"
        })

        # 问答2：是985还是211
        if "985" in tag_str:
            qa_list.append({
                "question": f"{name}是985大学吗？",
                "answer": f"是的，{name}是985大学，同时也是{tag_str}高校，位于{province}。"
            })
        elif "211" in tag_str:
            qa_list.append({
                "question": f"{name}是985大学吗？",
                "answer": f"{name}不是985大学，但是211大学，属于{tag_str}高校，位于{province}。"
            })

        # 问答3：院校类型
        if school_type:
            qa_list.append({
                "question": f"{name}是什么类型的大学？",
                "answer": f"{name}是一所{school_type}类大学，位于{province}，属于{tag_str}高校，2025年软科排名第{rank}名。"
            })

        # 问答4：所在地
        qa_list.append({
            "question": f"{name}在哪个城市？",
            "answer": f"{name}位于{province}。"
        })

    return qa_list


def convert_eol_scores(data):
    """把录取分数线数据转成问答格式"""
    qa_list = []

    for item in data:
        school = item.get("school", "")
        year = item.get("year", "")
        province = item.get("province", "")
        category = item.get("category", "")
        min_score = item.get("min_score", "")
        min_rank = item.get("min_rank", "")
        avg_score = item.get("avg_score", "")

        if not school:
            continue

        # 构建问答
        parts = []
        if year:
            parts.append(f"{year}年")
        if province:
            parts.append(f"{province}")
        if category:
            parts.append(f"{category}")

        location = "".join(parts)

        if min_score:
            answer_parts = [f"{year}年{school}在{province}{category}的最低录取分数线为{min_score}分"]
            if min_rank:
                answer_parts.append(f"最低位次{min_rank}名")
            if avg_score:
                answer_parts.append(f"平均分{avg_score}分")
            answer = "，".join(answer_parts) + "。"

            qa_list.append({
                "question": f"{year}年{school}在{province}{category}的录取分数线是多少？",
                "answer": answer
            })

        # 只有学校+年份的通用问答
        if min_score and year:
            qa_list.append({
                "question": f"{school}{year}年录取分数线是多少？",
                "answer": f"{year}年{school}在{province}{category}的最低录取分数线为{min_score}分。"
            })

    return qa_list


def convert_employment_data(data):
    """把就业数据转成问答格式"""
    qa_list = []

    for item in data:
        school = item.get("school", "")
        year = item.get("year", "")
        emp_rate = item.get("employment_rate", "")
        pg_rate = item.get("postgraduate_rate", "")
        ab_rate = item.get("abroad_rate", "")

        if not school:
            continue

        # 问答1：就业率
        if emp_rate:
            qa_list.append({
                "question": f"{school}的就业率怎么样？",
                "answer": f"{school}{year}年毕业生就业率为{emp_rate}%，考研率为{pg_rate}%，出国率为{ab_rate}%。"
            })

        # 问答2：考研率
        if pg_rate and float(str(pg_rate).replace("-", "0")) > 20:
            qa_list.append({
                "question": f"{school}考研率高吗？",
                "answer": f"{school}{year}年考研率为{pg_rate}%，就业率为{emp_rate}%。"
            })

        # 问答3：就业地区分布
        provinces = item.get("province_distribution", [])
        if provinces and len(provinces) >= 2:
            top_provinces = provinces[:3]
            prov_str = "、".join([f"{p['name']}({p['rate']}%)" for p in top_provinces if p['name']])
            if prov_str:
                qa_list.append({
                    "question": f"{school}毕业生去哪里工作？",
                    "answer": f"{school}毕业生主要就业地区：{prov_str}。"
                })

    return qa_list


def convert_subject_rankings(data):
    """把专业排名数据转成问答格式"""
    qa_list = []

    for item in data:
        university = item.get("university", "")
        subject = item.get("subject", "")
        ranking = item.get("ranking", "")
        score = item.get("score", "")
        category = item.get("category", "")
        year = item.get("year", "")

        if not university or not subject:
            continue

        # 问答1：某大学某学科排名
        qa_list.append({
            "question": f"{university}{subject}专业排名怎么样？",
            "answer": f"在{year}年软科中国最好学科排名中，{university}的{subject}学科位列全国第{ranking}名，得分{score}分，属于{category}门类。"
        })

        # 问答2：某学科哪些大学好
        # (这个由向量检索自然处理，不需要单独生成)

    return qa_list


if __name__ == "__main__":
    print("=" * 50)
    print("数据清洗工具（含自动检查）")
    print("=" * 50)

    # 清洗软科排名
    print("\n[1/4] 清洗软科排名数据...")
    cleaned = clean_shanghairanking()

    if cleaned:
        # 自动检查清洗后数据
        print(f"\n  清洗后数据检查:")
        is_valid, issues = validate_data(cleaned, "软科排名")
        for issue in issues:
            print(f"    {issue}")
        if is_valid:
            print(f"    [通过] 数据质量检查通过")
        else:
            print(f"    [失败] 数据存在问题，请检查")

        # 转成问答格式
        print("\n转换成问答格式...")
        qa_data = convert_to_qa(cleaned, "软科排名")

        # 合并手动数据
        manual_path = os.path.join(DATA_DIR, "manual_schools.json")
        if os.path.exists(manual_path):
            with open(manual_path, "r", encoding="utf-8") as f:
                manual = json.load(f)
            qa_data.extend(manual)
            print(f"  合并手动数据: {len(manual)} 条")

        # 合并录取分数线数据
        print("\n[2/4] 处理录取分数线数据...")
        eol_path = os.path.join(DATA_DIR, "eol_scores.json")
        if os.path.exists(eol_path):
            with open(eol_path, "r", encoding="utf-8") as f:
                eol_data = json.load(f)
            eol_qa = convert_eol_scores(eol_data)
            qa_data.extend(eol_qa)
            print(f"  录取分数线: {len(eol_qa)} 条问答")
        else:
            print(f"  跳过录取分数线（文件不存在: {eol_path}）")

        # 合并专业排名数据
        print("\n[3/4] 处理专业排名数据...")
        subj_path = os.path.join(DATA_DIR, "shanghai_subject_ranking.json")
        if os.path.exists(subj_path):
            with open(subj_path, "r", encoding="utf-8") as f:
                subj_data = json.load(f)
            subj_qa = convert_subject_rankings(subj_data)
            qa_data.extend(subj_qa)
            print(f"  专业排名: {len(subj_qa)} 条问答")
        else:
            print(f"  跳过专业排名（文件不存在: {subj_path}）")

        # 合并就业数据
        print("\n[4/4] 处理就业数据...")
        emp_path = os.path.join(DATA_DIR, "employment_data.json")
        if os.path.exists(emp_path):
            with open(emp_path, "r", encoding="utf-8") as f:
                emp_data = json.load(f)
            emp_qa = convert_employment_data(emp_data)
            qa_data.extend(emp_qa)
            print(f"  就业数据: {len(emp_qa)} 条问答")
        else:
            print(f"  跳过就业数据（文件不存在: {emp_path}）")

        # 检查问答数据
        print(f"\n  问答数据检查:")
        qa_valid, qa_issues = validate_data(qa_data, "问答数据")
        for issue in qa_issues:
            print(f"    {issue}")
        if qa_valid:
            print(f"    [通过] 问答数据质量检查通过")

        # 保存
        output_path = os.path.join(DATA_DIR, "gaokao_qa_all.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(qa_data, f, ensure_ascii=False, indent=2)

        print(f"\n问答数据已保存: {output_path}（{len(qa_data)} 条）")

        # 预览
        print("\n前 5 条预览:")
        for item in qa_data[:5]:
            print(f"  Q: {item['question']}")
            print(f"  A: {item['answer'][:60]}...")
            print()

        # 最终状态
        print("=" * 50)
        if is_valid and qa_valid and len(qa_data) >= 50:
            print("[成功] 数据质量OK，可以运行 03_build_rag.py")
        elif len(qa_data) < 50:
            print(f"[警告] 数据量偏少 ({len(qa_data)} 条)，建议增加更多数据")
            print("  下一步: python scripts\\03_build_rag.py")
        else:
            print("[警告] 数据存在问题，建议检查后重试")

    print("\n清洗完成！下一步运行: python scripts\\03_build_rag.py")
