# GeminiAIReportAgent 快速开始指南

## 🚀 5分钟快速开始

### 第一步：配置 Gemini API

1. 获取 Gemini API Key：
   - 访问：https://aistudio.google.com/app/apikey
   - 创建并复制 API Key

2. 配置环境变量：

```bash
# 复制配置文件
cp env.example .env

# 编辑 .env 文件，填入你的 API Key
REPORT_ENGINE_API_KEY=your_gemini_api_key_here
REPORT_ENGINE_MODEL_NAME=gemini-2.0-flash-exp
```

### 第二步：运行 Agent

```bash
# 完整流程：爬取新闻 + 智能分析生成报告
python main.py --use-agent --days 3

# 或者仅使用已有数据生成报告（跳过爬取）
python main.py --skip-crawl --use-agent --days 3
```

### 第三步：查看报告

报告保存在 `final_reports/AI_Report_YYYY-MM-DD_HHMMSS.md`

---

## 📊 Agent 处理流程

```
数据库新闻
    ↓
【第一步】过滤 (Filtering)
    ↓ 剔除商业、金融、二次解读等噪音
【第二步】归类 (Clustering)  
    ↓ 将同一事件的新闻聚合
【第三步】去重 (Deduplication)
    ↓ 每个事件只保留最权威的一条
【第四步】排序 (Ranking)
    ↓ S/A/B/C 四级评分
【第五步】报告生成
    ↓
高质量 AI 前沿动态速报
```

---

## ⚙️ 命令参数说明

```bash
# 基本用法
python main.py --use-agent                    # 使用 Agent 生成报告
python main.py --use-agent --days 7           # 处理最近 7 天的数据
python main.py --use-agent --save-intermediate # 保存中间结果（用于调试）

# 跳过爬取
python main.py --skip-crawl --use-agent       # 仅生成报告，不爬取新数据

# 仅爬取
python main.py --skip-report                  # 仅爬取，不生成报告
```

---

## 🧪 测试 Agent 功能

### 测试单个步骤

```bash
cd analysis

# 测试数据获取
python test_agent.py --test fetch

# 测试过滤功能
python test_agent.py --test filter

# 测试归类功能
python test_agent.py --test cluster

# 测试去重功能
python test_agent.py --test deduplicate

# 测试排序功能
python test_agent.py --test rank

# 测试完整流程
python test_agent.py --test full
```

### 测试所有步骤

```bash
cd analysis
python test_agent.py --test all
```

---

## 📁 输出文件说明

### 最终报告

- 路径：`final_reports/AI_Report_YYYY-MM-DD_HHMMSS.md`
- 格式：Markdown
- 内容：高质量的 AI 前沿动态速报

### 中间结果（可选）

使用 `--save-intermediate` 时会生成：

```
final_reports/intermediate/
├── 01_filtered_YYYY-MM-DD_HHMMSS.json    # 过滤后的新闻
├── 02_clustered_YYYY-MM-DD_HHMMSS.json   # 归类后的新闻
├── 03_deduplicated_YYYY-MM-DD_HHMMSS.json # 去重后的新闻
└── 04_ranked_YYYY-MM-DD_HHMMSS.json      # 排序后的新闻
```

每个 JSON 文件包含完整的处理信息，可用于：
- 调试和优化
- 分析 Agent 的处理效果
- 调整提示词和参数

---

## 🎯 评分体系说明

### S级（FinalScore ≥ 4.2）
- 范式转换级别的技术突破
- 全行业影响
- 极高热度（>20篇报道）

**示例**：GPT-5 发布、Transformer 架构提出

### A级（3.5 ≤ FinalScore < 4.2）
- 重大技术突破
- 多领域影响
- 高热度（11-20篇报道）

**示例**：Llama 3.1 开源、Gemini 2.0 发布

### B级（2.8 ≤ FinalScore < 3.5）
- 显著技术改进
- 特定领域影响
- 中等热度（6-10篇报道）

**示例**：新的优化算法、实用工具发布

### C级（FinalScore < 2.8）
- 常规优化或微小改进
- 特定任务或小众场景
- 低热度（1-5篇报道）

**示例**：版本小更新、增量式改进

---

## 💡 使用技巧

### 1. 首次使用

```bash
# 查看中间结果，了解 Agent 的处理效果
python main.py --skip-crawl --use-agent --days 3 --save-intermediate
```

### 2. 日常使用

```bash
# 默认配置即可，无需保存中间结果
python main.py --use-agent --days 3
```

### 3. 成本控制

使用 `gemini-2.0-flash-exp` 模型（默认）：
- 速度快
- 成本低
- 适合大批量处理

### 4. 质量优先

在 `.env` 中修改模型：

```env
REPORT_ENGINE_MODEL_NAME=gemini-2.0-pro-exp
```

---

## ❓ 常见问题

### Q1: 报告生成需要多长时间？

**A**: 取决于新闻数量和模型：
- 50条新闻 + gemini-2.0-flash-exp：约 2-3 分钟
- 200条新闻 + gemini-2.0-flash-exp：约 5-8 分钟

### Q2: Agent 和基础生成器有什么区别？

**A**: Agent 增加了智能处理流程：
- ✓ 过滤噪音信息
- ✓ 事件聚类
- ✓ 权威去重
- ✓ 多维度评分
- ✓ 质量检查

报告质量更高，但处理时间更长。

### Q3: 如何调整过滤规则？

**A**: 修改 `analysis/gemini_agent.py` 中的 `step1_filter` 方法的提示词。

### Q4: 如何调整评分权重？

**A**: 修改 `analysis/gemini_agent.py` 中的评分计算公式：

```python
item.final_score = (
    item.tech_impact * 0.5 +      # 技术影响力权重
    item.industry_scope * 0.3 +   # 行业范围权重
    item.hype_score * 0.2         # 热度权重
)
```

### Q5: 遇到 API 错误怎么办？

**A**: 检查以下几点：
1. API Key 是否正确配置
2. 网络连接是否正常
3. API 配额是否用尽
4. 尝试使用代理或 VPN

### Q6: 如何只处理特定来源的新闻？

**A**: 在 `fetch_articles_from_db` 方法中添加过滤条件：

```python
# 只获取 OpenAI 的新闻
stmt = (
    select(CompanyArticle)
    .where(CompanyArticle.company == "openai")
    .where(CompanyArticle.publish_time >= cutoff_ts)
    .order_by(desc(CompanyArticle.publish_time))
    .limit(limit)
)
```

---

## 📚 更多文档

- **详细使用指南**：`analysis/AGENT_README.md`
- **架构设计**：`crawler/ARCHITECTURE.md`
- **运行指南**：`运行指南.md`

---

## 🤝 反馈与支持

遇到问题或有改进建议？欢迎：
- 提交 Issue
- 提交 Pull Request
- 联系项目维护者

---

## ⚡ 快速参考

```bash
# 最常用的命令
python main.py --use-agent --days 3                           # 完整流程
python main.py --skip-crawl --use-agent --days 3              # 仅生成报告
python main.py --use-agent --days 3 --save-intermediate       # 保存中间结果

# 测试命令
cd analysis && python test_agent.py --test all                # 测试所有功能
cd analysis && python gemini_agent.py                         # 直接运行 Agent
```

---

祝您使用愉快！🎉

