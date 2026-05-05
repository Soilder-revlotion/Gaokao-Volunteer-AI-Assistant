"""
第三步：搭建 RAG 知识库
读取数据 → 向量化 → 存入 FAISS
"""

import json
import os
import numpy as np

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = "D:/gaokao_db"  # FAISS 不支持中文路径，放到纯英文目录
MODEL_LOCAL_PATH = "D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base"

print("正在加载依赖...")
from sentence_transformers import SentenceTransformer
import faiss


def load_all_data():
    """自动加载所有含问答格式的 JSON 文件（必须有 question + answer 字段）"""
    all_data = []
    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list) or not data:
                continue
            if not data[0].get("question") or not data[0].get("answer"):
                print(f"  跳过 {filename}（非问答格式）")
                continue
            valid = [item for item in data if item.get("question") and item.get("answer")]
            all_data.extend(valid)
            print(f"  加载 {filename}: {len(valid)} 条问答")
    return all_data


def main():
    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    data = load_all_data()
    if not data:
        print("错误：没有找到数据！请先准备好 data/*.json 文件")
        return
    print(f"  共加载 {len(data)} 条数据")

    # 2. 加载 Embedding 模型
    print("\n[2/4] 加载 Embedding 模型...")
    if os.path.exists(MODEL_LOCAL_PATH):
        print(f"  从本地加载: {MODEL_LOCAL_PATH}")
        model = SentenceTransformer(MODEL_LOCAL_PATH)
    else:
        print("  从 HuggingFace 下载（首次需要下载约400MB）...")
        model = SentenceTransformer("damo/nlp_gte_sentence-embedding_chinese-base")
    print("  模型加载成功")

    # 3. 向量化
    print("\n[3/4] 向量化所有问题...")
    questions = [item["question"] for item in data]
    answers = [item["answer"] for item in data]
    embeddings = model.encode(questions, show_progress_bar=True, batch_size=50)
    embeddings = np.array(embeddings, dtype="float32")
    print(f"  向量化完成，维度: {embeddings.shape}")

    # 4. 存入 FAISS
    print(f"\n[4/4] 存入 FAISS 索引... ({DB_PATH})")
    os.makedirs(DB_PATH, exist_ok=True)

    # 创建索引
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # 保存索引
    faiss.write_index(index, os.path.join(DB_PATH, "gaokao.index"))

    # 保存问答数据（用于检索后返回答案）
    with open(os.path.join(DB_PATH, "gaokao_data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n完成！共存入 {len(data)} 条数据")
    print(f"索引文件: {os.path.join(DB_PATH, 'gaokao.index')}")
    print(f"数据文件: {os.path.join(DB_PATH, 'gaokao_data.json')}")


if __name__ == "__main__":
    main()
