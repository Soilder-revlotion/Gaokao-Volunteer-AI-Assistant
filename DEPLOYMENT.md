# Docker 部署指南

本文档详细记录了高考志愿 AI 助手的 Docker 容器化部署过程，包括从零开始的完整步骤、遇到的所有问题及解决方案。

---

## 架构设计

```
┌─────────────────────────────────────────────────┐
│                   宿主机 (Windows)                │
│                                                   │
│  Ollama Server (0.0.0.0:11434)                   │
│  ├── qwen2.5:3b (1.9GB)                         │
│  ├── qwen2.5:7b (4.5GB)                         │
│  └── 模型存储: D:\ollama_models                   │
│           ▲                                       │
│           │ host.docker.internal:11434            │
│           │                                       │
│  ┌────────┴────────────────────────────────┐     │
│  │  Docker 容器: gaokao-web                 │     │
│  │  ├── Flask Web (端口 5000)               │     │
│  │  ├── FAISS 索引 (挂载 D:/gaokao_db)      │     │
│  │  ├── Embedding 模型 (挂载 D:/models)     │     │
│  │  └── 数据文件 (挂载 ./data)              │     │
│  └─────────────────────────────────────────┘     │
│                                                   │
│  浏览器 → http://localhost:5000                    │
└─────────────────────────────────────────────────┘
```

**关键决策：Ollama 不放 Docker 里**

最初计划将 Ollama 也容器化（docker-compose 两个服务），但 ollama/ollama 镜像约 4GB，在国内网络环境下拉取极困难（反复超时、EOF）。最终方案是 Ollama 运行在宿主机，Web 应用在 Docker 中通过 `host.docker.internal` 连接宿主机 Ollama。

---

## 前置条件

| 组件 | 说明 |
|------|------|
| Docker Desktop | 已安装并运行（WSL2 后端） |
| Ollama | 已安装，qwen2.5:3b 模型已下载 |
| 数据文件 | `D:/gaokao_db/`、`D:/models/`、`data/` 已就绪 |

---

## 部署步骤

### Step 1: 创建 requirements.txt

```txt
flask==3.1.1
sentence-transformers==3.0.1
faiss-cpu==1.9.0
numpy>=1.24.0
requests>=2.31.0
```

### Step 2: 修改 scripts/config.py

将硬编码路径改为支持环境变量（本地运行不受影响，环境变量不存在时用默认值）：

```python
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))
DB_PATH = os.environ.get("DB_PATH", "D:/gaokao_db")
MODEL_LOCAL_PATH = os.environ.get("MODEL_LOCAL_PATH", "D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
```

### Step 3: 创建 Dockerfile

```dockerfile
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

# 环境变量
ENV OLLAMA_URL=http://ollama:11434/api/generate
ENV OLLAMA_MODEL=qwen2.5:3b
ENV DB_PATH=/app/db
ENV MODEL_LOCAL_PATH=/app/models/nlp_gte_sentence-embedding_chinese-base
ENV HF_ENDPOINT=https://hf-mirror.com

EXPOSE 5000

CMD ["python", "scripts/05_web.py"]
```

### Step 4: 创建 .dockerignore

```
.git
__pycache__
cookies/
*.png
debug_*
test_*
*.pyc
.DS_Store
```

### Step 5: 创建 docker-compose.yml

```yaml
services:
  gaokao-web:
    image: ai-gaokao-web:latest
    container_name: gaokao-web
    ports:
      - "5000:5000"
    volumes:
      - D:/gaokao_db:/app/db
      - D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base:/app/models/nlp_gte_sentence-embedding_chinese-base
      - ./data:/app/data
      - ./scripts:/app/scripts
      - ./templates:/app/templates
    environment:
      - OLLAMA_URL=http://host.docker.internal:11434/api/generate
      - OLLAMA_MODEL=qwen2.5:3b
      - DB_PATH=/app/db
      - MODEL_LOCAL_PATH=/app/models/nlp_gte_sentence-embedding_chinese-base
      - HTTP_PROXY=
      - HTTPS_PROXY=
      - http_proxy=
      - https_proxy=
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
```

### Step 6: 构建镜像

```bash
cd 高考志愿AI助手
docker compose build
```

构建过程约需 30-90 分钟（取决于网络），主要耗时在下载 PyTorch（~530MB）和 NVIDIA 库。

### Step 7: 配置 Ollama 监听所有接口

默认 Ollama 只监听 `127.0.0.1`，Docker 容器无法访问。需要设置 `OLLAMA_HOST=0.0.0.0:11434`。

**Windows 设置方法：**

```powershell
# 设置环境变量（永久生效）
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')
[System.Environment]::SetEnvironmentVariable('OLLAMA_MODELS', 'D:\ollama_models', 'User')
```

设置后需重启 Ollama。或临时启动：

```bash
OLLAMA_HOST=0.0.0.0:11434 OLLAMA_MODELS="D:/ollama_models" ollama serve &
```

**验证：**

```bash
netstat -an | grep 11434
# 应显示: TCP  0.0.0.0:11434  0.0.0.0:0  LISTENING
```

### Step 8: 启动容器

```bash
docker compose up -d
```

### Step 9: 验证

```bash
# 检查容器状态
docker ps

# 检查日志
docker logs gaokao-web

# 测试 Web 界面
curl http://localhost:5000

# 测试 API
curl -X POST http://localhost:5000/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"清华大学怎么样\"}"
```

浏览器访问 http://localhost:5000

---

## 遇到的问题及解决方案

### 问题 1: Docker 构建时 pip 下载超时

**现象：** `docker compose build` 时 pip 下载 PyTorch 等大包超时失败。

**原因：** Docker Desktop 的守护进程在 WSL2 虚拟机中运行，无法使用宿主机的代理。

**解决方案：** 在 Dockerfile 中通过 `ARG` 传递代理：

```dockerfile
ARG HTTP_PROXY
ARG HTTPS_PROXY
```

docker-compose.yml 中指定代理地址：

```yaml
build:
  context: .
  args:
    HTTP_PROXY: http://host.docker.internal:7897
    HTTPS_PROXY: http://host.docker.internal:7897
```

构建命令：

```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 docker compose build
```

### 问题 2: ollama/ollama 镜像拉取失败

**现象：** `docker pull ollama/ollama` 卡在 "Pulling fs layer" 不动，或下载到一半 EOF 断开。

**原因：** ollama/ollama 镜像约 4GB，国内网络环境下 Docker Hub 连接不稳定。

**解决方案：** 放弃在 Docker 中运行 Ollama，改为使用宿主机的 Ollama。这反而更好：
- 省去 4GB 镜像下载
- Ollama 本来就需要在宿主机安装
- 模型数据持久化在宿主机，不受容器生命周期影响

### 问题 3: 容器连不上宿主机 Ollama

**现象：** 容器内请求 Ollama API 超时或连接拒绝。

**原因：** Ollama 默认只监听 `127.0.0.1:11434`，Docker 容器的 `host.docker.internal` 解析到宿主机的其他 IP（如 `192.168.65.254`），无法连接。

**解决方案：** 设置 `OLLAMA_HOST=0.0.0.0:11434` 使 Ollama 监听所有网络接口。

```bash
# Windows PowerShell
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')
```

### 问题 4: 容器内请求走代理导致 Ollama 502

**现象：** 容器内调用 Ollama API 返回 502 错误。

**原因：** Docker 客户端配置了代理（`~/.docker/config.json`），容器内所有 HTTP 请求都被代理拦截，包括对宿主机 Ollama 的请求。

**解决方案：** 在 docker-compose.yml 中清空容器内的代理环境变量：

```yaml
environment:
  - HTTP_PROXY=
  - HTTPS_PROXY=
  - http_proxy=
  - https_proxy=
```

### 问题 5: 推荐功能报错 invalid literal for int()

**现象：** 选择某些省份+科类（如江苏物理类）时，智能推荐返回 500 错误：`invalid literal for int() with base 10: '-'`

**原因：** 爬取的分数线数据中，部分条目的 `min_rank` 字段为 `"-"`（字符串短横线）而非数字。这通常出现在高分段学校，数据源未提供位次信息。

**解决方案：** 在推荐函数中过滤无效数据：

```python
# 过滤条件：确保 min_score 和 min_rank 是有效数字
filtered = [
    s for s in score_data
    if s.get("province") == province
    and s.get("category") == category
    and s.get("year") == 2025
    and str(s.get("min_score", "")).replace(".", "").isdigit()
    and str(s.get("min_rank", "")).replace(".", "").isdigit()
]
```

共有 308 条数据的 `min_rank` 为 `"-"`，过滤后不影响推荐结果的完整性。

### 问题 6: 代码修改后容器不生效

**现象：** 修改本地 `scripts/05_web.py` 后，容器内运行的仍是旧代码。

**原因：** 代码在构建时被 bake 进镜像，运行时容器使用的是镜像内的副本。

**解决方案：** 将 `scripts/` 和 `templates/` 目录挂载为 volume：

```yaml
volumes:
  - ./scripts:/app/scripts
  - ./templates:/app/templates
```

这样本地修改代码后，重启容器即可生效（`docker compose restart`），无需重新构建镜像。

---

## 日常使用

### 启动

```bash
# 确保 Ollama 运行
ollama serve &

# 启动容器
cd 高考志愿AI助手
docker compose up -d
```

### 停止

```bash
docker compose down
```

### 查看日志

```bash
docker logs -f gaokao-web
```

### 更新代码后生效

```bash
docker compose restart
```

### 重新构建镜像（依赖变更时）

```bash
docker compose build
docker compose up -d
```

---

## 给其他开发者的部署指南

如果你想在自己的机器上部署这个项目：

### 1. 克隆项目

```bash
git clone https://github.com/Soilder-revlotion/Gaokao-Volunteer-AI-Assistant.git
cd Gaokao-Volunteer-AI-Assistant
```

### 2. 安装 Ollama 并下载模型

```bash
# 从 ollama.com 安装 Ollama
ollama pull qwen2.5:3b
```

### 3. 配置 Ollama 监听所有接口

```bash
# Linux/macOS
export OLLAMA_HOST=0.0.0.0:11434
ollama serve &

# Windows PowerShell
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')
# 然后重启 Ollama
```

### 4. 准备数据

确保 `data/` 目录下有数据文件。如果没有，需要先运行数据管道：

```bash
python scripts/run_full_pipeline.py
```

### 5. 构建并启动

```bash
docker compose build
docker compose up -d
```

### 6. 访问

打开浏览器访问 http://localhost:5000

---

## 镜像大小说明

构建后的镜像约 8.5GB，主要组成：

| 组件 | 大小 | 说明 |
|------|------|------|
| python:3.12-slim | ~200MB | 基础镜像 |
| PyTorch (CPU) | ~530MB | sentence-transformers 依赖 |
| NVIDIA CUDA 库 | ~2GB | PyTorch 间接依赖 |
| sentence-transformers | ~500MB | Embedding 框架 |
| FAISS | ~50MB | 向量检索库 |
| 其他依赖 | ~100MB | Flask, numpy 等 |

数据文件（FAISS 索引、Embedding 模型、QA 数据）通过 volume 挂载，不计入镜像大小。
