# AIReport - 智能 AI 动态速报生成系统

## 🌟 项目简介

AIReport 是一个自动化的 AI 前沿动态报告生成系统，集成了：
- 🕷️ 多源新闻爬取（量子位、OpenAI、Google、Anthropic 等）
- 🤖 智能新闻分析（GeminiAIReportAgent）
- 📝 高质量报告生成

## 🎯 核心功能

### 1. 多源数据爬取
- **新闻媒体**：量子位等 AI 科技媒体
- **官方博客**：OpenAI、Anthropic、Google AI、Meta、Microsoft 等
- **支持增量更新**：避免重复爬取
- **并发爬取**：提高效率

### 2. 智能新闻处理（GeminiAIReportAgent）⭐

**四步处理流程：**

#### 【第一步】过滤 (Filtering)
剔除与 AI 核心技术进展无关的噪音信息：
- ✓ 保留技术进展、关键领域、权威来源
- ✗ 剔除商业金融、市场分析、二次解读、信源不明

#### 【第二步】归类 (Clustering)
利用语义相似度将同一事件的新闻聚合：
- 识别"同一技术事件 / 模型版本 / 产品发布 / 关键论文"
- 例如："GPT-5 发布"、"Llama 3.1 开源"等

#### 【第三步】去重 (Deduplication)
每个事件只保留最权威的一条新闻：
- 优先级：官方信源 > 核心人员解读 > 权威媒体 > 社交转述

#### 【第四步】排序 (Ranking)
多维度价值评分（S/A/B/C 四级）：
- **技术影响力** (50%权重)：1-5分
- **行业影响范围** (30%权重)：1-5分
- **热度** (20%权重)：基于报道数量

### 3. 报告生成
- 基于模板生成 Markdown 格式报告
- 包含深度解读和趋势分析
- 自动引用原始来源

---

## 🚀 快速开始

### 前置要求

- Python 3.8+
- MySQL 或 PostgreSQL 数据库
- Gemini API Key（用于智能分析）

### 安装步骤

1. **克隆项目**

```bash
git clone <repository_url>
cd AIReport
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置数据库**

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE ai_report CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 初始化表结构
python -c "from database.init_db import init_db; import asyncio; asyncio.run(init_db())"
```

4. **配置环境变量**

```bash
# 复制配置模板
cp env.example .env

# 编辑 .env 文件
nano .env
```

关键配置：

```env
# 数据库配置
DB_DIALECT=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=ai_report

# Gemini API 配置
REPORT_ENGINE_API_KEY=your_gemini_api_key
REPORT_ENGINE_MODEL_NAME=gemini-2.0-flash-exp
```

**获取 Gemini API Key**：https://aistudio.google.com/app/apikey

---

## 📖 使用指南

### 方式一：使用智能 Agent（推荐）⭐

```bash
# 完整流程：爬取 + 智能分析
python main.py --use-agent --days 3

# 仅智能分析（使用已有数据）
python main.py --skip-crawl --use-agent --days 3

# 保存中间处理结果（用于调试）
python main.py --skip-crawl --use-agent --days 3 --save-intermediate
```

**处理流程：**
```
数据库 → 过滤 → 归类 → 去重 → 排序 → 报告生成
       (剔除噪音) (事件聚合) (权威筛选) (评分分级)
```

**输出文件：**
- 最终报告：`final_reports/AI_Report_YYYY-MM-DD_HHMMSS.md`
- 中间结果（可选）：`final_reports/intermediate/*.json`

### 方式二：使用基础生成器

```bash
# 完整流程
python main.py --days 3

# 仅生成报告
python main.py --skip-crawl --days 3
```

### 仅爬取新闻

```bash
# 爬取所有来源
python main.py --skip-report --days 7

# 爬取特定来源
python main.py --skip-report --crawler openai --days 7
python main.py --skip-report --crawler qbitai --days 7

# 并发爬取（更快）
python main.py --skip-report --concurrent --max-concurrent 5
```

---

## 🎯 命令参数详解

### 基本参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--days N` | 获取最近N天的数据 | 7 |
| `--skip-crawl` | 跳过爬取，仅生成报告 | False |
| `--skip-report` | 跳过报告生成，仅爬取 | False |

### Agent 相关

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--use-agent` | 使用智能 Agent（推荐） | False |
| `--save-intermediate` | 保存中间处理结果 | False |

### 爬虫相关

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--crawler NAME` | 指定爬虫：all, qbitai, openai, anthropic, google, etc. | all |
| `--concurrent` | 启用并发爬取 | False |
| `--max-concurrent N` | 最大并发数 | 3 |
| `--no-incremental` | 禁用增量更新 | False |
| `--use-proxy` | 启用代理池 | False |

---

## 🧪 测试 Agent 功能

### 快速测试

```bash
cd analysis

# 测试完整流程
python test_agent.py --test full

# 测试所有步骤
python test_agent.py --test all

# 测试单个步骤
python test_agent.py --test filter      # 过滤
python test_agent.py --test cluster     # 归类
python test_agent.py --test deduplicate # 去重
python test_agent.py --test rank        # 排序
```

### 直接运行 Agent

```bash
cd analysis
python gemini_agent.py
```

---

## 📊 评分体系说明

### S级（FinalScore ≥ 4.2）
- 🔥 范式转换级别的技术突破
- 🌍 全行业影响
- 📈 极高热度（>20篇报道）

**示例**：GPT-5 发布、Transformer 架构提出

### A级（3.5 ≤ FinalScore < 4.2）
- 💎 重大技术突破
- 🎯 多领域影响
- 📊 高热度（11-20篇报道）

**示例**：Llama 3.1 开源、Gemini 2.0 发布

### B级（2.8 ≤ FinalScore < 3.5）
- ⚡ 显著技术改进
- 🎨 特定领域影响
- 📋 中等热度（6-10篇报道）

**示例**：新的优化算法、实用工具发布

### C级（FinalScore < 2.8）
- 🔧 常规优化或微小改进
- 🎪 特定任务或小众场景
- 📄 低热度（1-5篇报道）

**示例**：版本小更新、增量式改进

---

## 📁 项目结构

```
AIReport/
├── analysis/                    # 分析和报告生成
│   ├── gemini_agent.py         # 🤖 智能 Agent（核心）
│   ├── generator.py            # 基础报告生成器
│   ├── test_agent.py           # Agent 测试脚本
│   ├── AGENT_README.md         # Agent 详细文档
│   └── templates/              # 报告模板
│       └── AIReport_example.md
├── crawler/                     # 爬虫模块
│   ├── base_scraper.py         # 爬虫基类
│   ├── qbitai_scraper.py       # 量子位爬虫
│   ├── openai_scraper.py       # OpenAI 爬虫
│   ├── anthropic_scraper.py    # Anthropic 爬虫
│   ├── google_ai_scraper.py    # Google AI 爬虫
│   └── ...
├── database/                    # 数据库模块
│   ├── models.py               # 数据模型
│   ├── db_session.py           # 数据库会话
│   └── init_db.py              # 数据库初始化
├── final_reports/              # 生成的报告
│   ├── AI_Report_*.md          # 最终报告
│   └── intermediate/           # 中间结果（可选）
├── config.py                   # 配置管理
├── main.py                     # 主程序入口
├── requirements.txt            # Python 依赖
├── env.example                 # 配置模板
├── AGENT_QUICKSTART.md         # 快速开始指南
└── README_AGENT.md             # 本文件
```

---

## 🔧 配置说明

### 数据库配置

支持 MySQL 和 PostgreSQL：

```env
# MySQL 配置
DB_DIALECT=mysql
DB_PORT=3306

# PostgreSQL 配置
DB_DIALECT=postgresql
DB_PORT=5432
```

### Gemini API 配置

```env
# 主配置（推荐）
REPORT_ENGINE_API_KEY=your_api_key
REPORT_ENGINE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
REPORT_ENGINE_MODEL_NAME=gemini-2.0-flash-exp

# 向后兼容配置
GEMINI_API_KEY=your_api_key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL_NAME=gemini-2.0-flash-exp
```

### 推荐模型

| 模型 | 特点 | 适用场景 |
|------|------|----------|
| `gemini-2.0-flash-exp` | 速度快、成本低 | Agent 批量处理（推荐） |
| `gemini-2.0-pro-exp` | 质量高、平衡性好 | 高质量报告生成 |
| `gemini-exp-1206` | 最新实验版本 | 尝鲜测试 |

---

## 💡 使用技巧

### 1. 首次使用

```bash
# 查看 Agent 的处理效果
python main.py --skip-crawl --use-agent --days 3 --save-intermediate

# 检查中间结果
ls -lh final_reports/intermediate/
```

### 2. 日常使用

```bash
# 每天运行一次，生成当日报告
python main.py --use-agent --days 1
```

### 3. 调试优化

```bash
# 使用测试脚本调试单个步骤
cd analysis
python test_agent.py --test filter
python test_agent.py --test cluster
```

### 4. 成本控制

- 使用 `gemini-2.0-flash-exp` 模型（默认）
- 调整 `--days` 参数，减少处理的新闻数量
- 使用 `--skip-crawl` 避免重复爬取

### 5. 质量优先

```env
# 在 .env 中使用更强大的模型
REPORT_ENGINE_MODEL_NAME=gemini-2.0-pro-exp
```

---

## ❓ 常见问题

### Q1: Agent 和基础生成器有什么区别？

**Agent 的优势：**
- ✅ 智能过滤噪音信息
- ✅ 语义事件聚类
- ✅ 权威来源去重
- ✅ 多维度价值评分
- ✅ 多轮质量检查

**基础生成器特点：**
- ✅ 速度快（~10秒）
- ✅ 成本低
- ❌ 无智能处理

### Q2: 报告生成需要多长时间？

- **基础生成器**：~10秒
- **Agent**：
  - 50条新闻：2-3分钟
  - 200条新闻：5-8分钟

### Q3: 如何调整过滤规则？

编辑 `analysis/gemini_agent.py` 中的 `step1_filter` 方法的提示词。

### Q4: 如何自定义评分权重？

编辑 `analysis/gemini_agent.py` 中的评分计算公式：

```python
item.final_score = (
    item.tech_impact * 0.5 +      # 技术影响力权重
    item.industry_scope * 0.3 +   # 行业范围权重
    item.hype_score * 0.2         # 热度权重
)
```

### Q5: 遇到 API 错误怎么办？

1. 检查 API Key 是否正确
2. 检查网络连接
3. 检查 API 配额
4. 查看错误日志：`final_reports/logs/`

### Q6: 如何添加新的数据源？

1. 在 `crawler/` 目录下创建新的爬虫类
2. 继承 `BaseScraper` 基类
3. 实现 `fetch_articles` 方法
4. 在 `crawler_registry.py` 中注册

---

## 📚 详细文档

- **Agent 详细使用指南**：`analysis/AGENT_README.md`
- **快速开始指南**：`AGENT_QUICKSTART.md`
- **爬虫架构设计**：`crawler/ARCHITECTURE.md`
- **爬虫快速参考**：`crawler/QUICK_REFERENCE.md`

---

## 🤝 贡献指南

欢迎贡献代码和提出建议！

**改进方向：**
- 🎯 优化 Agent 提示词
- 🕷️ 添加更多数据源
- ⚡ 实现并发批处理
- 🤖 支持更多 LLM 模型
- 📊 添加更多评分维度
- 🌐 多语言支持

**提交流程：**
1. Fork 项目
2. 创建功能分支
3. 提交代码
4. 发起 Pull Request

---

## 📄 许可证

[根据项目实际情况填写]

---

## 📞 联系方式

- **Issues**：[提交 Issue](项目 Issues 页面)
- **Pull Requests**：[提交 PR](项目 PR 页面)
- **Email**：[项目维护者邮箱]

---

## 🎉 致谢

感谢所有贡献者和使用者！

特别感谢：
- Google Gemini API
- 量子位等媒体提供的优质内容
- OpenAI、Anthropic、Google 等公司的开放技术博客

---

**祝您使用愉快！如有问题欢迎反馈。** 🚀

