# GeminiAIReportAgent 使用指南

## 概述

`GeminiAIReportAgent` 是一个基于大语言模型的智能新闻处理 Agent，通过多轮语义分析实现：

1. **过滤 (Filtering)** - 剔除与 AI 核心技术进展无关的噪音信息
2. **归类 (Clustering)** - 将描述同一事件的新闻聚合在一起
3. **去重 (Deduplication)** - 保留最权威、信息质量最高的新闻
4. **排序 (Ranking)** - 对新闻进行价值评分（S/A/B/C 四级）
5. **报告生成** - 生成高质量的 AI 前沿动态速报

## 核心特性

### 1. 智能过滤

**保留条件**（逻辑或，满足其一即保留）：
- 技术/能力进展：核心内容是关于 AI 技术、模型、系统、工程或应用能力的具体进展
- 关键领域：明确涉及基础模型、训练/推理方法、数据工程、AI Infra、Agent 框架或相关技术产品
- 权威来源：信息来源为学术论文、官方技术博客、官方产品发布页或 GitHub Release Notes

**剔除条件**（逻辑或，满足其一即剔除）：
- 商业/金融：股价、市值、融资、IPO、估值、财报、收入、用户规模
- 市场分析：投资观点、市场情绪、资本动向、无直接技术关联的商业合作新闻
- 二次解读：个人观点、KOL 长篇分析、无一手信息源的推文总结
- 信源不明：未标注明确来源、来源为匿名论坛或社交群聊截图

### 2. 语义归类

利用大模型的语义理解能力，将描述同一事件的新闻聚合：
- 按"同一技术事件 / 模型版本 / 产品发布 / 关键论文"进行语义归类
- 例如："GPT-5 发布"、"Llama 3.1 开源"、"DeepMind 提出新 AlphaFold 算法"等均属于独立的语义事件
- 每个事件会被分配一个有意义的 `event_id`

### 3. 权威去重

在每个事件中，仅保留一条最权威的新闻。

**保留优先级**（从高到低）：
1. 官方核心信源：官网发布、官方博客、arXiv 论文、GitHub Release
2. 核心人员解读：作者、核心工程师或官方研究员的深度解读
3. 权威技术媒体：对上述信源的深度、快速转述报道
4. 社交媒体/普通转述：优先级最低

### 4. 价值评分

**评分维度**：

1. **技术影响力 (Tech_Impact)** [1-5分]：
   - 5分（范式转换）：提出全新架构或理论，可能改变一个领域的走向
   - 4分（重大突破）：在关键能力上有巨大提升或开源了强大的基础模型
   - 3分（显著改进）：现有方法上的重要改进，或发布了非常有用的工具/框架
   - 2分（常规优化）：性能的小幅提升或常规版本迭代
   - 1分（微小改进）：增量式更新

2. **行业影响范围 (Industry_Scope)** [1-5分]：
   - 5分（全行业）：对几乎所有 AI 应用开发者和公司都产生影响
   - 4分（多领域）：影响多个主要 AI 应用领域
   - 3分（特定领域）：深度影响一个垂直领域
   - 2分（特定任务）：主要影响一个或少数几个具体任务
   - 1分（小众场景）：影响范围非常有限

3. **热度 (Hype_Score)** [1-5分]：
   - 根据同一事件的新闻数量映射：
     - 1-2篇 → 1分
     - 3-5篇 → 2分
     - 6-10篇 → 3分
     - 11-20篇 → 4分
     - >20篇 → 5分

**最终评分计算**：
```
FinalScore = (Tech_Impact × 0.5) + (Industry_Scope × 0.3) + (Hype_Score × 0.2)
```

**评级映射**：
- FinalScore ≥ 4.2 → **S级**
- 3.5 ≤ FinalScore < 4.2 → **A级**
- 2.8 ≤ FinalScore < 3.5 → **B级**
- FinalScore < 2.8 → **C级**

## 使用方法

### 方法一：使用主程序（推荐）

```bash
# 完整流程：爬取 + 智能分析
python main.py --use-agent --days 3

# 仅智能分析（跳过爬取）
python main.py --skip-crawl --use-agent --days 3

# 保存中间结果（用于调试）
python main.py --skip-crawl --use-agent --days 3 --save-intermediate
```

### 方法二：直接运行 Agent

```bash
cd analysis
python gemini_agent.py
```

### 方法三：在代码中使用

```python
import asyncio
from analysis.gemini_agent import GeminiAIReportAgent

async def generate_report():
    # 初始化 Agent
    agent = GeminiAIReportAgent(max_retries=2)
    
    # 运行完整流程
    report_content = await agent.run(
        days=3,  # 获取最近3天的数据
        save_intermediate=True  # 保存中间结果
    )
    
    if report_content:
        print("报告生成成功！")
    else:
        print("报告生成失败")

# 运行
asyncio.run(generate_report())
```

## 配置说明

在 `.env` 文件中配置 Gemini API：

```env
# Gemini API 配置
REPORT_ENGINE_API_KEY=your_gemini_api_key
REPORT_ENGINE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
REPORT_ENGINE_MODEL_NAME=gemini-2.0-flash-exp

# 或者使用简化配置（向后兼容）
GEMINI_API_KEY=your_gemini_api_key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
GEMINI_MODEL_NAME=gemini-2.0-flash-exp
```

推荐使用的模型：
- `gemini-2.0-flash-exp` - 速度快，成本低，适合大批量处理
- `gemini-exp-1206` - 质量高，适合高质量报告生成
- `gemini-2.0-pro-exp` - 平衡速度和质量

## 输出说明

### 最终报告

报告保存在 `final_reports/AI_Report_YYYY-MM-DD_HHMMSS.md`

### 中间结果（可选）

如果使用 `--save-intermediate` 参数，会在 `final_reports/intermediate/` 目录下保存每个步骤的中间结果：

- `01_filtered_*.json` - 过滤后的新闻
- `02_clustered_*.json` - 归类后的新闻
- `03_deduplicated_*.json` - 去重后的新闻
- `04_ranked_*.json` - 排序后的新闻

每个 JSON 文件包含完整的处理信息，可用于调试和分析。

## 性能优化

### 批处理大小

Agent 使用批处理来处理大量新闻，默认批处理大小：
- 过滤：20条/批
- 归类：30条/批
- 去重：按事件分组处理
- 排序：20条/批

如果遇到 API 限流，可以在代码中调整批处理大小：

```python
# 在 gemini_agent.py 中修改
news_items = await self.step1_filter(news_items, batch_size=10)  # 减小批处理大小
```

### 重试机制

Agent 默认每个步骤最多重试 3 次。可以在初始化时调整：

```python
agent = GeminiAIReportAgent(max_retries=5)  # 增加重试次数
```

### 并发处理

当前实现是串行处理每个批次。未来版本可以考虑并发处理多个批次以提高速度。

## 质量保证

### 多轮质量检查

报告生成阶段会进行最多 3 轮质量检查：
1. 检查是否包含所有必需章节
2. 检查报告长度是否合理
3. 如果检查失败，会在提示词中添加反馈并重新生成

### 提示词优化

所有提示词都经过精心设计，包含：
- 明确的任务定义
- 详细的评判标准
- 结构化的输出格式
- 多轮迭代反馈机制

## 故障排查

### 问题1：API 调用失败

**症状**：`LLM API 调用失败`

**解决方案**：
1. 检查 `.env` 文件中的 API Key 是否正确
2. 检查网络连接
3. 检查 API 配额是否用尽
4. 尝试使用代理

### 问题2：JSON 解析失败

**症状**：`无法解析 JSON 响应`

**解决方案**：
1. 检查模型是否支持结构化输出
2. 尝试使用更稳定的模型（如 `gemini-2.0-flash-exp`）
3. 增加重试次数

### 问题3：过滤过于严格/宽松

**症状**：保留的新闻太少或太多

**解决方案**：
1. 调整 `step1_filter` 中的提示词
2. 修改保留/剔除条件的描述
3. 使用 `--save-intermediate` 查看中间结果并调试

### 问题4：事件归类不准确

**症状**：相关新闻被分到不同事件，或不相关新闻被归到同一事件

**解决方案**：
1. 调整 `step2_cluster` 中的提示词
2. 使用更强大的模型（如 `gemini-2.0-pro-exp`）
3. 减小批处理大小，提供更多上下文

## 进阶使用

### 自定义过滤规则

修改 `step1_filter` 方法中的提示词，添加或修改过滤规则。

### 自定义评分权重

修改 `step4_rank` 方法中的评分计算公式：

```python
# 调整权重
item.final_score = (
    item.tech_impact * 0.6 +      # 增加技术影响力的权重
    item.industry_scope * 0.2 +   # 减少行业范围的权重
    item.hype_score * 0.2
)
```

### 自定义评级阈值

修改评级映射逻辑：

```python
# 调整阈值
if item.final_score >= 4.5:       # 提高 S 级门槛
    item.ranking_level = "S"
elif item.final_score >= 3.8:     # 提高 A 级门槛
    item.ranking_level = "A"
# ...
```

### 添加新的处理步骤

可以在现有流程中插入新的处理步骤：

```python
async def step_custom(self, news_items: List[NewsItem]) -> List[NewsItem]:
    """自定义处理步骤"""
    # 实现自定义逻辑
    return news_items

# 在 run 方法中调用
async def run(self, days: int = 3):
    # ...
    news_items = await self.step2_cluster(news_items)
    news_items = await self.step_custom(news_items)  # 插入自定义步骤
    news_items = await self.step3_deduplicate(news_items)
    # ...
```

## 最佳实践

1. **首次使用**：使用 `--save-intermediate` 查看中间结果，了解每个步骤的处理效果
2. **日常使用**：使用默认配置即可，无需保存中间结果
3. **调试优化**：根据中间结果调整提示词和参数
4. **成本控制**：使用 `gemini-2.0-flash-exp` 模型，速度快且成本低
5. **质量优先**：使用 `gemini-2.0-pro-exp` 模型，生成更高质量的报告

## 与基础生成器的对比

| 特性 | 基础生成器 | GeminiAIReportAgent |
|------|-----------|-------------------|
| 新闻过滤 | 无 | ✓ 智能过滤 |
| 事件聚类 | 无 | ✓ 语义归类 |
| 去重 | 无 | ✓ 权威去重 |
| 价值评分 | 无 | ✓ 多维度评分 |
| 质量检查 | 无 | ✓ 多轮检查 |
| 处理时间 | ~10秒 | ~2-5分钟 |
| 报告质量 | 中等 | 高 |

## 贡献指南

欢迎提交 Issue 和 Pull Request！

改进方向：
- 优化提示词设计
- 添加更多数据源
- 实现并发批处理
- 支持更多 LLM 模型
- 添加更多评分维度

## 许可证

与项目主仓库保持一致。

