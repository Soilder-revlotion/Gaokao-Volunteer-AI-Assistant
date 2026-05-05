"""
集中配置文件
所有脚本共用的配置项统一在此管理
"""

import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Ollama LLM 配置
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"  # 7b 需要 32GB+ 内存，16GB 系统用 3b
OLLAMA_TIMEOUT = 120  # 7b 模型较慢，给足时间

# 向量数据库路径
DB_PATH = "D:/gaokao_db"

# Embedding 模型路径
MODEL_LOCAL_PATH = "D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base"

# 数据目录
DATA_DIR = os.path.join(BASE_DIR, "data")
