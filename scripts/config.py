"""
集中配置文件
所有脚本共用的配置项统一在此管理
支持环境变量覆盖（Docker 部署时使用）
"""

import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Ollama LLM 配置
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

# 向量数据库路径
DB_PATH = os.environ.get("DB_PATH", "D:/gaokao_db")

# Embedding 模型路径
MODEL_LOCAL_PATH = os.environ.get("MODEL_LOCAL_PATH", "D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base")

# 数据目录
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
