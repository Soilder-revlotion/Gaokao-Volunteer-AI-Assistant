# 高考志愿 AI 助手

> 基于 RAG（检索增强生成）+ 本地大模型的高考志愿填报问答系统
> 所有数据和模型均在本地运行，不出网络，完全免费
> 每年高考后可自行更新数据，持续使用

---

## 目录

- [功能概览](#功能概览)
- [效果展示](#效果展示)
- [技术架构](#技术架构)
- [环境要求](#环境要求)
- [方式一：本地运行](#方式一本地运行)
- [方式二：Docker 部署](#方式二docker-部署)
- [API 接口](#api-接口)
- [项目结构](#项目结构)
- [数据说明](#数据说明)
- [年度数据更新](#年度数据更新)
- [开发历程](#开发历程)
- [常见问题](#常见问题)

---

## 功能概览

### 1. 智能问答（聊天模式）

输入任何关于高考志愿的问题，系统会：
1. 用 FAISS 向量检索从 70827 条知识库中找到最相关的 5 条参考内容
2. 同时用正则表达式做精确匹配（如学校名称）
3. 将参考内容 + 用户问题组装成 prompt，发送给本地 LLM（qwen2.5:3b）
4. LLM 基于参考资料生成回答

支持多轮对话，上下文记忆。

**示例问题：**
- "清华大学怎么样？"
- "河南考生理科580分能上什么学校？"
- "什么是平行志愿？"
- "中国计量大学的就业率是多少？"

### 2. 智能推荐

输入高考分数、所在省份、科类（物理类/历史类/理科/文科），系统会：
1. 从分数线数据中筛选该省份 + 科类 + 2025 年的所有记录
2. 用分段线性插值法估算考生位次
3. 对每所学校计算考生位次与录取位次的比值
4. 按"冲-稳-保"三档推荐，每档 15 所学校
5. 展示每个学校的全部批次详情（本科一批、提前批等）
6. 支持导出为 CSV 文件

**推荐算法特点：**
- 位次估算：查表 + 分段线性插值，比简单公式更准确
- 主批次优先：同一学校优先展示本科批次数据
- 动态阈值：根据学校层次（985/211/普通）动态调整冲稳保分数线
- 专业组详情：展示同一学校不同批次的录取情况

### 3. CSV 导出

推荐结果可一键导出为 CSV 文件，方便在 Excel 中查看和比较。

---

## 效果展示

### 智能问答

```
用户: 清华大学怎么样？

AI: 清华大学在教育界享有极高的声誉，在多个维度上都显示出了卓越的表现。
首先，清华大学位于中国的首都北京，作为一所综合类大学，提供广泛的学术课程。
关于清华大学的教育资源和地位：
- 清华大学是双一流、985及211工程的重点高校
- 2024年毕业生的就业率达到98.47%
- 考研率为28.12%
...
```

### 智能推荐

```
输入: 550分, 江苏, 物理类

冲一冲（15所）:
  南京信息工程大学 | 2024年最低分551 | 位次82435
  南京工业大学     | 2024年最低分549 | 位次84577
  ...

稳一稳（15所）:
  扬州大学         | 2024年最低分543 | 位次91234
  江苏大学         | 2024年最低分541 | 位次93456
  ...

保一保（15所）:
  南通大学         | 2024年最低分535 | 位次99876
  ...
```

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                             │
│                     http://localhost:5000                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Flask Web 应用 (05_web.py)                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  正则精确匹配  │  │ FAISS 向量检索 │  │  LLM 生成回答     │  │
│  │  (direct_     │  │ (vector_     │  │  (Ollama API)    │  │
│  │   query)      │  │  search)     │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                │                    │              │
│         ▼                ▼                    ▼              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ gaokao_qa_   │  │ FAISS 索引   │  │  Ollama Server   │  │
│  │ all.json     │  │ 70827条向量  │  │  qwen2.5:3b      │  │
│  │ (70827条QA)  │  │ 768维        │  │  (端口 11434)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              智能推荐 (recommend_schools)              │   │
│  │  位次法v3: 查表插值 + 主批次优先 + 动态阈值            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 工作流程

#### 智能问答流程

```
用户输入问题
    │
    ▼
┌─────────────────┐     ┌─────────────────┐
│ 正则精确匹配     │     │ FAISS 向量检索    │
│ 遍历 QA 数据，   │     │ 问题 → Embedding │
│ 用正则匹配学校名 │     │ → 在 70827 条向量 │
│ 分数等关键词     │     │ 中找 Top 5 相似   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│         组装 Prompt                      │
│ "你是高考志愿填报专家。请根据参考资料       │
│  直接回答考生问题..."                     │
│  + 精确匹配结果 + 向量检索结果             │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│         Ollama (qwen2.5:3b)             │
│         本地 LLM 推理                    │
└────────────────────┬────────────────────┘
                     │
                     ▼
              返回生成的回答
```

#### 智能推荐流程

```
用户输入: 分数 + 省份 + 科类
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. 数据筛选                              │
│    过滤: 省份 + 科类 + 2025年             │
│    排除: min_score 或 min_rank 为 "-" 的  │
│    结果: 该省份该科类的有效录取数据        │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 2. 位次估算                              │
│    从筛选数据构建 分数→位次 查找表         │
│    用分段线性插值估算考生位次              │
│    例: 550分 → 位次 78432                │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 3. 学校聚合                              │
│    按学校名聚合所有批次数据               │
│    优先选"本科"批次                       │
│    取位次最接近考生的那条作为主推荐        │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│ 4. 动态分档                              │
│    计算: ratio = 考生位次 / 学校录取位次   │
│    根据学校层次动态调整阈值:              │
│    - 985/211: 冲1.5 稳0.8 保0.6          │
│    - 普通一本: 冲1.8 稳0.8 保0.6          │
│    - 二本:     冲2.5 稳0.7 保0.5          │
│    分为 冲/稳/保 三档，每档15所           │
└────────────────────┬────────────────────┘
                     │
                     ▼
              返回推荐结果 + 专业组详情
```

### 技术栈详解

| 组件 | 技术 | 版本 | 作用 | 为什么选它 |
|------|------|------|------|-----------|
| Web 框架 | Flask | 3.1.1 | 提供 HTTP API 和静态页面 | 轻量、简单、Python 生态 |
| 向量数据库 | FAISS (faiss-cpu) | 1.9.0 | 存储 70827 条 768 维向量，支持快速相似度检索 | Facebook 开源，纯 CPU 即可运行，性能优秀 |
| Embedding 模型 | nlp_gte_sentence-embedding_chinese-base | — | 将文本转为 768 维向量 | 阿里达摩院出品，中文效果好，体积小（~400MB） |
| LLM | qwen2.5:3b | Q4_K_M 量化 | 理解问题并生成回答 | 中文能力强，3B 参数在 16GB 内存上可运行 |
| LLM 运行时 | Ollama | 0.20.7 | 管理和运行 LLM 模型 | 一键安装，支持多模型管理，API 简单 |
| 前端 | 原生 HTML/CSS/JS | — | 用户界面 | 无框架依赖，单文件，加载快 |
| 爬虫 | Playwright | 1.59.1 | 自动化采集高考数据 | 支持动态渲染页面，反检测能力强 |

### 关键技术点

#### 1. RAG（检索增强生成）

传统 LLM 的问题：知识截止到训练日期，无法获取最新数据，容易"幻觉"。

RAG 的解决方案：
- **检索（Retrieval）**: 先从知识库中检索与问题相关的文档
- **增强（Augmented）**: 将检索到的文档作为"参考资料"注入 prompt
- **生成（Generation）**: LLM 基于参考资料生成回答，而非凭空编造

本项目的 RAG 实现：
```
用户问题 → Embedding → FAISS 检索 Top 5 → 组装 Prompt → LLM 生成
```

#### 2. 位次法推荐

高考录取的核心逻辑是"位次优先"而非"分数优先"。同一年份，不同分数对应的位次不同；同一分数在不同年份的位次也不同。

位次法的步骤：
1. 从该省份的分数线数据中，构建"分数 → 位次"的查找表
2. 用分段线性插值估算考生位次（比简单线性公式更准确）
3. 用考生位次与各学校录取位次比较，而非直接比较分数

#### 3. 分段线性插值

```
已知: 分数 580 → 位次 50000
已知: 分数 560 → 位次 65000
求:   分数 570 → 位次 ?

插值: ratio = (580 - 570) / (580 - 560) = 0.5
位次 = 50000 + 0.5 × (65000 - 50000) = 57500
```

---

## 环境要求

### 硬件要求

| 组件 | 最低要求 | 推荐配置 | 说明 |
|------|---------|---------|------|
| CPU | 4 核 | 8 核 | LLM 推理主要依赖 CPU |
| 内存 | 12GB | 16GB | 3b 模型约占 2GB，加上 FAISS 和 Embedding 模型 |
| 磁盘 | 10GB | 20GB | 模型 2.5GB + 数据 200MB + Docker 镜像 8.5GB |
| GPU | 不需要 | — | 纯 CPU 推理，3b 模型约 3-10 秒/次 |

> **注意**: 7b 模型需要约 5GB 内存，16GB 内存的电脑在运行其他程序时可能 OOM（内存溢出）。推荐使用 3b 模型。

### 软件要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行后端代码 |
| Ollama | 最新版 | 运行 LLM 模型 |
| Docker Desktop | 最新版 | 容器化部署（可选） |
| Git | 最新版 | 克隆代码（可选） |

### 磁盘空间明细

| 组件 | 大小 | 路径 |
|------|------|------|
| qwen2.5:3b 模型 | ~1.9GB | `D:\ollama_models\` 或 `~/.ollama/models/` |
| Embedding 模型 | ~400MB | `D:\models\text2vec\damo\nlp_gte_sentence-embedding_chinese-base\` |
| FAISS 索引 | ~222MB | `D:\gaokao_db\` |
| QA 数据文件 | ~38MB | `data/` |
| Python 依赖 | ~3GB | Python 环境的 site-packages |
| Docker 镜像 | ~8.5GB | Docker 内部存储（仅 Docker 部署需要） |

---

## 方式一：本地运行

适合开发者或想直接修改代码的用户。不需要 Docker。

### Step 1: 安装 Ollama

1. 访问 https://ollama.com 下载 Ollama 安装包
2. 运行安装程序，按默认选项安装即可
3. 安装完成后，Ollama 会自动启动并在后台运行

**验证安装：**

打开终端（CMD / PowerShell / Terminal），执行：

```bash
ollama --version
# 应输出类似: ollama version 0.20.7
```

### Step 2: 下载 LLM 模型

```bash
# 下载 qwen2.5:3b 模型（约 1.9GB，下载时间取决于网速）
ollama pull qwen2.5:3b
```

**验证模型：**

```bash
ollama list
# 应显示:
# NAME          ID           SIZE    MODIFIED
# qwen2.5:3b    357c53fb...  1.9GB   ...
```

**测试模型：**

```bash
ollama run qwen2.5:3b "你好"
# 应输出一段中文回复
```

### Step 3: 克隆项目

```bash
git clone https://github.com/Soilder-revlotion/Gaokao-Volunteer-AI-Assistant.git
cd Gaokao-Volunteer-AI-Assistant
```

如果没有 Git，也可以直接从 GitHub 下载 ZIP 解压。

### Step 4: 安装 Python 依赖

```bash
# 使用清华镜像加速下载
pip install flask==3.1.1 sentence-transformers==3.0.1 faiss-cpu==1.9.0 numpy requests -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**各依赖的作用：**

| 包名 | 作用 |
|------|------|
| flask | Web 框架，提供 HTTP 接口 |
| sentence-transformers | 加载 Embedding 模型，将文本转为向量 |
| faiss-cpu | 向量相似度检索库 |
| numpy | 数值计算基础库 |
| requests | HTTP 客户端，调用 Ollama API |

### Step 5: 准备 Embedding 模型

Embedding 模型用于将文本转为 768 维向量。首次运行时会自动从 HuggingFace 下载。

**如果网络正常（能访问 HuggingFace）：**

直接跳到 Step 6，首次运行时自动下载。

**如果网络受限（国内常见）：**

设置 HuggingFace 镜像：

```bash
# Windows CMD
set HF_ENDPOINT=https://hf-mirror.com

# Windows PowerShell
$env:HF_ENDPOINT = "https://hf-mirror.com"

# Linux/macOS
export HF_ENDPOINT=https://hf-mirror.com
```

或手动下载模型到指定路径：

```bash
# 使用 ModelScope 下载
pip install modelscope -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "from modelscope import snapshot_download; snapshot_download('damo/nlp_gte_sentence-embedding_chinese-base', cache_dir='D:/models/text2vec')"
```

模型默认路径: `D:/models/text2vec/damo/nlp_gte_sentence-embedding_chinese-base/`

如果模型在其他路径，修改 `scripts/config.py` 中的 `MODEL_LOCAL_PATH`。

### Step 6: 准备数据文件

确保 `data/` 目录下有以下文件：

```
data/
├── gaokao_qa_all.json            # 合并后的 QA 数据 (70827条)
├── eol_scores.json               # 录取分数线 (31366条)
├── shanghairanking_cleaned.json  # 软科排名
├── shanghai_subject_ranking.json # 专业排名
├── employment_data.json          # 就业数据
├── manual_schools.json           # 手动数据
└── gaokao_policy_qa.json         # 政策问答
```

这些文件已包含在项目中，无需额外下载。

### Step 7: 构建 FAISS 索引

首次运行需要构建向量索引（约需 2-5 分钟）：

```bash
python scripts/03_build_rag.py
```

构建完成后，`D:/gaokao_db/` 目录下会生成：
- `gaokao.index` — FAISS 索引文件（~222MB）
- `metadata.json` — 元数据文件

### Step 8: 启动 Web 服务

```bash
python scripts/05_web.py
```

启动成功后会显示：

```
正在加载依赖...
正在加载 Embedding 模型...
正在加载向量索引...
就绪，知识库共 70827 条数据，分数线 31366 条

启动 Web 服务...
访问地址: http://localhost:5000
```

### Step 9: 使用

打开浏览器访问 http://localhost:5000

- **聊天模式**: 在输入框输入问题，按回车或点击发送
- **智能推荐**: 点击"智能推荐"标签，输入分数、省份、科类
- **CSV 导出**: 在推荐结果页面点击"导出 CSV"

---

## 方式二：Docker 部署

适合想一键部署、不想手动配置 Python 环境的用户。详细步骤见 [DEPLOYMENT.md](DEPLOYMENT.md)。

### 快速启动（已有 Docker Desktop + Ollama）

```bash
# 1. 确保 Ollama 监听所有接口（Docker 容器需要通过网络访问 Ollama）
#    Windows PowerShell（以管理员身份运行）:
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0:11434', 'User')
# 然后重启 Ollama（关闭并重新打开 Ollama 应用）

# 2. 克隆项目并进入目录
git clone https://github.com/Soilder-revlotion/Gaokao-Volunteer-AI-Assistant.git
cd Gaokao-Volunteer-AI-Assistant

# 3. 构建 Docker 镜像（首次约需 30-90 分钟）
docker compose build

# 4. 启动容器
docker compose up -d

# 5. 访问 http://localhost:5000
```

### Docker 部署 vs 本地运行

| 对比项 | 本地运行 | Docker 部署 |
|--------|---------|------------|
| 环境配置 | 需要手动安装 Python 依赖 | 一键启动，无需配置 |
| 代码修改 | 直接修改立即生效 | 需挂载 volume 或重新构建 |
| 启动速度 | 快 | 首次构建慢，之后快 |
| 磁盘占用 | 较小 | 额外 8.5GB 镜像 |
| 隔离性 | 与系统共享 Python 环境 | 完全隔离 |

---

## API 接口

### GET /

Web 界面首页。

### POST /ask

智能问答接口。

**请求：**

```json
{
  "question": "清华大学怎么样"
}
```

**响应：**

```json
{
  "answer": "清华大学在教育界享有极高的声誉..."
}
```

**错误响应：**

```json
{
  "error": "无法连接到 Ollama，请确保 Ollama 正在运行"
}
```

### POST /recommend

智能推荐接口。

**请求：**

```json
{
  "score": 550,
  "province": "江苏",
  "category": "物理类"
}
```

**参数说明：**

| 参数 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| score | int | 高考分数 | 0-750 |
| province | string | 省份 | 全国 31 个省市自治区 |
| category | string | 科类 | 物理类、历史类、理科、文科、综合类 |

**响应：**

```json
{
  "user_rank": 78432,
  "chong": [
    {
      "school": "南京信息工程大学",
      "min_score": 551,
      "min_rank": 82435,
      "batch": "本科批",
      "soft_rank": 1234,
      "details": [
        {"batch": "本科批", "min_score": 551, "min_rank": 82435},
        {"batch": "提前批", "min_score": 548, "min_rank": 85000}
      ]
    }
  ],
  "wen": [...],
  "bao": [...]
}
```

### POST /export

导出推荐结果为 CSV 文件。请求参数同 `/recommend`，响应为 CSV 文件下载。

---

## 项目结构

```
高考志愿AI助手/
│
├── data/                                    # 数据文件目录
│   ├── gaokao_qa_all.json                   # 合并后的 QA 数据 (70827条)
│   │   ├── 来源: 软科排名 + 分数线 + 专业排名 + 就业 + 政策
│   │   ├── 格式: [{"question": "...", "answer": "..."}, ...]
│   │   └── 用途: RAG 知识库的数据源
│   │
│   ├── eol_scores.json                      # 录取分数线数据 (31366条)
│   │   ├── 来源: 掌上高考网站爬取
│   │   ├── 字段: school, province, category, year, batch, min_score, min_rank
│   │   └── 用途: 智能推荐的核心数据
│   │
│   ├── shanghairanking_cleaned.json         # 软科中国大学排名 (589所)
│   │   ├── 来源: 软科官网爬取
│   │   └── 用途: 学校排名、学校类型（综合/理工/师范等）
│   │
│   ├── shanghai_subject_ranking.json        # 软科专业排名 (4924条)
│   │   ├── 来源: 软科官网爬取
│   │   └── 用途: 各学校的专业排名信息
│   │
│   ├── employment_data.json                 # 就业数据 (575所大学)
│   │   ├── 来源: 各高校就业质量报告
│   │   └── 用途: 就业率、考研率、出国率等
│   │
│   ├── manual_schools.json                  # 手动整理的问答 (15条)
│   │   └── 用途: 补充特殊学校的详细信息
│   │
│   └── gaokao_policy_qa.json                # 政策问答 (27条)
│       └── 用途: 平行志愿、投档线、征集志愿等政策解释
│
├── scripts/                                 # Python 脚本目录
│   ├── config.py                            # 集中配置文件
│   │   ├── OLLAMA_URL: Ollama API 地址
│   │   ├── OLLAMA_MODEL: 使用的模型名
│   │   ├── DB_PATH: FAISS 索引路径
│   │   ├── MODEL_LOCAL_PATH: Embedding 模型路径
│   │   └── 所有配置支持环境变量覆盖
│   │
│   ├── 03_build_rag.py                      # 构建 FAISS 向量索引
│   │   ├── 读取 gaokao_qa_all.json
│   │   ├── 用 Embedding 模型将每条 QA 转为 768 维向量
│   │   ├── 构建 FAISS 索引并保存到 D:/gaokao_db/
│   │   └── 首次运行约需 2-5 分钟
│   │
│   ├── 04_query.py                          # 命令行查询工具
│   │   └── 用于测试 RAG 效果，不启动 Web 服务
│   │
│   ├── 05_web.py                            # Web 界面主程序
│   │   ├── Flask 路由: /, /ask, /recommend, /export
│   │   ├── direct_query(): 正则精确匹配
│   │   ├── vector_search(): FAISS 向量检索
│   │   ├── estimate_rank(): 分段线性插值位次估算
│   │   └── recommend_schools(): 智能推荐算法
│   │
│   ├── clean_data.py                        # 数据清洗脚本
│   │   └── 清洗原始爬取数据，转换为标准 QA 格式
│   │
│   ├── run_full_pipeline.py                 # 一键全自动管道
│   │   └── 政策QA生成 + 数据爬取 + 清洗 + 索引构建
│   │
│   └── scrape_beijing.py                    # 北京分数线数据爬取
│       └── 单独爬取北京地区的特殊数据格式
│
├── templates/                               # 前端模板目录
│   └── index.html                           # 单页应用
│       ├── 极简白风格（类 ChatGPT）
│       ├── 聊天模式 + 智能推荐 两个标签页
│       ├── 响应式设计，支持手机访问
│       └── 纯原生 HTML/CSS/JS，无框架依赖
│
├── Dockerfile                               # Docker 镜像构建文件
│   ├── 基础镜像: python:3.12-slim
│   ├── 安装 Python 依赖
│   ├── 复制应用代码
│   └── 暴露端口 5000
│
├── docker-compose.yml                       # Docker 编排文件
│   ├── 定义 gaokao-web 容器
│   ├── 挂载数据目录和代码目录
│   └── 配置 Ollama 连接地址
│
├── requirements.txt                         # Python 依赖清单
│   └── flask, sentence-transformers, faiss-cpu, numpy, requests
│
├── .dockerignore                            # Docker 忽略文件
│   └── 排除 .git, __pycache__, cookies/ 等
│
├── README.md                                # 项目说明文档（本文件）
│
└── DEPLOYMENT.md                            # Docker 部署详细指南
```

---

## 数据说明

### 数据来源

| 来源 | 网址 | 数据内容 | 采集方式 |
|------|------|---------|---------|
| 掌上高考 | gaokao.eol.cn | 各大学各省份录取分数线 | Playwright 爬虫 |
| 软科排名 | shanghairanking.cn | 中国大学排名、专业排名 | Playwright 爬虫 |
| 各高校官网 | 各大学就业信息网 | 就业质量报告数据 | 手动整理 |
| 阳光高考 | gaokao.chsi.com.cn | 政策规则 | 手动整理 |

### 数据量统计

| 数据源 | 文件 | 大学数 | 记录数 | 生成 QA 数 |
|--------|------|--------|--------|-----------|
| 软科排名 | shanghairanking_cleaned.json | 589 | 589 | 1864 |
| 录取分数线 | eol_scores.json | 407 | 31366 | 62708 |
| 专业排名 | shanghai_subject_ranking.json | — | 4924 | 4924 |
| 就业数据 | employment_data.json | 575 | 575 | 1098 |
| 手动数据 | manual_schools.json | — | 15 | 15 |
| 政策问答 | gaokao_policy_qa.json | — | 27 | 27 |
| **合计** | — | — | — | **70827** |

### 数据字段说明

#### eol_scores.json（录取分数线）

```json
{
  "school": "清华大学",
  "province": "河南",
  "category": "理科",
  "year": 2025,
  "batch": "本科一批",
  "min_score": 685,
  "min_rank": 123
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| school | string | 学校名称 |
| province | string | 招生省份 |
| category | string | 科类（物理类/历史类/理科/文科/综合类） |
| year | int | 年份（2021-2025） |
| batch | string | 批次（本科一批/本科批/提前批等） |
| min_score | int/string | 最低分（部分数据为 "-"） |
| min_rank | int/string | 最低位次（部分数据为 "-"） |

> **注意**: 部分高分段学校的数据源未提供位次信息，`min_rank` 为 `"-"`。系统在推荐时会自动过滤这些无效数据（共 308 条）。

---

## 年度数据更新

每年高考后（6-7月），录取分数线数据会更新。更新步骤：

### 方式一：一键更新（推荐）

```bash
python scripts/run_full_pipeline.py
```

该脚本会自动执行：
1. 生成政策问答数据
2. 爬取最新的录取分数线
3. 清洗和合并数据
4. 重建 FAISS 索引

### 方式二：分步更新

```bash
# 1. 爬取最新数据（需要先登录获取 Cookie）
python scripts/01_login_save_cookies.py gaokao
python scripts/02_scrape_data.py

# 2. 清洗数据
python scripts/clean_data.py

# 3. 重建 FAISS 索引
python scripts/03_build_rag.py
```

### 方式三：手动添加数据

编辑 `data/manual_schools.json`，按格式添加新的问答数据：

```json
{
  "question": "某某大学2025年在河南的录取分数线是多少？",
  "answer": "某某大学2025年在河南理科本科一批的最低分为XXX分，最低位次为XXXXX位。"
}
```

然后重建索引：

```bash
python scripts/03_build_rag.py
```

---

## 开发历程

### 第一阶段：查询质量提升

**目标**: 提高问答的准确性和回答质量

**工作内容**:
- 将 LLM 从 qwen2:1.5b 升级到 qwen2.5:3b（参数量翻倍，中文能力显著提升）
- 创建统一配置文件 `config.py`，所有脚本共用同一份配置
- 优化 prompt 模板，让 LLM 更准确地引用参考资料
- 支持环境变量覆盖配置，为后续 Docker 部署做准备

**关键决策**:
- 选择 3b 而非 7b：16GB 内存的电脑运行 7b 模型会 OOM，3b 是平衡点
- 使用 Q4_K_M 量化：在保持回答质量的同时大幅减少内存占用

### 第二阶段：Web 界面优化

**目标**: 提供美观易用的 Web 界面

**工作内容**:
- 设计极简白风格界面（类 ChatGPT）
- 实现聊天模式和智能推荐两个功能标签页
- 修复 `index` 变量被 Flask 路由函数 `def index()` 覆盖的 bug
- 添加错误处理，API 返回 JSON 而非 HTML 错误页面

**关键修复**:
- `index` 变量名冲突：FAISS 索引变量和 Flask 路由函数同名，导致加载索引时被覆盖为函数对象 → 改名为 `faiss_index`

### 第三阶段：数据扩展

**目标**: 大幅扩充知识库数据量

**工作内容**:
- 爬取 435 所大学的录取分数线数据（掌上高考网站）
- QA 数量从 32186 条增至 70827 条（+120%）
- 数据覆盖全国 31 个省市自治区
- 添加北京地区特殊数据格式的爬取脚本

**技术挑战**:
- 掌上高考网站有反爬机制 → 使用 Playwright 模拟真人操作
- 数据量大导致爬取时间长 → 添加真人延迟，分批爬取
- 不同省份的数据格式不一致 → 统一清洗为标准格式

### 第四阶段：智能推荐

**目标**: 基于位次法实现智能推荐功能

**工作内容**:
- 实现位次法 v1：简单线性公式
- 优化为 v2：查表 + 线性插值
- 优化为 v3：分段线性插值 + 主批次优先 + 动态阈值
- 添加专业组详情展示（同一学校不同批次）
- 添加 CSV 导出功能

**算法演进**:
- v1: 位次 = 分数 × 系数 → 误差大
- v2: 查表 + 简单插值 → 边界情况处理不好
- v3: 分段线性插值 + 主批次优先 + 动态阈值 → 准确性大幅提升

### 第五阶段：部署分发

**目标**: 实现一键部署，方便分发和使用

**工作内容**:
- 创建 Dockerfile 和 docker-compose.yml
- 修改 config.py 支持环境变量覆盖
- 解决 Docker 网络代理、Ollama 连接等问题
- 编写详细的部署文档
- 修复推荐算法中的数据质量问题

**踩坑记录**:
- Docker 构建时 pip 下载超时 → 通过 ARG 传递代理
- ollama 镜像拉不动 → 改用宿主机 Ollama
- 容器连不上 Ollama → 设置 OLLAMA_HOST=0.0.0.0
- 容器内请求走代理 → 清空容器代理环境变量
- 推荐功能报错 → 过滤 min_rank 为 "-" 的无效数据
- 代码修改不生效 → 挂载 scripts/ 目录为 volume

---

## 常见问题

### 安装和配置

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `pip install` 下载慢 | 默认源在国外 | 使用清华镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| HuggingFace 模型下载失败 | 国内无法访问 HuggingFace | 设置 `HF_ENDPOINT=https://hf-mirror.com`，或用 ModelScope 下载 |
| Ollama 安装后无法运行 | 可能需要重启终端 | 关闭终端重新打开，或重启电脑 |
| `ollama` 命令找不到 | 未加入 PATH | 重新安装 Ollama，或手动添加到系统 PATH |

### 运行问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Ollama 连不上 | Ollama 未启动 | 打开 Ollama 应用，或执行 `ollama serve` |
| 回答质量差 | 模型太小或数据不足 | 升级到 qwen2.5:7b（需 16GB+ 内存），或补充数据 |
| 回答较慢（>10秒） | CPU 推理，正常现象 | 3b 模型在 CPU 上约 3-10 秒，7b 约 10-30 秒 |
| 推荐结果为空 | 该省份+科类无数据 | 检查 `data/eol_scores.json` 是否有对应数据 |
| FAISS 索引加载失败 | 索引文件损坏或不存在 | 重新运行 `python scripts/03_build_rag.py` |
| 端口 5000 被占用 | 其他程序占用了端口 | 关闭占用端口的程序，或修改 `05_web.py` 中的端口号 |

### Docker 问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `docker compose build` 超时 | 网络问题，pip 下载失败 | 配置代理或使用国内镜像 |
| 容器连不上 Ollama | Ollama 只监听 127.0.0.1 | 设置 `OLLAMA_HOST=0.0.0.0:11434` |
| 容器内请求 502 | 容器走了代理 | docker-compose.yml 中清空代理环境变量 |
| 代码修改不生效 | 代码 bake 在镜像里 | 挂载 scripts/ 目录为 volume |
| 镜像太大（8.5GB） | PyTorch + CUDA 库 | 正常现象，可使用多阶段构建减小体积 |

### 数据问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 推荐报错 `invalid literal for int()` | 数据中 min_rank 为 "-" | 已修复：自动过滤无效数据 |
| 某些省份无推荐结果 | 该省份无 2025 年数据 | 检查 `data/eol_scores.json` 的 year 字段 |
| 分数线数据过旧 | 数据是往年的 | 运行 `python scripts/run_full_pipeline.py` 更新 |

---

## License

MIT

---

## 致谢

- [Ollama](https://ollama.com) — 本地 LLM 运行时
- [FAISS](https://github.com/facebookresearch/faiss) — 向量检索库
- [sentence-transformers](https://www.sbert.net/) — Embedding 框架
- [Flask](https://flask.palletsprojects.com/) — Web 框架
- [通义千问](https://qwenlm.github.io/) — 中文大语言模型
