# GeminiAIReportAgent 架构设计文档

## 设计概述

`GeminiAIReportAgent` 是一个基于大语言模型（Gemini）的智能新闻处理系统，通过多轮语义分析实现从海量新闻数据到高质量报告的自动化生成。

### 设计目标

1. **智能过滤**：自动识别和剔除噪音信息（商业、金融、二次解读等）
2. **语义理解**：基于语义而非关键词进行事件聚类
3. **权威筛选**：在多个信息源中选择最权威的一条
4. **价值评估**：多维度评分，识别真正重要的技术进展
5. **质量保证**：多轮迭代和质量检查机制

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    GeminiAIReportAgent                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐        │
│  │  Database  │───▶│  NewsItem  │───▶│  Processor │        │
│  │   Layer    │    │   Model    │    │   Pipeline │        │
│  └────────────┘    └────────────┘    └────────────┘        │
│                                              │               │
│                          ┌───────────────────┘               │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │   Processing Steps    │                       │
│              ├───────────────────────┤                       │
│              │ 1. Filter             │                       │
│              │ 2. Cluster            │                       │
│              │ 3. Deduplicate        │                       │
│              │ 4. Rank               │                       │
│              │ 5. Generate Report    │                       │
│              └───────────────────────┘                       │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │   Gemini API Client   │                       │
│              ├───────────────────────┤                       │
│              │ - Prompt Engineering  │                       │
│              │ - Retry Mechanism     │                       │
│              │ - JSON Parsing        │                       │
│              │ - Batch Processing    │                       │
│              └───────────────────────┘                       │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │   Output Generator    │                       │
│              ├───────────────────────┤                       │
│              │ - Final Report        │                       │
│              │ - Intermediate Files  │                       │
│              │ - Quality Check       │                       │
│              └───────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. NewsItem 数据模型

```python
class NewsItem:
    # 基础信息
    article_id: str          # 唯一标识
    title: str               # 标题
    description: str         # 摘要
    content: str             # 内容（限制1000字符）
    url: str                 # URL
    source: str              # 来源（qbitai, openai等）
    publish_time: int        # 发布时间戳
    reference_links: str     # 参考链接（JSON格式）
    
    # 处理结果
    filter_decision: str     # "保留" or "剔除"
    filter_reason: str       # 过滤理由
    event_id: str            # 事件ID
    event_count: int         # 事件热度
    dedup_decision: str      # "保留" or "删除"
    dedup_reason: str        # 去重理由
    tech_impact: int         # 技术影响力 (1-5)
    industry_scope: int      # 行业范围 (1-5)
    hype_score: int          # 热度 (1-5)
    final_score: float       # 最终评分
    ranking_level: str       # 评级 (S/A/B/C)
```

### 2. GeminiAIReportAgent 主类

**职责：**
- 协调整个处理流程
- 管理 Gemini API 调用
- 批处理和重试机制
- 中间结果保存

**核心方法：**
```python
class GeminiAIReportAgent:
    async def fetch_articles_from_db()      # 数据获取
    async def step1_filter()                # 第一步：过滤
    async def step2_cluster()               # 第二步：归类
    async def step3_deduplicate()           # 第三步：去重
    async def step4_rank()                  # 第四步：排序
    def generate_final_report()             # 第五步：报告生成
    async def run()                         # 完整流程
```

---

## 处理流程详解

### 阶段 0：数据获取

**输入：** 
- `days`: 获取最近N天的数据
- `limit`: 每个表的最大条数

**处理：**
- 从 `QbitaiArticle` 表获取量子位新闻
- 从 `CompanyArticle` 表获取官方新闻
- 转换为 `NewsItem` 对象

**输出：** 
- `List[NewsItem]`

**批处理：** 不适用

---

### 阶段 1：过滤 (Filtering)

**目标：** 剔除与 AI 核心技术进展无关的噪音信息

**输入：** 
- 原始新闻列表

**处理逻辑：**

1. **保留条件**（逻辑或）：
   - 技术/能力进展
   - 关键领域（基础模型、训练/推理方法、AI Infra、Agent 框架）
   - 权威来源（arXiv、官方博客、GitHub Release）

2. **剔除条件**（逻辑或）：
   - 商业/金融（股价、融资、估值、财报）
   - 市场分析（投资观点、资本动向）
   - 二次解读（KOL 分析、推文总结）
   - 信源不明

**提示词设计：**
```
你是一个专业的AI技术内容筛选专家。请对以下新闻进行过滤判断。

【保留条件】（逻辑或，满足其一即保留）:
1. 技术/能力进展...
2. 关键领域...
3. 权威来源...

【剔除条件】（逻辑或，满足其一即剔除）:
1. 商业/金融...
2. 市场分析...
3. 二次解读...
4. 信源不明...

【新闻数据】
...

【输出格式】
JSON数组：
[
  {"article_id": "xxx", "filter_decision": "保留", "filter_reason": "..."},
  ...
]
```

**批处理：** 
- 批处理大小：20条/批
- 避免 Token 限制
- 减少 API 调用次数

**输出：** 
- 过滤后的新闻列表
- 每条新闻包含 `filter_decision` 和 `filter_reason`

**重试机制：** 
- 最多重试 3 次
- 失败时跳过该批次

---

### 阶段 2：归类 (Clustering)

**目标：** 将描述同一事件的新闻聚合在一起

**输入：** 
- 过滤后的新闻列表

**处理逻辑：**

1. **语义归类标准**：
   - 同一技术事件
   - 同一模型版本
   - 同一产品发布
   - 同一关键论文

2. **Event ID 生成**：
   - 有意义的英文短语
   - 使用下划线连接
   - 例如：`gpt5_release`, `llama3_1_opensource`

3. **增量归类**：
   - 每批处理时提供已识别的事件列表
   - 确保不同批次的相同事件使用同一 `event_id`

**提示词设计：**
```
你是一个专业的AI新闻事件聚类专家。请对以下新闻进行语义归类。

【归类标准】
- 按"同一技术事件 / 模型版本 / 产品发布 / 关键论文"进行语义归类
- event_id 应该是有意义的英文短语，用下划线连接

【已识别的事件ID列表】（供参考）
- gpt5_release: GPT-5 发布...
- llama3_1_opensource: Llama 3.1 开源...

【新闻数据】
...

【输出格式】
JSON数组：
[
  {"article_id": "xxx", "event_id": "gpt5_release"},
  ...
]
```

**批处理：** 
- 批处理大小：30条/批
- 每批提供已识别的事件信息

**输出：** 
- 归类后的新闻列表
- 每条新闻包含 `event_id` 和 `event_count`

**后处理：**
- 统计每个事件的新闻数量
- 更新所有相关新闻的 `event_count`

---

### 阶段 3：去重 (Deduplication)

**目标：** 每个事件只保留最权威、信息质量最高的一条新闻

**输入：** 
- 归类后的新闻列表

**处理逻辑：**

1. **按 event_id 分组**

2. **保留优先级**（从高到低）：
   - 官方核心信源（官网、官方博客、arXiv、GitHub）
   - 核心人员解读（作者、工程师、研究员）
   - 权威技术媒体（深度转述报道）
   - 社交媒体/普通转述（优先级最低）

3. **单事件处理**：
   - 只有1条新闻：直接保留
   - 多条新闻：使用 LLM 判断

**提示词设计：**
```
你是一个专业的AI新闻去重专家。以下是描述同一事件的多条新闻，
请选出最权威、信息质量最高的一条。

【保留优先级】（从高到低）
1. 官方核心信源...
2. 核心人员解读...
3. 权威技术媒体...
4. 社交媒体/普通转述...

【事件ID】gpt5_release

【新闻列表】
...

【输出格式】
JSON数组：
[
  {"article_id": "xxx", "dedup_decision": "保留", "dedup_reason": "官方博客首发"},
  {"article_id": "yyy", "dedup_decision": "删除", "dedup_reason": "二次转述"},
  ...
]
```

**批处理：** 
- 按事件分组处理
- 不跨事件批处理

**输出：** 
- 去重后的新闻列表
- 每条新闻包含 `dedup_decision` 和 `dedup_reason`

**容错机制：**
- 失败时默认保留第一条

---

### 阶段 4：排序 (Ranking)

**目标：** 对保留的新闻进行价值评分和分级

**输入：** 
- 去重后的新闻列表

**处理逻辑：**

1. **评分维度**：

   **技术影响力 (tech_impact)** [1-5分]：
   - 5分：范式转换
   - 4分：重大突破
   - 3分：显著改进
   - 2分：常规优化
   - 1分：微小改进

   **行业影响范围 (industry_scope)** [1-5分]：
   - 5分：全行业
   - 4分：多领域
   - 3分：特定领域
   - 2分：特定任务
   - 1分：小众场景

   **热度 (hype_score)** [1-5分]：
   - 基于 `event_count` 映射
   - 1-2篇→1分, 3-5篇→2分, 6-10篇→3分, 11-20篇→4分, >20篇→5分

2. **最终评分计算**：
   ```
   FinalScore = (tech_impact × 0.5) + (industry_scope × 0.3) + (hype_score × 0.2)
   ```

3. **评级映射**：
   - FinalScore ≥ 4.2 → S级
   - 3.5 ≤ FinalScore < 4.2 → A级
   - 2.8 ≤ FinalScore < 3.5 → B级
   - FinalScore < 2.8 → C级

**提示词设计：**
```
你是一个专业的AI技术影响力评估专家。请对以下新闻进行价值评分。

【评分维度】

1. 技术影响力 (tech_impact) [1-5分]:
   - 5分 (范式转换): ...
   - 4分 (重大突破): ...
   - ...

2. 行业影响范围 (industry_scope) [1-5分]:
   - 5分 (全行业): ...
   - ...

3. 热度 (hype_score) [1-5分]:
   - 根据 event_count 映射

【新闻数据】
...

【输出格式】
JSON数组：
[
  {"article_id": "xxx", "tech_impact": 5, "industry_scope": 5, "hype_score": 4},
  ...
]
```

**批处理：** 
- 批处理大小：20条/批

**输出：** 
- 排序后的新闻列表（按 `final_score` 降序）
- 每条新闻包含完整的评分信息

**后处理：**
- 计算 `final_score`
- 映射 `ranking_level`
- 按评分排序

---

### 阶段 5：报告生成

**目标：** 生成高质量的 Markdown 格式报告

**输入：** 
- 排序后的新闻列表
- 报告模板

**处理逻辑：**

1. **按评级分组**：
   - S级、A级、B级、C级

2. **格式化新闻数据**：
   - 标题、来源、链接、发布时间
   - 评分详情、事件热度
   - 摘要、原始来源

3. **生成报告**：
   - 使用模板定义格式
   - LLM 生成内容
   - 温度参数：0.3（平衡创造性和稳定性）

4. **质量检查**（可选）：
   - 检查必需章节
   - 检查报告长度
   - 最多重试 3 次

**提示词设计：**
```
你是一个专业的AI前沿科技分析师。请根据以下经过筛选、归类、去重和排序的
新闻数据，编写一份高质量的AI前沿动态速报。

【当前日期】2025-12-18

【报告模板和要求】
...（从 templates/AIReport_example.md 读取）

【经过处理的新闻数据】
## S级新闻 (3条)
...
## A级新闻 (5条)
...

【特别指令】
1. 严格遵循模板格式
2. 优先关注 S 级和 A 级新闻
3. 深度解读要有实质内容
4. 优先使用原始来源链接
5. 语言风格专业、客观、有洞察力
...
```

**批处理：** 
- 不适用（整体生成）

**输出：** 
- Markdown 格式的报告内容

**质量保证：**
- 多轮生成和检查
- 失败时提供反馈并重新生成

---

## 技术细节

### 1. Gemini API 调用

**配置：**
```python
client = OpenAI(
    api_key=self.api_key,
    base_url=self.base_url,  # OpenAI 兼容格式
    http_client=httpx.Client(verify=False, timeout=120.0)
)
```

**调用：**
```python
response = client.chat.completions.create(
    model=self.model_name,
    messages=[{"role": "user", "content": prompt}],
    temperature=temperature
)
```

**推荐模型：**
- `gemini-2.0-flash-exp`: 速度快，成本低（推荐用于 Agent）
- `gemini-2.0-pro-exp`: 质量高，平衡性好
- `gemini-exp-1206`: 最新实验版本

### 2. JSON 解析

**支持格式：**
- 直接 JSON：`[{...}, {...}]`
- Markdown 代码块：` ```json\n[...]\n``` `

**解析逻辑：**
```python
def _parse_json_response(self, response: str) -> Optional[List[Dict]]:
    try:
        # 直接解析
        return json.loads(response)
    except json.JSONDecodeError:
        # 提取 markdown 代码块中的 JSON
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        return None
```

### 3. 批处理机制

**目的：**
- 避免 Token 限制
- 减少 API 调用次数
- 提高处理效率

**实现：**
```python
for i in range(0, len(news_items), batch_size):
    batch = news_items[i:i + batch_size]
    # 处理批次
    results = await self.process_batch(batch)
    # 合并结果
    all_results.extend(results)
    # 避免限流
    await asyncio.sleep(1)
```

**批处理大小：**
- 过滤：20条/批
- 归类：30条/批
- 去重：按事件分组
- 排序：20条/批

### 4. 重试机制

**策略：**
- 每个步骤最多重试 3 次（可配置）
- 失败时记录日志
- 关键步骤失败时使用默认策略

**实现：**
```python
for retry in range(self.max_retries):
    response = self._call_llm(prompt)
    results = self._parse_json_response(response)
    
    if results:
        # 成功
        break
    else:
        logger.warning(f"重试 {retry + 1}/{self.max_retries}")
        if retry == self.max_retries - 1:
            # 失败处理
            handle_failure()
```

### 5. 中间结果保存

**目的：**
- 调试和优化
- 分析处理效果
- 故障恢复

**格式：**
```json
[
  {
    "article_id": "qbitai_123",
    "title": "...",
    "filter_decision": "保留",
    "filter_reason": "...",
    "event_id": "gpt5_release",
    "event_count": 5,
    "dedup_decision": "保留",
    "dedup_reason": "...",
    "tech_impact": 5,
    "industry_scope": 5,
    "hype_score": 3,
    "final_score": 4.6,
    "ranking_level": "S"
  }
]
```

**保存时机：**
- 每个阶段完成后
- 仅在 `save_intermediate=True` 时保存

---

## 性能优化

### 1. 批处理优化

**当前：** 串行处理每个批次

**未来改进：** 并发处理多个批次
```python
tasks = [self.process_batch(batch) for batch in batches]
results = await asyncio.gather(*tasks)
```

### 2. 缓存机制

**潜在改进：**
- 缓存相似新闻的处理结果
- 减少重复的 API 调用

### 3. 增量处理

**潜在改进：**
- 只处理新增的新闻
- 复用之前的处理结果

### 4. 模型选择

**权衡：**
- `gemini-2.0-flash-exp`: 速度快，成本低，质量中等
- `gemini-2.0-pro-exp`: 速度中，成本中，质量高

**建议：**
- 日常使用：`gemini-2.0-flash-exp`
- 重要报告：`gemini-2.0-pro-exp`

---

## 扩展性设计

### 1. 自定义处理步骤

**接口：**
```python
async def step_custom(self, news_items: List[NewsItem]) -> List[NewsItem]:
    """自定义处理步骤"""
    # 实现自定义逻辑
    return news_items
```

**集成：**
```python
async def run(self, days: int = 3):
    news_items = await self.step1_filter(news_items)
    news_items = await self.step_custom(news_items)  # 插入自定义步骤
    news_items = await self.step2_cluster(news_items)
```

### 2. 自定义评分权重

**当前：**
```python
final_score = (tech_impact * 0.5) + (industry_scope * 0.3) + (hype_score * 0.2)
```

**扩展：**
```python
def calculate_score(self, item: NewsItem, weights: Dict[str, float]) -> float:
    return (
        item.tech_impact * weights.get('tech', 0.5) +
        item.industry_scope * weights.get('industry', 0.3) +
        item.hype_score * weights.get('hype', 0.2)
    )
```

### 3. 支持更多 LLM

**当前：** 仅支持 Gemini（OpenAI 兼容格式）

**扩展：**
```python
class BaseLLMClient:
    def call_llm(self, prompt: str) -> str:
        raise NotImplementedError

class GeminiClient(BaseLLMClient):
    def call_llm(self, prompt: str) -> str:
        # Gemini 实现

class OpenAIClient(BaseLLMClient):
    def call_llm(self, prompt: str) -> str:
        # OpenAI 实现
```

---

## 质量保证

### 1. 提示词工程

**原则：**
- 明确的任务定义
- 详细的评判标准
- 结构化的输出格式
- 多轮迭代反馈

**示例：**
```
【任务】明确告诉 LLM 要做什么
【标准】详细说明评判标准
【数据】提供必要的输入数据
【格式】指定输出格式（JSON）
【约束】说明特殊要求和限制
```

### 2. 输出验证

**检查项：**
- JSON 格式正确性
- 必需字段完整性
- 值的合理性（如评分范围）
- 逻辑一致性

### 3. 多轮迭代

**策略：**
- 第一轮：初步生成
- 检查质量
- 提供反馈
- 重新生成（最多3轮）

### 4. 日志记录

**记录内容：**
- 每个步骤的输入输出
- API 调用状态
- 错误和警告
- 处理统计信息

---

## 最佳实践

### 1. 提示词设计

✅ **推荐：**
- 使用清晰的结构（【标题】内容）
- 提供具体的示例
- 明确输出格式
- 包含边界条件处理

❌ **避免：**
- 模糊的指令
- 过长的提示词（>4000 tokens）
- 隐式假设
- 缺少输出格式说明

### 2. 批处理大小

✅ **推荐：**
- 根据 Token 限制调整
- 考虑 API 限流
- 平衡速度和质量

❌ **避免：**
- 批次太大导致超时
- 批次太小增加成本

### 3. 错误处理

✅ **推荐：**
- 捕获所有异常
- 记录详细错误信息
- 提供回退方案
- 优雅降级

❌ **避免：**
- 静默失败
- 抛出未处理异常
- 缺少用户提示

### 4. 测试和验证

✅ **推荐：**
- 使用测试脚本验证每个步骤
- 保存中间结果进行分析
- 对比不同模型的效果
- 收集用户反馈

---

## 未来改进方向

### 1. 性能优化
- [ ] 并发批处理
- [ ] 结果缓存
- [ ] 增量处理
- [ ] 智能批次大小调整

### 2. 功能增强
- [ ] 支持更多 LLM（OpenAI, Claude 等）
- [ ] 多语言支持
- [ ] 自定义评分维度
- [ ] 交互式报告生成

### 3. 质量提升
- [ ] 更精细的提示词工程
- [ ] 自适应质量检查
- [ ] 用户反馈学习
- [ ] A/B 测试框架

### 4. 易用性
- [ ] Web UI 界面
- [ ] 配置文件支持
- [ ] 插件系统
- [ ] 详细的使用文档

---

## 总结

`GeminiAIReportAgent` 通过多轮语义分析实现了从海量新闻到高质量报告的自动化生成。其核心优势在于：

1. **智能化**：基于 LLM 的语义理解，而非简单的关键词匹配
2. **模块化**：清晰的五步流程，易于理解和扩展
3. **可靠性**：完善的错误处理和重试机制
4. **可观测**：详细的日志和中间结果
5. **灵活性**：支持自定义处理逻辑和参数

通过合理的架构设计和提示词工程，Agent 能够有效地处理大量新闻数据，生成高质量的 AI 前沿动态报告。

---

**文档版本：** 1.0  
**最后更新：** 2025-12-18  
**维护者：** AIReport Team

