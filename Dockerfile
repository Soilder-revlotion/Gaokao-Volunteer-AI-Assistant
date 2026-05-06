FROM python:3.12-slim

WORKDIR /app

# 代理配置（构建时使用）
ARG HTTP_PROXY
ARG HTTPS_PROXY

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY scripts/config.py scripts/05_web.py scripts/
COPY templates/ templates/

# 环境变量（可通过 docker-compose 覆盖）
ENV OLLAMA_URL=http://ollama:11434/api/generate
ENV OLLAMA_MODEL=qwen2.5:3b
ENV DB_PATH=/app/db
ENV MODEL_LOCAL_PATH=/app/models/nlp_gte_sentence-embedding_chinese-base
ENV HF_ENDPOINT=https://hf-mirror.com

EXPOSE 5000

CMD ["python", "scripts/05_web.py"]
