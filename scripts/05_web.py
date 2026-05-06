"""
第五步：网页版后端
启动后访问 http://localhost:5000
"""

import csv
import io
import json
import os
import re
import urllib.parse
import requests
import numpy as np
from flask import Flask, request, jsonify, render_template, Response

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

# 加载录取分数线数据（用于智能推荐）
score_data = []
score_path = os.path.join(DATA_DIR, "eol_scores.json")
if os.path.exists(score_path):
    with open(score_path, "r", encoding="utf-8") as f:
        score_data = json.load(f)

# 构建学校排名映射（用于推荐排序）
rank_map = {}
for s in school_data:
    name = s.get("name", "")
    rank = s.get("rank", "9999")
    try:
        rank_map[name] = int(rank)
    except (ValueError, TypeError):
        rank_map[name] = 9999

print(f"就绪，知识库共 {len(qa_data)} 条数据，分数线 {len(score_data)} 条")

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


def estimate_rank(user_score, filtered):
    """从分数线数据构建分数→位次查找表，用分段线性插值估算用户位次"""
    # 提取所有 (分数, 位次) 对
    score_rank_pairs = [(int(s["min_score"]), int(s["min_rank"])) for s in filtered]
    score_rank_pairs.sort(key=lambda x: -x[0])

    # 去重：同分数取最小位次（更保守估计）
    score_to_rank = {}
    for sc, rk in score_rank_pairs:
        if sc not in score_to_rank or rk < score_to_rank[sc]:
            score_to_rank[sc] = rk
    sorted_scores = sorted(score_to_rank.keys(), reverse=True)

    if not sorted_scores:
        return None

    # 边界处理
    if user_score >= sorted_scores[0]:
        return max(1, score_to_rank[sorted_scores[0]])
    if user_score <= sorted_scores[-1]:
        return max(1, score_to_rank[sorted_scores[-1]])

    # 分段线性插值
    for i in range(len(sorted_scores) - 1):
        high_score = sorted_scores[i]
        low_score = sorted_scores[i + 1]
        if high_score >= user_score >= low_score:
            high_rank = score_to_rank[high_score]
            low_rank = score_to_rank[low_score]
            if high_score == low_score:
                return max(1, high_rank)
            ratio = (high_score - user_score) / (high_score - low_score)
            return max(1, int(high_rank + ratio * (low_rank - high_rank)))

    return max(1, score_to_rank[sorted_scores[-1]])


def recommend_schools(user_score, province, category):
    """基于位次法的智能推荐（v3：精确插值 + 主批次优先 + 动态阈值 + 专业组详情）"""
    user_score = int(user_score)

    # 过滤该省份+科类+2025年的数据
    filtered = [
        s for s in score_data
        if s.get("province") == province
        and s.get("category") == category
        and s.get("year") == 2025
        and s.get("min_score")
        and s.get("min_rank")
    ]

    if not filtered:
        return None

    # === 位次估算 ===
    user_rank = estimate_rank(user_score, filtered)
    if user_rank is None:
        return None

    # === 按学校聚合，收集所有批次详情 ===
    school_records = {}
    for s in filtered:
        name = s["school"]
        if name not in school_records:
            school_records[name] = []
        school_records[name].append(s)

    school_best = {}
    school_details = {}
    for name, records in school_records.items():
        # 优先级：含"本科"的批次 > 其他批次
        benke_records = [r for r in records if "本科" in str(r.get("batch", ""))]
        candidates = benke_records if benke_records else records

        # 取位次最接近用户位次的那条作为主推荐
        best = min(candidates, key=lambda r: abs(int(r["min_rank"]) - user_rank))
        school_best[name] = {
            "min_score": int(best["min_score"]),
            "min_rank": int(best["min_rank"]),
            "batch": best.get("batch", ""),
            "soft_rank": rank_map.get(name, 9999),
        }

        # 收集所有批次详情（去重）
        details = []
        seen = set()
        for r in records:
            key = (r.get("batch", ""), r.get("min_score"))
            if key not in seen:
                seen.add(key)
                details.append({
                    "batch": r.get("batch", ""),
                    "min_score": int(r["min_score"]),
                    "min_rank": int(r["min_rank"]),
                })
        details.sort(key=lambda x: x["min_rank"])
        school_details[name] = details

    # === 动态分档阈值 ===
    def get_thresholds(school_rank):
        if school_rank < 5000:
            return 1.5, 0.8, 0.6
        elif school_rank < 50000:
            return 1.8, 0.8, 0.6
        else:
            return 2.5, 0.7, 0.5

    chong, wen, bao = [], [], []
    for name, info in school_best.items():
        school_rank = info["min_rank"]
        chong_th, wen_th, bao_th = get_thresholds(school_rank)

        ratio = user_rank / max(school_rank, 1)
        rank_diff = user_rank - school_rank

        item = {
            "name": name,
            "min_score": info["min_score"],
            "min_rank": school_rank,
            "soft_rank": info["soft_rank"],
            "batch": info["batch"],
            "rank_diff": rank_diff,
            "details": school_details[name],
        }

        if ratio <= bao_th:
            bao.append(item)
        elif ratio <= wen_th:
            wen.append(item)
        elif ratio <= chong_th:
            chong.append(item)

    chong.sort(key=lambda x: x["soft_rank"])
    wen.sort(key=lambda x: x["soft_rank"])
    bao.sort(key=lambda x: x["soft_rank"])

    return {
        "user_rank": user_rank,
        "chong": chong[:15],
        "wen": wen[:15],
        "bao": bao[:15],
    }


@app.route("/recommend", methods=["POST"])
def recommend():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "请求格式错误"}), 400

        score = data.get("score")
        province = data.get("province", "").strip()
        category = data.get("category", "").strip()

        if not score or not province or not category:
            return jsonify({"error": "请填写完整信息（分数、省份、科类）"}), 400

        result = recommend_schools(score, province, category)
        if result is None:
            return jsonify({"error": f"暂无 {province} {category} 的录取数据"}), 404

        return jsonify(result)

    except Exception as e:
        print(f"[ERROR] /recommend: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/export", methods=["POST"])
def export():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "请求格式错误"}), 400

        province = data.get("province", "")
        category = data.get("category", "")
        score = data.get("score", "")
        user_rank = data.get("user_rank", "")
        chong = data.get("chong", [])
        wen = data.get("wen", [])
        bao = data.get("bao", [])

        output = io.StringIO()
        output.write('﻿')  # BOM for Excel
        writer = csv.writer(output)
        writer.writerow(["分类", "学校", "批次", "2025最低分", "最低位次", "软科排名", "位次差距"])
        writer.writerow([f"考生信息：{province} {category} {score}分 估算位次{user_rank}", "", "", "", "", "", ""])
        writer.writerow([])

        for label, items in [("冲一冲", chong), ("稳一稳", wen), ("保一保", bao)]:
            for s in items:
                diff = s.get("rank_diff", 0)
                diff_str = f"+{diff}" if diff > 0 else str(diff)
                writer.writerow([label, s.get("name", ""), s.get("batch", ""), s.get("min_score", ""), s.get("min_rank", ""), s.get("soft_rank", ""), diff_str])

        csv_content = output.getvalue()
        output.close()

        filename = f"gaokao_recommend_{province}_{category}_{score}.csv"
        encoded_filename = urllib.parse.quote(filename)

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
        )

    except Exception as e:
        print(f"[ERROR] /export: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n启动 Web 服务...")
    print("访问地址: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
