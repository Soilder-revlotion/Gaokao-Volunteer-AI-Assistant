# Docker 部署指南

本文档是高考志愿 AI 助手的 Docker 容器化部署完整指南。包含从零开始的每一步操作、遇到的所有问题及其解决方案，以及给其他开发者的部署教程。

---

## 目录

- [架构设计](#架构设计)
- [为什么 Ollama 不放 Docker 里](#为什么-ollama-不放-docker-里)
- [全新电脑部署教程](#全新电脑部署教程)
- [部署步骤详解](#部署步骤详解)
- [踩坑记录与解决方案](#踩坑记录与解决方案)
- [日常使用](#日常使用)
- [给其他开发者的部署指南](#给其他开发者的部署指南)
- [镜像大小说明](#镜像大小说明)
- [故障排查](#故障排查)

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      宿主机 (Windows/macOS/Linux)            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Ollama Server                                        │   │
│  │  监听地址: 0.0.0.0:11434                              │   │
│  │  模型存储: D:\ollama_models\                          │   │
│  │  ├── qwen2.5:3b  (1.9GB, 推荐)                       │   │
│  │  ├── qwen2.5:7b  (4.5GB, 需 16GB+ 内存)              │   │
│  │  └── my-qwen-0.5b (398MB, 测试用)                    │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │ TCP 连接                           │
│                         │ host.docker.internal:11434         │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Docker 容器: gaokao-web                              │   │
│  │                                                       │   │
│  │  Flask Web 应用 (端口 5000)                           │   │
│  │  ├── scripts/05_web.py (挂载自宿主机)                 │   │
│  │  ├── templates/index.html (挂载自宿主机)              │   │
│  │  ├── FAISS 索引 (挂载 D:/gaokao_db → /app/db)        │   │
│  │  ├── Embedding 模型 (挂载 D:/models → /app/models)   │   │
│  │  └── 数据文件 (挂载 ./data → /app/data)               │   │
│  └──────────────────────────────────────────────────────┘   │
│                         ▲                                    │
│                         │ HTTP                               │
│                         │                                    │
│  浏览器 ────────────────┘                                    │
│  http://localhost:5000                                        │
└─────────────────────────────────────────────────────────────┘
```

### 为什么这样设计

1. **Ollama 在宿主机运行**：Ollama 镜像约 4GB，国内拉取极困难；且 Ollama 本就需要在宿主机安装
2. **Web 应用在 Docker 中运行**：隔离 Python 环境，避免依赖冲突
3. **数据通过 volume 挂载**：数据持久化在宿主机，容器可随时重建
4. **代码也挂载**：修改代码后 `docker compose restart` 即生效，无需重新构建镜像

---

## 为什么 Ollama 不放 Docker 里

### 最初方案（失败）

最初设计为 docker-compose 两个服务：

```yaml
services:
  ollama:
    image: ollama/ollama    # 约 4GB
    ports:
      - "11434:11434"
  gaokao-web:
    build: .
    depends_on:
      - ollama
```

### 遇到的问题

1. **ollama/ollama 镜像拉取失败**：镜像约 4GB（4 个 layer），在国内网络环境下反复超时、EOF 断开
2. **Docker Hub 访问不稳定**：即使配置了代理，大文件下载仍容易中断
3. **国内镜像不可靠**：多个 Docker Hub 镜像站（USTC、163、百度）返回 EOF

### 最终方案

放弃在 Docker 中运行 Ollama，改为宿主机直接运行：

**优势：**
- 省去 4GB 镜像下载
- Ollama 本来就需要在宿主机安装（用户可能已经在用）
- 模型数据持久化在宿主机，不受容器生命周期影响
- 可以通过 Ollama 桌面应用管理模型，更方便

---

## 全新电脑部署教程

以下是从一台全新电脑开始，完整部署本项目的每一步操作。

### 前提条件

- Windows 10/11（64位）、macOS 或 Linux
- 至少 16GB 内存
- 至少 20GB 可用磁盘空间
- 能访问互联网（需要下载约 10GB 的软件和模型）

### Step 1: 安装 Ollama

Ollama 是本地 LLM 运行时，用于运行 qwen2.5:3b 大语言模型。

1. 访问 https://ollama.com
2. 点击 "Download" 按钮，下载对应操作系统的安装包
3. 运行安装程序，按默认选项安装
4. 安装完成后，Ollama 会自动在后台运行

**验证安装：**

打开终端（Windows: CMD 或 PowerShell；macOS/Linux: Terminal）：

```bash
ollama --version
```

应输出类似 `ollama version 0.20.7`。

### Step 2: 下载 LLM 模型

```bash
# 下载 qwen2.5:3b 模型（约 1.9GB）
ollama pull qwen2.5:3b
```

下载时间取决于网速，通常需要 5-20 分钟。

**验证模型：**

```bash
ollama list
```

应显示：

```
NAME          ID           SIZE    MODIFIED
qwen2.5:3b    357c53fb...  1.9GB   ...
```

**测试模型：**

```bash
ollama run qwen2.5:3b "你好"
```

应输出一段中文回复。按 `Ctrl+D` 退出。

### Step 3: 配置 Ollama 监听所有接口

这是**关键步骤**。默认情况下，Ollama 只监听 `127.0.0.1:11434`（仅本机访问）。Docker 容器有自己的网络命名空间，通过 `host.docker.internal` 访问宿主机时，走的不是 `127.0.0.1`，所以连不上。

需要让 Ollama 监听 `0.0.0.0:11434`（所有网络接口）。

**Windows 设置方法：**

打开 PowerShell（以管理员身份运行），执行：

```powershell
# 设置 OLLAMA_HOST 环境变量（永久生效）
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')

# 设置 OLLAMA_MODELS 环境变量（指定模型存储路径，可选）
[System.Environment]::SetEnvironmentVariable('OLLAMA_MODELS', 'D:\ollama_models', 'User')
```

设置完成后，需要**重启 Ollama**：
1. 右键点击系统托盘中的 Ollama 图标
2. 选择 "Quit Ollama"（退出）
3. 重新打开 Ollama 应用

**macOS 设置方法：**

```bash
# 在 ~/.zshrc 或 ~/.bashrc 中添加
export OLLAMA_HOST=0.0.0.0:11434

# 使配置生效
source ~/.zshrc

# 重启 Ollama
ollama serve &
```

**Linux 设置方法：**

```bash
# 编辑 Ollama 的 systemd 服务文件
sudo systemctl edit ollama.service

# 在 [Service] 部分添加：
# Environment="OLLAMA_HOST=0.0.0.0:11434"

# 重启服务
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**验证配置：**

```bash
# Windows CMD
netstat -an | findstr 11434

# macOS/Linux
netstat -an | grep 11434
```

应显示 `0.0.0.0:11434` 而非 `127.0.0.1:11434`：

```
TCP    0.0.0.0:11434          0.0.0.0:0              LISTENING    ← 正确
TCP    127.0.0.1:11434        0.0.0.0:0              LISTENING    ← 错误，需要重新配置
```

### Step 4: 安装 Docker Desktop

1. 访问 https://www.docker.com/products/docker-desktop/
2. 下载 Docker Desktop 安装包
3. 运行安装程序，按默认选项安装
4. 安装完成后重启电脑
5. 启动 Docker Desktop，等待它完全启动（系统托盘图标变绿）

**验证安装：**

```bash
docker --version
# 应输出类似: Docker version 29.3.1

docker compose version
# 应输出类似: Docker Compose version v5.1.1
```

**Docker Desktop 设置：**

打开 Docker Desktop → Settings（设置）：
- **General**: 确保 "Use the WSL 2 based engine" 已勾选（Windows）
- **Resources → WSL Integration**: 确保已启用
- **Docker Engine**: 可配置镜像加速器（可选）

### Step 5: 克隆项目

```bash
git clone https://github.com/Soilder-revlotion/Gaokao-Volunteer-AI-Assistant.git
cd Gaokao-Volunteer-AI-Assistant
```

如果没有 Git，也可以：
1. 访问 GitHub 项目页面
2. 点击绿色 "Code" 按钮
3. 选择 "Download ZIP"
4. 解压到任意目录
5. 在终端中 `cd` 到解压后的目录

### Step 6: 准备数据和模型路径

确保以下目录存在（如果不存在，需要创建或修改配置）：

**FAISS 索引目录（必须）：**

```
D:\gaokao_db\
├── gaokao.index      # FAISS 索引文件（首次运行自动生成）
└── metadata.json     # 元数据文件
```

如果目录不存在，首次运行 `03_build_rag.py` 会自动创建。

**Embedding 模型目录（必须）：**

```
D:\models\text2vec\damo\nlp_gte_sentence-embedding_chinese-base\
├── pytorch_model.bin
├── config.json
├── tokenizer.json
└── ...
```

如果模型不在默认路径，需要修改 `scripts/config.py` 中的 `MODEL_LOCAL_PATH`。

**数据文件目录（必须）：**

```
项目目录\data\
├── gaokao_qa_all.json
├── eol_scores.json
├── shanghairanking_cleaned.json
├── shanghai_subject_ranking.json
├── employment_data.json
├── manual_schools.json
└── gaokao_policy_qa.json
```

这些文件已包含在项目中，无需额外下载。

### Step 7: 构建 Docker 镜像

```bash
cd Gaokao-Volunteer-AI-Assistant
docker compose build
```

**构建过程说明：**

构建过程约需 30-90 分钟，主要耗时在：
1. 下载 python:3.12-slim 基础镜像（~200MB）
2. 安装 PyTorch（~530MB）
3. 安装 NVIDIA CUDA 库（~2GB，PyTorch 间接依赖）
4. 安装 sentence-transformers、FAISS 等依赖

**如果构建超时或失败：**

可能是网络问题。配置代理后重试：

```bash
# 设置代理环境变量后构建
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 docker compose build
```

其中 `127.0.0.1:7897` 替换为你实际的代理地址。

**验证构建成功：**

```bash
docker images | grep ai-gaokao-web
# 应显示: ai-gaokao-web   latest   xxx   xxx   x.xGB
```

### Step 8: 启动容器

```bash
docker compose up -d
```

**参数说明：**
- `up`: 创建并启动容器
- `-d`: 后台运行（detach）

**验证启动：**

```bash
# 查看容器状态
docker ps

# 应显示:
# NAMES        STATUS         PORTS
# gaokao-web   Up X seconds   0.0.0.0:5000->5000/tcp

# 查看日志
docker logs gaokao-web

# 应显示:
# 正在加载依赖...
# 正在加载 Embedding 模型...
# 正在加载向量索引...
# 就绪，知识库共 70827 条数据，分数线 31366 条
# 启动 Web 服务...
# 访问地址: http://localhost:5000
```

### Step 9: 访问和测试

打开浏览器访问 http://localhost:5000

**测试智能问答：**
1. 在输入框输入 "清华大学怎么样"
2. 按回车或点击发送按钮
3. 应看到 AI 生成的回答

**测试智能推荐：**
1. 点击 "智能推荐" 标签
2. 输入：分数 550，省份 江苏，科类 物理类
3. 点击 "推荐" 按钮
4. 应看到冲-稳-保三档推荐结果

**测试 CSV 导出：**
1. 在推荐结果页面点击 "导出 CSV"
2. 应下载一个 CSV 文件

---

## 部署步骤详解

### 各配置文件的作用

#### Dockerfile

```dockerfile
FROM python:3.12-slim        # 基础镜像：Python 3.12 精简版

WORKDIR /app                  # 工作目录

# 代理配置（构建时使用，通过 docker-compose.yml 的 args 传入）
ARG HTTP_PROXY
ARG HTTPS_PROXY

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY scripts/config.py scripts/05_web.py scripts/
COPY templates/ templates/

# 环境变量（运行时配置，可通过 docker-compose.yml 的 environment 覆盖）
ENV OLLAMA_URL=http://ollama:11434/api/generate
ENV OLLAMA_MODEL=qwen2.5:3b
ENV DB_PATH=/app/db
ENV MODEL_LOCAL_PATH=/app/models/nlp_gte_sentence-embedding_chinese-base
ENV HF_ENDPOINT=https://hf-mirror.com

EXPOSE 5000                   # 暴露端口

CMD ["python", "scripts/05_web.py"]   # 启动命令
```

**关键点：**
- `ARG` 只在构建时有效，`ENV` 在运行时有效
- 只复制了需要的文件（config.py, 05_web.py, templates/），不复制整个项目
- 代码通过 volume 挂载后，镜像内的代码会被覆盖

#### docker-compose.yml

```yaml
services:
  gaokao-web:
    image: ai-gaokao-web:latest          # 使用构建好的镜像
    container_name: gaokao-web            # 容器名称
    ports:
      - "5000:5000"                       # 端口映射: 宿主机5000 → 容器5000
    volumes:
      - D:/gaokao_db:/app/db              # FAISS 索引
      - D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base:/app/models/nlp_gte_sentence-embedding_chinese-base  # Embedding 模型
      - ./data:/app/data                  # 数据文件
      - ./scripts:/app/scripts            # 代码目录（修改后 restart 即生效）
      - ./templates:/app/templates        # 前端页面
    environment:
      - OLLAMA_URL=http://host.docker.internal:11434/api/generate  # Ollama 地址
      - OLLAMA_MODEL=qwen2.5:3b           # 使用的模型
      - DB_PATH=/app/db                   # 容器内 FAISS 路径
      - MODEL_LOCAL_PATH=/app/models/nlp_gte_sentence-embedding_chinese-base  # 容器内模型路径
      - HTTP_PROXY=                       # 清空代理（防止容器内请求走代理）
      - HTTPS_PROXY=
      - http_proxy=
      - https_proxy=
    extra_hosts:
      - "host.docker.internal:host-gateway"  # 确保 host.docker.internal 可解析
    restart: unless-stopped                # 自动重启（除非手动停止）
```

**关键点：**
- `host.docker.internal` 是 Docker 提供的特殊域名，解析到宿主机 IP
- `extra_hosts` 确保这个域名在所有平台上都能正确解析
- 清空代理环境变量是为了防止容器内的请求被代理拦截
- 代码目录挂载后，修改本地代码 → `docker compose restart` 即生效

#### requirements.txt

```
flask==3.1.1                    # Web 框架
sentence-transformers==3.0.1    # Embedding 模型框架
faiss-cpu==1.9.0                # 向量检索库（CPU 版本）
numpy>=1.24.0                   # 数值计算库
requests>=2.31.0                # HTTP 客户端
```

#### .dockerignore

```
.git                            # Git 仓库（不需要）
__pycache__                     # Python 缓存
cookies/                        # 浏览器 Cookie
*.png                           # 图片文件
debug_*                         # 调试文件
test_*                          # 测试文件
*.pyc                           # Python 字节码
.DS_Store                       # macOS 系统文件
```

---

## 踩坑记录与解决方案

### 问题 1: Docker 构建时 pip 下载超时

**现象：**

```
ERROR: Could not find a version that satisfies the requirement torch
pip._vendor.urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool...
```

**原因分析：**

Docker Desktop 的守护进程运行在 WSL2 虚拟机中。当你在宿主机终端执行 `docker compose build` 时，构建过程实际在 WSL2 虚拟机里执行。宿主机配置的代理（如 Clash Verge）对 WSL2 虚拟机不可见。

**解决过程：**

1. 尝试设置 Docker Desktop 的代理 → 无效（Docker Desktop 的代理设置只影响容器，不影响构建）
2. 尝试在 Dockerfile 中 `ENV HTTP_PROXY=...` → 无效（ENV 在运行时生效，不在构建时）
3. 最终方案：通过 `ARG` 在构建时传入代理

**解决方案：**

Dockerfile 中添加：
```dockerfile
ARG HTTP_PROXY
ARG HTTPS_PROXY
```

docker-compose.yml 中指定：
```yaml
build:
  context: .
  args:
    HTTP_PROXY: http://host.docker.internal:7897
    HTTPS_PROXY: http://host.docker.internal:7897
```

构建命令（在宿主机终端执行）：
```bash
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 docker compose build
```

> **注意**: `host.docker.internal:7897` 是 Docker 构建时访问宿主机代理的地址；`127.0.0.1:7897` 是 docker-compose CLI 读取的代理地址。两者不同。

---

### 问题 2: ollama/ollama 镜像拉取失败

**现象：**

```bash
docker pull ollama/ollama
# 一直卡在 "Pulling fs layer" 不动
# 或下载到一半报错: short read: expected 3862167689 bytes but got 55971968: unexpected EOF
```

**原因分析：**

ollama/ollama 镜像约 4GB，包含 4 个 layer。Docker Hub 在国内访问不稳定，大文件下载容易中断。

**尝试过的方案：**

| 方案 | 结果 |
|------|------|
| 直接 `docker pull` | 卡在 "Pulling fs layer" |
| 配置代理后 pull | 下载到一半 EOF |
| 使用国内镜像站（USTC、163、百度） | 返回 EOF |
| 使用 docker.1ms.run 镜像 | 同样卡住 |
| 重启 Docker Desktop | 无效 |
| 修改 Docker Desktop 代理设置 | 无效 |

**最终方案：**

放弃在 Docker 中运行 Ollama，改为使用宿主机的 Ollama。

修改 docker-compose.yml，去掉 ollama 服务，gaokao-web 直接连接宿主机 Ollama：

```yaml
services:
  gaokao-web:
    environment:
      - OLLAMA_URL=http://host.docker.internal:11434/api/generate
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

---

### 问题 3: 容器连不上宿主机 Ollama

**现象：**

容器内调用 Ollama API 返回 502 或超时。

**原因分析：**

Ollama 默认只监听 `127.0.0.1:11434`（localhost）。Docker 容器通过 `host.docker.internal` 访问宿主机时，实际连接的是宿主机的另一个 IP（如 `192.168.65.254`），而不是 `127.0.0.1`。

```
容器 → host.docker.internal → 192.168.65.254:11434 → 拒绝连接（Ollama 只听 127.0.0.1）
```

**验证方法：**

```bash
# 在宿主机执行
netstat -an | grep 11434

# 如果显示 127.0.0.1:11434，说明只监听 localhost
# 需要改为 0.0.0.0:11434
```

**解决方案：**

设置 `OLLAMA_HOST=0.0.0.0:11434`，使 Ollama 监听所有网络接口。

Windows PowerShell（以管理员身份运行）：
```powershell
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')
```

然后重启 Ollama（关闭并重新打开 Ollama 应用）。

**验证：**

```bash
netstat -an | grep 11434
# 应显示: TCP  0.0.0.0:11434  0.0.0.0:0  LISTENING
```

---

### 问题 4: 容器内请求走代理导致 Ollama 502

**现象：**

容器内调用 Ollama API 返回 502 错误，日志显示请求被代理拦截。

**原因分析：**

Docker 客户端配置了代理（`~/.docker/config.json`）：

```json
{
  "proxies": {
    "default": {
      "httpProxy": "http://host.docker.internal:7897",
      "httpsProxy": "http://host.docker.internal:7897"
    }
  }
}
```

这个配置会让容器内**所有** HTTP 请求都走代理，包括对宿主机 Ollama 的请求。但代理服务器无法正确转发到 Ollama，导致 502。

**解决方案：**

在 docker-compose.yml 中清空容器内的代理环境变量：

```yaml
environment:
  - HTTP_PROXY=
  - HTTPS_PROXY=
  - http_proxy=
  - https_proxy=
```

这样容器内的请求就不走代理了，直接连接 `host.docker.internal:11434`。

---

### 问题 5: 推荐功能报错 invalid literal for int()

**现象：**

选择某些省份+科类（如江苏物理类）时，智能推荐返回 500 错误：

```
{"error": "invalid literal for int() with base 10: '-'"}
```

**原因分析：**

爬取的分数线数据中，部分条目的 `min_rank` 字段为 `"-"`（字符串短横线）而非数字。这通常出现在高分段学校，数据源未提供位次信息。

```json
{
  "school": "清华大学",
  "province": "江苏",
  "category": "物理类",
  "year": 2025,
  "batch": "本科批",
  "min_score": 686,
  "min_rank": "-"          // ← 问题在这里
}
```

共有 308 条这样的数据。

代码中 `int("-")` 会抛出 `ValueError`。

**解决方案：**

在 `recommend_schools` 函数中过滤无效数据：

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

同时在 `estimate_rank` 函数中添加 try/except 作为安全网：

```python
score_rank_pairs = []
for s in filtered:
    try:
        score_rank_pairs.append((int(s["min_score"]), int(s["min_rank"])))
    except (ValueError, TypeError):
        continue
```

---

### 问题 6: 代码修改后容器不生效

**现象：**

修改本地 `scripts/05_web.py` 后，容器内运行的仍是旧代码。`docker restart gaokao-web` 也无效。

**原因分析：**

代码在 `docker compose build` 时被 bake 进镜像。运行时容器使用的是镜像内的代码副本，与本地文件无关。

**解决方案：**

将 `scripts/` 和 `templates/` 目录挂载为 volume：

```yaml
volumes:
  - ./scripts:/app/scripts
  - ./templates:/app/templates
```

这样本地文件会覆盖镜像内的文件。修改代码后，只需 `docker compose restart` 即可生效，无需重新构建镜像。

---

### 问题 7: Docker Desktop 代理设置无效

**现象：**

在 Docker Desktop Settings 中配置了代理，但 `docker pull` 仍然卡住。

**原因分析：**

Docker Desktop 的代理设置分为两层：
1. **容器代理**（`ContainersOverrideProxyHTTP`）：影响容器内的请求
2. **守护进程代理**（`OverrideProxyHTTP`）：影响 Docker 守护进程的请求（如 pull 镜像）

守护进程运行在 WSL2 虚拟机中，`127.0.0.1:7897` 指向虚拟机自身，而非宿主机的代理。

**解决方案：**

修改 `~/.docker/settings-store.json`，将代理地址改为 `host.docker.internal:7897`：

```json
{
  "OverrideProxyHTTP": "http://host.docker.internal:7897",
  "OverrideProxyHTTPS": "http://host.docker.internal:7897"
}
```

然后重启 Docker Desktop。

> **注意**: 此问题在最终方案中已不再重要（因为不需要拉取 ollama 镜像），但保留记录供参考。

---

## 日常使用

### 启动

```bash
# 1. 确保 Ollama 正在运行
#    Windows: 检查系统托盘是否有 Ollama 图标
#    macOS/Linux: ollama serve &

# 2. 启动容器
cd Gaokao-Volunteer-AI-Assistant
docker compose up -d
```

### 停止

```bash
docker compose down
```

### 重启（代码修改后）

```bash
docker compose restart
```

### 查看日志

```bash
# 实时查看
docker logs -f gaokao-web

# 查看最近 50 行
docker logs --tail 50 gaokao-web
```

### 重新构建镜像（依赖变更时）

如果修改了 `requirements.txt` 或 `Dockerfile`，需要重新构建：

```bash
docker compose build
docker compose up -d
```

### 进入容器调试

```bash
# 进入容器的 shell
docker exec -it gaokao-web bash

# 在容器内测试 Ollama 连接
curl http://host.docker.internal:11434/api/tags

# 在容器内测试 Web 接口
curl -X POST http://127.0.0.1:5000/ask -H "Content-Type: application/json" -d '{"question":"test"}'
```

---

## 给其他开发者的部署指南

如果你想在自己的机器上部署这个项目，请按以下步骤操作：

### 1. 前置条件确认

```bash
# 检查 Docker
docker --version
docker compose version

# 检查 Ollama
ollama --version
ollama list   # 应有 qwen2.5:3b 模型
```

### 2. 克隆项目

```bash
git clone https://github.com/Soilder-revlotion/Gaokao-Volunteer-AI-Assistant.git
cd Gaokao-Volunteer-AI-Assistant
```

### 3. 配置 Ollama

```bash
# Windows PowerShell
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')
# 重启 Ollama

# Linux/macOS
export OLLAMA_HOST=0.0.0.0:11434
ollama serve &
```

### 4. 修改配置（如果路径不同）

如果你的数据路径与默认不同，需要修改 `scripts/config.py`：

```python
DB_PATH = os.environ.get("DB_PATH", "你的FAISS索引路径")
MODEL_LOCAL_PATH = os.environ.get("MODEL_LOCAL_PATH", "你的Embedding模型路径")
```

或修改 `docker-compose.yml` 中的 volume 挂载路径。

### 5. 构建并启动

```bash
docker compose build    # 首次约 30-90 分钟
docker compose up -d
```

### 6. 验证

```bash
docker ps                    # 检查容器状态
docker logs gaokao-web       # 检查启动日志
curl http://localhost:5000   # 检查 Web 界面
```

### 7. 访问

打开浏览器访问 http://localhost:5000

---

## 镜像大小说明

构建后的镜像约 8.5GB，主要组成：

| 组件 | 大小 | 说明 |
|------|------|------|
| python:3.12-slim | ~200MB | 基础镜像，精简版 Python |
| PyTorch (CPU) | ~530MB | sentence-transformers 的核心依赖 |
| NVIDIA CUDA 库 | ~2GB | PyTorch 间接依赖（即使不用 GPU） |
| sentence-transformers | ~500MB | Embedding 框架及其依赖 |
| FAISS (faiss-cpu) | ~50MB | 向量检索库 |
| 其他依赖 | ~100MB | Flask, numpy, requests 等 |

**为什么镜像这么大？**

PyTorch 即使安装 CPU 版本，也会下载部分 NVIDIA CUDA 库（作为 fallback）。这是 PyTorch 的设计决定，无法避免。

**数据文件不计入镜像大小：**

- FAISS 索引（~222MB）→ 挂载自 `D:/gaokao_db/`
- Embedding 模型（~400MB）→ 挂载自 `D:/models/`
- QA 数据（~38MB）→ 挂载自 `./data/`

---

## 故障排查

### 容器启动失败

```bash
# 查看详细日志
docker logs gaokao-web

# 常见原因：
# 1. 端口 5000 被占用 → 关闭占用端口的程序
# 2. volume 挂载路径不存在 → 检查路径是否正确
# 3. Ollama 未启动 → 先启动 Ollama
```

### 容器内无法连接 Ollama

```bash
# 进入容器测试
docker exec -it gaokao-web bash
curl http://host.docker.internal:11434/api/tags

# 如果超时：
# 1. 检查 Ollama 是否监听 0.0.0.0（而非 127.0.0.1）
# 2. 检查防火墙是否阻止了 11434 端口
```

### 推荐结果为空

```bash
# 检查数据文件是否存在
docker exec gaokao-web ls -la /app/data/

# 检查特定省份的数据
docker exec gaokao-web python -c "
import json
with open('/app/data/eol_scores.json') as f:
    data = json.load(f)
filtered = [s for s in data if s.get('province') == '你的省份' and s.get('category') == '你的科类' and s.get('year') == 2025]
print(f'找到 {len(filtered)} 条数据')
"
```

### Embedding 模型加载失败

```bash
# 检查模型目录
docker exec gaokao-web ls -la /app/models/nlp_gte_sentence-embedding_chinese-base/

# 如果目录为空，检查 volume 挂载
# 确保 D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base/ 存在且有文件
```

### 重新构建镜像

如果遇到无法解决的问题，可以完全重建：

```bash
# 停止并删除容器
docker compose down

# 删除旧镜像
docker rmi ai-gaokao-web:latest

# 重新构建
docker compose build

# 启动
docker compose up -d
```
