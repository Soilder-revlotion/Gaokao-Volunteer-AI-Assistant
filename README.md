# 高考志愿 AI 助手

> 基于 RAG + 本地模型的高考志愿填报问答系统
> 数据不出网，免费运行，每年可更新数据
> 日期：2026年5月4日

---

## 项目结构

```
D:\Holiday\claude1\高考志愿AI助手\
├── README.md                  ← 本文件
├── cookies\                   ← 登录 Cookie（自动登录用）
├── data\                      ← 数据文件
│   └── manual_schools.json    ← 手动整理的问答数据
├── db\                        ← 向量数据库（自动生成）
├── scripts\                   ← Python 脚本
│   ├── 01_login_save_cookies.py  ← 登录并保存 Cookie
│   ├── 02_scrape_data.py         ← 爬取数据（带真人延迟）
│   ├── 03_build_rag.py           ← 搭建 RAG 知识库
│   ├── 04_query.py               ← 命令行查询
│   ├── 05_web.py                 ← 网页版
│   └── update_data.py            ← 年度数据更新（一键运行）
└── templates\                 ← 网页模板
    └── index.html             ← 前端页面
```

---

## 环境要求（已确认可用）

| 组件                  | 状态    | 说明                        |
| ------------------- | ----- | ------------------------- |
| Python 3.12.2 (64位) | ✅ 已安装 |                           |
| Ollama + qwen2.5:3b | ✅ 已安装 | 本地模型                      |
| pip 清华镜像            | ✅ 可访问 | pypi.tuna.tsinghua.edu.cn |
| Playwright          | ✅ 已安装 | npm 版 1.59.1              |
| hf-mirror           | ✅ 可访问 | HuggingFace 镜像            |
| ModelScope          | ✅ 可访问 | text2vec 模型可下载            |

---

## 第一次使用（完整流程）

### 步骤 1：安装 Python 依赖

在 CMD 中执行：

```bash
cd D:\Holiday\claude1\高考志愿AI助手
pip install chromadb sentence-transformers flask requests -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 步骤 2：下载 Embedding 模型

```bash
pip install modelscope -i https://pypi.tuna.tsinghua.edu.cn/simple
python -c "from modelscope import snapshot_download; snapshot_download('shibing614/text2vec-base-chinese', cache_dir='D:/models/text2vec')"
```

### 步骤 3：搭建 RAG 知识库

```bash
python scripts\03_build_rag.py
```

### 步骤 4：测试

```bash
python scripts\04_query.py
```

输入问题测试：

```
河南考生理科580分能上什么学校？
什么是平行志愿？
```

### 步骤 5：启动网页

```bash
python scripts\05_web.py
```

浏览器打开 `http://localhost:5000`

---

## 年度数据更新流程

每年高考后（6-7月）运行一次，更新数据：

### 方式一：手动更新（推荐先用这个）

1. 编辑 `data/manual_schools.json`，添加新的问答数据
2. 运行 `python scripts\03_build_rag.py` 重建知识库
3. 测试效果

### 方式二：自动爬取

1. 登录网站保存 Cookie：
   
   ```bash
   python scripts\01_login_save_cookies.py gaokao
   ```
2. 爬取数据：
   
   ```bash
   python scripts\02_scrape_data.py
   ```
3. 重建知识库：
   
   ```bash
   python scripts\03_build_rag.py
   ```

### 方式三：一键更新

```bash
python scripts\update_data.py
```

---

## 爬虫防封禁措施

所有爬虫脚本都内置了真人延迟：

| 操作     | 延迟时间        | 说明          |
| ------ | ----------- | ----------- |
| 页面加载后  | 2-5 秒       | 模拟真人阅读      |
| 滚动页面   | 0.5-1.5 秒/次 | 分段滚动，不是一下到底 |
| 点击操作后  | 0.8-2 秒     | 模拟真人点击      |
| 翻页之间   | 3-7 秒       | 模拟真人翻页      |
| 不同网站之间 | 3-7 秒       | 避免连续请求      |

反检测措施：

- 隐藏 Playwright 自动化特征
- 使用真实 User-Agent
- Cookie 持久化，避免频繁登录

---

## 数据来源（已预检可访问性）

| 来源   | 网址                 | 状态         | 用途          |
| ---- | ------------------ | ---------- | ----------- |
| 学信网  | chsi.com.cn        | ✅ 200      | 学历查询        |
| 研招网  | yz.chsi.com.cn     | ✅ 200      | 研究生招生       |
| 软科排名 | shanghairanking.cn | ✅ 200      | 大学排名        |
| 阳光高考 | gaokao.chsi.com.cn | ⚠️ 412 有反爬 | 需要登录+Cookie |
| 掌上高考 | www.gaokao.cn      | ❌ 不可访问     | 无法使用        |

---

## 常见问题

### 网络问题

| 问题               | 解决方案                                                |
| ---------------- | --------------------------------------------------- |
| pip 下载慢          | 用清华镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| HuggingFace 下载不了 | 用 ModelScope 下载模型                                   |
| hf-mirror 返回 404 | 该模型不在 hf-mirror 上，用 ModelScope                      |

### 运行问题

| 问题         | 解决方案                               |
| ---------- | ---------------------------------- |
| Ollama 连不上 | 另开 CMD 运行 `ollama serve`           |
| 回答质量差      | 增加 `data/manual_schools.json` 中的数据 |
| 回答较慢       | CPU 推理正常，7B 约 10-30 秒              |
| 模型加载失败     | 检查 ModelScope 是否下载成功               |

### 爬虫问题

| 问题        | 解决方案                               |
| --------- | ---------------------------------- |
| 网站打不开     | 可能需要登录，运行 01_login_save_cookies.py |
| Cookie 过期 | 重新运行登录脚本                           |
| 被封禁       | 增加延迟时间，或换时间段爬取                     |
| 页面结构变了    | 需要更新选择器，手动检查页面                     |

---

## 技术栈

| 组件        | 工具                    | 作用      | 费用  |
| --------- | --------------------- | ------- | --- |
| 向量数据库     | ChromaDB              | 存储和检索知识 | 免费  |
| Embedding | text2vec-base-chinese | 文字转向量   | 免费  |
| 大模型       | Ollama + qwen2.5:3b   | 生成答案    | 免费  |
| 爬虫        | Playwright            | 自动化数据采集 | 免费  |
| 后端        | Flask                 | 提供 API  | 免费  |
| 前端        | HTML + JS             | 用户界面    | 免费  |
