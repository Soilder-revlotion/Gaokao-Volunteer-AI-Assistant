# 高考志愿 AI 助手

> 基于 RAG + 本地模型的高考志愿填报问答系统
> 数据不出网，免费运行，每年可更新数据

---

## 功能概览

| 功能 | 说明 |
|------|------|
| 智能问答 | 输入问题，系统从知识库检索相关内容，由 LLM 生成回答 |
| 智能推荐 | 输入分数、省份、科类，按"冲-稳-保"三档推荐院校，含专业组详情 |
| CSV 导出 | 推荐结果可导出为 CSV 文件 |
| 聊天模式 | 支持多轮对话，上下文记忆 |

---

## 技术架构

```
用户浏览器
    │
    ▼
Flask Web (端口 5000)
    ├── 向量检索: FAISS (768维, 70827条QA)
    ├── Embedding: nlp_gte_sentence-embedding_chinese-base
    ├── 精确匹配: 正则表达式
    └── LLM 生成: Ollama + qwen2.5:3b
            │
            ▼
        Ollama Server (端口 11434)
```

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| Web 框架 | Flask 3.1.1 | 轻量 Python Web 框架 |
| 向量数据库 | FAISS (faiss-cpu) | Facebook 开源的向量相似度检索库 |
| Embedding 模型 | nlp_gte_sentence-embedding_chinese-base | 阿里达摩院中文句向量模型，768维 |
| LLM | qwen2.5:3b via Ollama | 通义千问 2.5 3B 参数模型，Q4_K_M 量化 |
| 前端 | 原生 HTML/CSS/JS | 单页应用，极简白风格（类 ChatGPT） |
| 爬虫 | Playwright | 自动化数据采集 |

### 数据来源

| 数据源 | 文件 | 记录数 | 问答数 |
|--------|------|--------|--------|
| 软科排名 | shanghairanking_cleaned.json | 589所大学 | 1864 |
| 录取分数线 | eol_scores.json | 31366条, 407所大学 | 62708 |
| 软科专业排名 | shanghai_subject_ranking.json | 4924条 | 4924 |
| 就业数据 | employment_data.json | 575所大学 | 1098 |
| 手动数据 | manual_schools.json | 15条 | 15 |
| 政策问答 | gaokao_policy_qa.json | 27条 | 27 |
| **总计** | gaokao_qa_all.json | — | **70827** |

FAISS 索引：70827 条向量，768 维，存储于 `D:/gaokao_db/`

---

## 环境要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（推荐）、macOS、Linux |
| Python | 3.10+ |
| 内存 | 16GB（7b 模型会 OOM，推荐 3b） |
| 磁盘 | 约 10GB（模型 + 数据） |
| Ollama | 本地 LLM 运行时 |

---

## 方式一：本地运行

### 1. 安装 Ollama

访问 [ollama.com](https://ollama.com) 下载安装。

```bash
# 拉取模型（约 1.9GB）
ollama pull qwen2.5:3b
```

### 2. 安装 Python 依赖

```bash
pip install flask==3.1.1 sentence-transformers==3.0.1 faiss-cpu==1.9.0 numpy requests -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 准备数据和模型

确保以下路径存在：
- `D:/gaokao_db/` — FAISS 索引文件（首次运行 `python scripts/03_build_rag.py` 自动生成）
- `data/` — 数据文件
- `D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base/` — Embedding 模型

### 4. 启动

```bash
python scripts/05_web.py
```

访问 http://localhost:5000

---

## 方式二：Docker 部署

详见 [DEPLOYMENT.md](DEPLOYMENT.md)

**快速启动：**

```bash
# 1. 确保 Ollama 在宿主机运行（监听所有接口）
OLLAMA_HOST=0.0.0.0:11434 OLLAMA_MODELS="D:/ollama_models" ollama serve &

# 2. 启动 Web 容器
cd 高考志愿AI助手
docker compose up -d

# 3. 访问 http://localhost:5000
```

---

## API 接口

| 端点 | 方法 | 参数 | 说明 |
|------|------|------|------|
| `/` | GET | — | Web 界面 |
| `/ask` | POST | `{"question": "清华大学怎么样"}` | 智能问答 |
| `/recommend` | POST | `{"score": 550, "province": "江苏", "category": "物理类"}` | 智能推荐 |
| `/export` | POST | 同 `/recommend` | 导出 CSV |

---

## 项目结构

```
高考志愿AI助手/
├── data/                          # 数据文件
│   ├── gaokao_qa_all.json         # 合并后的 QA 数据 (70827条)
│   ├── eol_scores.json            # 录取分数线 (31366条)
│   ├── shanghairanking_cleaned.json
│   ├── shanghai_subject_ranking.json
│   ├── employment_data.json
│   ├── manual_schools.json
│   └── gaokao_policy_qa.json
├── scripts/
│   ├── config.py                  # 集中配置（支持环境变量覆盖）
│   ├── 03_build_rag.py            # 构建 FAISS 向量索引
│   ├── 04_query.py                # 命令行查询
│   ├── 05_web.py                  # Web 界面（主程序）
│   ├── clean_data.py              # 数据清洗
│   ├── run_full_pipeline.py       # 一键全自动管道
│   └── scrape_beijing.py          # 北京分数线爬取
├── templates/
│   └── index.html                 # 前端页面
├── Dockerfile                     # Docker 镜像构建
├── docker-compose.yml             # Docker 编排
├── requirements.txt               # Python 依赖
├── DEPLOYMENT.md                  # Docker 部署详细指南
└── .dockerignore                  # Docker 忽略文件
```

---

## 年度数据更新

每年高考后（6-7月）运行一次：

```bash
# 一键全自动：政策QA + 爬取 + 清洗 + 重建索引
python scripts/run_full_pipeline.py
```

或分步执行：

```bash
python scripts/clean_data.py       # 数据清洗
python scripts/03_build_rag.py     # 重建 FAISS 索引
```

---

## 开发历程

| 阶段 | 内容 | 状态 |
|------|------|------|
| 一 | 查询质量提升 — 升级到 qwen2.5:3b，统一 config，优化 prompt | ✓ |
| 二 | Web 界面优化 — 极简白风格(类ChatGPT)，修复 index 覆盖 bug | ✓ |
| 三 | 数据扩展 — 435所大学分数线爬取完成，QA从32186→70827条 | ✓ |
| 四 | 智能推荐 — 位次法v3(查表插值+主批次优先+动态阈值+专业组详情+CSV导出) | ✓ |
| 五 | 部署分发 — Docker容器化部署，宿主机Ollama + Docker Web | ✓ |

---

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| Ollama 连不上 | 确保 Ollama 正在运行：`ollama serve` |
| 推荐结果为空 | 检查省份+科类是否有 2025 年数据 |
| 回答较慢 | CPU 推理正常，3b 约 3-10 秒 |
| pip 下载慢 | 用清华镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| HuggingFace 下载不了 | 设置 `HF_ENDPOINT=https://hf-mirror.com` |
| Docker 容器连不上 Ollama | 确保 Ollama 监听 `0.0.0.0:11434`（设置 `OLLAMA_HOST`） |

---

## License

MIT
