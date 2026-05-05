"""
第四步：查询测试
在命令行中与 AI 助手对话
支持两种查询方式：直接查询（排名、省份等）+ 向量检索
"""

import json
import os
import re
import requests
import numpy as np

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, DB_PATH, MODEL_LOCAL_PATH, DATA_DIR

print("正在加载依赖...")
from sentence_transformers import SentenceTransformer
import faiss

print("正在加载 Embedding 模型...")
if os.path.exists(MODEL_LOCAL_PATH):
    embedding_model = SentenceTransformer(MODEL_LOCAL_PATH)
else:
    embedding_model = SentenceTransformer("damo/nlp_gte_sentence-embedding_chinese-base")

print("正在加载向量索引...")
index = faiss.read_index(os.path.join(DB_PATH, "gaokao.index"))
with open(os.path.join(DB_PATH, "gaokao_data.json"), "r", encoding="utf-8") as f:
    qa_data = json.load(f)

# 加载结构化数据（用于直接查询）
print("正在加载院校数据...")
school_data = []
for filename in ["shanghairanking_cleaned.json"]:
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            school_data = json.load(f)
        print(f"  加载 {filename}: {len(school_data)} 所院校")

print(f"就绪，知识库共 {len(qa_data)} 条问答\n")


def direct_query(question):
    """
    直接查询：处理排名、省份、标签等结构化查询
    返回补充上下文字符串，如果无法处理返回 None
    """
    results = []

    # 查询：排名前N
    match = re.search(r'排名前\s*(\d+)', question)
    if match:
        n = int(match.group(1))
        top_schools = sorted(school_data, key=lambda x: x.get("rank", "9999"))[:n]
        lines = []
        for s in top_schools:
            rank = s.get("rank", "?")
            name = s.get("name", "")
            province = s.get("province", "")
            tags = "、".join(s.get("tags", []))
            lines.append(f"{rank}. {name}（{province}，{tags}）")
        results.append("软科排名前{}的大学：\n{}".format(n, "\n".join(lines)))

    # 查询：XX省的大学
    province_match = re.search(r'([一-龥]{2,4}(?:省|市|自治区))?的大学', question)
    if not province_match:
        province_match = re.search(r'([一-龥]{2,4})有哪些大学', question)
    if province_match:
        province = province_match.group(1)
        if province:
            province = province.replace("省", "").replace("市", "").replace("自治区", "")
            matched = [s for s in school_data if province in s.get("province", "")]
            if matched:
                lines = [f"{s['name']}（{s.get('province', '')}，排名{s.get('rank', '?')}）" for s in matched[:20]]
                results.append(f"{province}的大学（前20所）：\n" + "\n".join(lines))

    # 查询：985/211/双一流大学
    for tag in ["985", "211", "双一流"]:
        if tag in question:
            matched = [s for s in school_data if tag in "、".join(s.get("tags", []))]
            if matched:
                lines = [f"{s['name']}（{s.get('province', '')}，排名{s.get('rank', '?')}）" for s in matched[:20]]
                results.append(f"{tag}大学（前20所）：\n" + "\n".join(lines))
            break

    # 查询：XX大学排名多少
    rank_match = re.search(r'([一-龥]+大学)排名', question)
    if not rank_match:
        rank_match = re.search(r'([一-龥]+(?:大学|学院))', question)
    if rank_match:
        school_name = rank_match.group(1)
        for s in school_data:
            if s.get("name") == school_name:
                rank = s.get("rank", "?")
                province = s.get("province", "")
                tags = "、".join(s.get("tags", []))
                school_type = s.get("type", "")
                results.append(f"{school_name}在2025年软科排名中位列第{rank}名，位于{province}，属于{tags}高校，类型为{school_type}。")
                break

    return "\n\n".join(results) if results else None


def vector_search(question, n_results=5):
    """向量检索，返回相关问答"""
    query_embedding = embedding_model.encode([question]).astype("float32")
    distances, indices = index.search(query_embedding, n_results)

    context_parts = []
    for idx in indices[0]:
        if 0 <= idx < len(qa_data):
            context_parts.append(f"- {qa_data[idx]['answer']}")
    return "\n".join(context_parts)


def ask(question):
    """向 AI 提问：先直接查询，再向量检索，合并结果"""
    # 1. 直接查询
    direct_result = direct_query(question)

    # 2. 向量检索
    vector_result = vector_search(question)

    # 3. 合并上下文
    context_parts = []
    if direct_result:
        context_parts.append(f"【精确匹配】\n{direct_result}")
    context_parts.append(f"【相关问答】\n{vector_result}")
    context = "\n\n".join(context_parts)

    # 4. 调用 Ollama
    prompt = f"""你是高考志愿填报专家。请根据参考资料直接回答考生问题，要求：
1. 优先引用参考资料中的具体数据
2. 回答要详细、有条理
3. 如果有多条相关数据，综合分析
4. 不要说"无法提供"或"没有相关信息"，尽力从资料中找到答案

参考资料：
{context}

问题：{question}

详细回答："""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=OLLAMA_TIMEOUT)

        if response.status_code == 200:
            return response.json()["response"]
        else:
            return f"错误：Ollama 返回状态码 {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "错误：无法连接到 Ollama，请确保 Ollama 正在运行（ollama serve）"
    except Exception as e:
        return f"错误：{e}"


if __name__ == "__main__":
    import sys

    # 支持命令行参数直接提问
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"\n问题：{question}")
        print("\n正在思考...")
        answer = ask(question)
        print(f"\nAI 回答：\n{answer}")
    else:
        print("=" * 50)
        print("高考志愿 AI 助手（输入 quit 退出）")
        print("=" * 50)

        while True:
            question = input("\n请输入问题: ").strip()
            if question.lower() == "quit":
                break
            if not question:
                continue

            print("\n正在思考...")
            answer = ask(question)
            print(f"\nAI 回答：\n{answer}")
