"""
第五步：网页版后端
启动后访问 http://localhost:5000
"""

import json
import os
import re
import requests
import numpy as np
from flask import Flask, request, jsonify, render_template

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, DB_PATH, MODEL_LOCAL_PATH, DATA_DIR, BASE_DIR

TEMPLATE_PATH = os.path.join(BASE_DIR, "templates")

print("正在加载依赖...")
from sentence_transformers import SentenceTransformer
import faiss

print("正在加载 Embedding 模型...")
if os.path.exists(MODEL_LOCAL_PATH):
    embedding_model = SentenceTransformer(MODEL_LOCAL_PATH)
else:
    embedding_model = SentenceTransformer("damo/nlp_gte_sentence-embedding_chinese-base")

print("正在加载向量索引...")
faiss_index = faiss.read_index(os.path.join(DB_PATH, "gaokao.index"))
with open(os.path.join(DB_PATH, "gaokao_data.json"), "r", encoding="utf-8") as f:
    qa_data = json.load(f)

# 加载结构化数据
school_data = []
for filename in ["shanghairanking_cleaned.json"]:
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            school_data = json.load(f)

print(f"就绪，知识库共 {len(qa_data)} 条数据")

app = Flask(__name__, template_folder=TEMPLATE_PATH)


def direct_query(question):
    """直接查询：处理排名、省份、标签等结构化查询"""
    results = []

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

    for tag in ["985", "211", "双一流"]:
        if tag in question:
            matched = [s for s in school_data if tag in "、".join(s.get("tags", []))]
            if matched:
                lines = [f"{s['name']}（{s.get('province', '')}，排名{s.get('rank', '?')}）" for s in matched[:20]]
                results.append(f"{tag}大学（前20所）：\n" + "\n".join(lines))
            break

    rank_match = re.search(r'([一-龥]+大学)', question)
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
    """向量检索"""
    query_embedding = embedding_model.encode([question]).astype("float32")
    distances, indices = faiss_index.search(query_embedding, n_results)
    context_parts = []
    for idx in indices[0]:
        if 0 <= idx < len(qa_data):
            context_parts.append(f"- {qa_data[idx]['answer']}")
    return "\n".join(context_parts)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "请求格式错误"}), 400
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "请输入问题"}), 400

        # 直接查询 + 向量检索
        direct_result = direct_query(question)
        vector_result = vector_search(question)

        context_parts = []
        if direct_result:
            context_parts.append(f"【精确匹配】\n{direct_result}")
        context_parts.append(f"【相关问答】\n{vector_result}")
        context = "\n\n".join(context_parts)

        prompt = f"""你是高考志愿填报专家。请根据参考资料直接回答考生问题，要求：
1. 优先引用参考资料中的具体数据
2. 回答要详细、有条理
3. 如果有多条相关数据，综合分析
4. 不要说"无法提供"或"没有相关信息"，尽力从资料中找到答案

参考资料：
{context}

问题：{question}

详细回答："""

        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }, timeout=OLLAMA_TIMEOUT)

        if response.status_code == 200:
            return jsonify({"answer": response.json()["response"]})
        else:
            return jsonify({"error": f"Ollama 错误: {response.status_code}"}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "无法连接到 Ollama，请确保 Ollama 正在运行"}), 500
    except Exception as e:
        print(f"[ERROR] /ask: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n启动 Web 服务...")
    print("访问地址: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
