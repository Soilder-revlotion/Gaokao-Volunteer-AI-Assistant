"""
把爬取的数据转换成问答格式，供 RAG 使用

功能：
1. 软科排名数据 → 问答格式
2. 阳光高考院校数据 → 问答格式
3. 上海高考投档数据 → 问答格式
4. 合并所有数据到一个文件
"""

import json
import os

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_json(filename):
    """加载 JSON 文件"""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f"  文件不存在: {filename}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  加载 {filename}: {len(data)} 条")
    return data


def convert_shanghairanking(data):
    """软科排名数据 → 问答格式"""
    qa_list = []
    for item in data:
        name = item.get("name", "")
        rank = item.get("rank", "")
        province = item.get("province", "")
        score = item.get("score", "")

        if not name:
            continue

        # 问答1：排名
        qa_list.append({
            "question": f"{name}在2025年软科排名中排第几？",
            "answer": f"{name}在2025年软科中国大学排名中位列第{rank}名，位于{province}。"
        })

        # 问答2：基本信息
        qa_list.append({
            "question": f"{name}是什么档次的大学？",
            "answer": f"{name}位于{province}，在2025年软科中国大学排名中位列第{rank}名。{'总分' + score if score else ''}"
        })

    return qa_list


def convert_gaokao_schools(data):
    """阳光高考院校数据 → 问答格式"""
    qa_list = []
    for item in data:
        name = item.get("name", "")
        address = item.get("address", "")
        tags = item.get("tags", [])

        if not name:
            continue

        tag_str = "、".join(tags) if tags else "普通本科"

        # 问答：院校基本信息
        qa_list.append({
            "question": f"{name}是985还是211？",
            "answer": f"{name}位于{address}，是{tag_str}高校。"
        })

        # 问答：院校位置
        qa_list.append({
            "question": f"{name}在哪里？",
            "answer": f"{name}位于{address}。"
        })

    return qa_list


def convert_shanghai_gaokao(data):
    """上海高考投档数据 → 问答格式"""
    qa_list = []
    for item in data:
        school = item.get("院校名", "")
        year = item.get("年份", "")
        score = item.get("投档线", "")
        rank = item.get("最低排名", "")

        if not school or not year:
            continue

        # 问答：投档线
        if score and score != "null":
            qa_list.append({
                "question": f"{year}年{school}在上海的投档线是多少？",
                "answer": f"{year}年{school}在上海的投档线为{score}，最低排名{rank}名。"
            })

    return qa_list


def convert_manual_data(data):
    """手动整理的数据已经是问答格式，直接返回"""
    return [item for item in data if item.get("question") and item.get("answer")]


def save_qa_data(qa_list, filename="gaokao_qa_all.json"):
    """保存问答数据"""
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(qa_list, f, ensure_ascii=False, indent=2)
    print(f"\n问答数据已保存到: {filepath}（{len(qa_list)} 条）")
    return filepath


if __name__ == "__main__":
    print("=" * 50)
    print("数据转换工具：爬取数据 → 问答格式")
    print("=" * 50)

    all_qa = []

    # 1. 软科排名
    print("\n[1/4] 处理软科排名数据...")
    shanghairanking = load_json("shanghairanking_2025.json")
    if shanghairanking:
        qa = convert_shanghairanking(shanghairanking)
        all_qa.extend(qa)
        print(f"  转换: {len(qa)} 条问答")

    # 2. 阳光高考院校
    print("\n[2/4] 处理阳光高考院校数据...")
    gaokao_schools = load_json("gaokao_schools.json")
    if gaokao_schools:
        qa = convert_gaokao_schools(gaokao_schools)
        all_qa.extend(qa)
        print(f"  转换: {len(qa)} 条问答")

    # 3. 上海高考投档数据
    print("\n[3/4] 处理上海高考投档数据...")
    shanghai_gaokao = load_json("shanghai_gaokao.json")
    if shanghai_gaokao:
        qa = convert_shanghai_gaokao(shanghai_gaokao)
        all_qa.extend(qa)
        print(f"  转换: {len(qa)} 条问答")

    # 4. 手动整理的数据
    print("\n[4/4] 处理手动整理的数据...")
    manual = load_json("manual_schools.json")
    if manual:
        qa = convert_manual_data(manual)
        all_qa.extend(qa)
        print(f"  转换: {len(qa)} 条问答")

    # 保存
    if all_qa:
        save_qa_data(all_qa)
        print(f"\n总计: {len(all_qa)} 条问答数据")
        print("\n前 5 条预览:")
        for item in all_qa[:5]:
            print(f"  Q: {item['question']}")
            print(f"  A: {item['answer'][:50]}...")
            print()
    else:
        print("\n没有数据可转换，请先运行爬虫")
