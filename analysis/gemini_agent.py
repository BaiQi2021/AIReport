#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeminiAIReportAgent - 智能新闻处理Agent
实现：过滤 -> 归类 -> 去重 -> 排序 -> 报告生成 的多轮流程
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from openai import OpenAI
import httpx
from sqlalchemy import select, desc, or_

from database.models import QbitaiArticle, CompanyArticle
from database.db_session import get_session
import config
from crawler import utils

settings = config.settings
logger = utils.logger


class NewsItem:
    """新闻条目数据结构"""
    def __init__(self, article_id: str, title: str, description: str, 
                 content: str, url: str, source: str, publish_time: int,
                 reference_links: Optional[str] = None):
        self.article_id = article_id
        self.title = title
        self.description = description
        self.content = content[:1000]  # 限制内容长度
        self.url = url
        self.source = source  # 来源：qbitai, openai, google等
        self.publish_time = publish_time
        self.reference_links = reference_links
        
        # 处理结果字段
        self.filter_decision = None  # "保留" or "剔除"
        self.filter_reason = None
        self.event_id = None
        self.event_count = 0
        self.dedup_decision = None  # "保留" or "删除"
        self.dedup_reason = None
        self.tech_impact = 0
        self.industry_scope = 0
        self.hype_score = 0
        self.final_score = 0.0
        self.ranking_level = "C"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "article_id": self.article_id,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "url": self.url,
            "source": self.source,
            "publish_time": self.publish_time,
            "reference_links": self.reference_links,
            "filter_decision": self.filter_decision,
            "filter_reason": self.filter_reason,
            "event_id": self.event_id,
            "event_count": self.event_count,
            "dedup_decision": self.dedup_decision,
            "dedup_reason": self.dedup_reason,
            "tech_impact": self.tech_impact,
            "industry_scope": self.industry_scope,
            "hype_score": self.hype_score,
            "final_score": self.final_score,
            "ranking_level": self.ranking_level
        }


class GeminiAIReportAgent:
    """基于 Gemini 的智能报告生成 Agent"""
    
    def __init__(self, max_retries: int = 3):
        """
        初始化 Agent
        
        Args:
            max_retries: 每个步骤的最大重试次数
        """
        self.api_key = settings.REPORT_ENGINE_API_KEY
        self.base_url = settings.REPORT_ENGINE_BASE_URL
        self.model_name = settings.REPORT_ENGINE_MODEL_NAME or "gemini-2.0-flash-exp"
        self.max_retries = max_retries
        
        if not self.api_key:
            raise ValueError("API Key not configured in settings")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=httpx.Client(verify=False, timeout=120.0)
        )
        
        self.template_path = Path(__file__).parent / "templates" / "AIReport_example.md"
        
    async def fetch_articles_from_db(self, days: int = 3, limit: int = 200) -> List[NewsItem]:
        """
        从数据库获取新闻数据
        
        Args:
            days: 获取最近N天的数据
            limit: 每个表的最大条数
            
        Returns:
            新闻条目列表
        """
        logger.info(f"正在从数据库获取最近 {days} 天的新闻数据...")
        
        cutoff_date = (datetime.now() - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cutoff_ts = int(cutoff_date.timestamp())
        
        news_items = []
        
        async with get_session() as session:
            # 获取量子位文章
            stmt = (
                select(QbitaiArticle)
                .where(QbitaiArticle.publish_time >= cutoff_ts)
                .order_by(desc(QbitaiArticle.publish_time))
                .limit(limit)
            )
            result = await session.execute(stmt)
            qbitai_articles = result.scalars().all()
            
            for art in qbitai_articles:
                news_items.append(NewsItem(
                    article_id=f"qbitai_{art.article_id}",
                    title=art.title,
                    description=art.description or "",
                    content=art.content or "",
                    url=art.article_url,
                    source="量子位",
                    publish_time=art.publish_time,
                    reference_links=art.reference_links
                ))
            
            # 获取公司官方文章
            stmt = (
                select(CompanyArticle)
                .where(CompanyArticle.publish_time >= cutoff_ts)
                .order_by(desc(CompanyArticle.publish_time))
                .limit(limit)
            )
            result = await session.execute(stmt)
            company_articles = result.scalars().all()
            
            for art in company_articles:
                news_items.append(NewsItem(
                    article_id=f"{art.company}_{art.article_id}",
                    title=art.title,
                    description=art.description or "",
                    content=art.content or "",
                    url=art.article_url,
                    source=art.company.upper(),
                    publish_time=art.publish_time,
                    reference_links=art.reference_links
                ))
        
        logger.info(f"共获取 {len(news_items)} 条新闻数据")
        return news_items
    
    def _call_llm(self, prompt: str, temperature: float = 0.1) -> Optional[str]:
        """
        调用 LLM API
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            
        Returns:
            LLM 响应内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            return None
    
    def _parse_json_response(self, response: str) -> Optional[List[Dict]]:
        """
        解析 JSON 响应，支持提取 markdown 代码块中的 JSON
        
        Args:
            response: LLM 响应文本
            
        Returns:
            解析后的 JSON 列表
        """
        if not response:
            return None
        
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 markdown 代码块中的 JSON
            import re
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    pass
            
            logger.error(f"无法解析 JSON 响应: {response[:200]}")
            return None
    
    async def step1_filter(self, news_items: List[NewsItem], batch_size: int = 20) -> List[NewsItem]:
        """
        第一步：过滤 (Filtering)
        剔除与 AI 核心技术进展无关的噪音信息
        
        Args:
            news_items: 原始新闻列表
            batch_size: 批处理大小
            
        Returns:
            过滤后的新闻列表
        """
        logger.info("=" * 60)
        logger.info("【第一步】开始过滤 (Filtering)...")
        logger.info(f"待处理新闻数: {len(news_items)}, 批处理大小: {batch_size}")
        
        filtered_items = []
        
        # 分批处理
        for i in range(0, len(news_items), batch_size):
            batch = news_items[i:i + batch_size]
            logger.info(f"处理批次 {i // batch_size + 1}/{(len(news_items) - 1) // batch_size + 1}")
            
            # 构建提示词
            batch_data = []
            for item in batch:
                batch_data.append({
                    "article_id": item.article_id,
                    "title": item.title,
                    "description": item.description,
                    "content_snippet": item.content[:300],
                    "source": item.source,
                    "url": item.url
                })
            
            prompt = f"""你是一个专业的AI技术内容筛选专家。请对以下新闻进行过滤判断。

**过滤规则：**

【保留条件】（逻辑或，满足其一即保留）:
1. 技术/能力进展: 核心内容是关于 AI 技术、模型、系统、工程或应用能力的具体进展。
2. 关键领域: 明确涉及基础模型、训练/推理方法、数据工程、AI Infra、Agent 框架或相关技术产品。
3. 权威来源: 信息来源为学术论文 (如 arXiv)、官方技术博客 (如 OpenAI Blog)、官方产品发布页或 GitHub Release Notes。

【剔除条件】（逻辑或，满足其一即剔除）:
1. 商业/金融: 股价、市值、融资、IPO、估值、财报、收入、用户规模、收购、并购。
2. 市场分析: 投资观点、市场情绪、资本动向、无直接技术关联的商业合作新闻。
3. 二次解读: 个人观点、KOL 长篇分析、无引用的推文总结。
4. 信源不明: 未标注明确来源、来源为匿名论坛或社交群聊截图。

**新闻数据：**
```json
{json.dumps(batch_data, ensure_ascii=False, indent=2)}
```

**输出要求：**
请以 JSON 数组格式返回，每条新闻包含以下字段：
- article_id: 文章ID
- filter_decision: "保留" 或 "剔除"
- filter_reason: 判断理由（一句话简述）

输出格式示例：
```json
[
  {{"article_id": "xxx", "filter_decision": "保留", "filter_reason": "涉及大模型训练技术突破"}},
  {{"article_id": "yyy", "filter_decision": "剔除", "filter_reason": "主要讨论融资和市值"}}
]
```

请直接返回 JSON，不要添加额外说明。
"""
            
            # 调用 LLM
            for retry in range(self.max_retries):
                response = self._call_llm(prompt)
                results = self._parse_json_response(response)
                
                if results:
                    # 更新新闻条目
                    result_map = {r["article_id"]: r for r in results}
                    for item in batch:
                        if item.article_id in result_map:
                            r = result_map[item.article_id]
                            item.filter_decision = r.get("filter_decision")
                            item.filter_reason = r.get("filter_reason")
                            
                            if item.filter_decision == "保留":
                                filtered_items.append(item)
                    break
                else:
                    logger.warning(f"批次 {i // batch_size + 1} 解析失败，重试 {retry + 1}/{self.max_retries}")
                    if retry == self.max_retries - 1:
                        logger.error(f"批次 {i // batch_size + 1} 处理失败，跳过")
            
            # 避免 API 限流
            await asyncio.sleep(1)
        
        logger.info(f"过滤完成：保留 {len(filtered_items)}/{len(news_items)} 条新闻")
        return filtered_items
    
    async def step2_cluster(self, news_items: List[NewsItem], batch_size: int = 30) -> List[NewsItem]:
        """
        第二步：归类 (Clustering)
        将描述同一事件的新闻聚合在一起
        
        Args:
            news_items: 过滤后的新闻列表
            batch_size: 批处理大小
            
        Returns:
            归类后的新闻列表
        """
        logger.info("=" * 60)
        logger.info("【第二步】开始归类 (Clustering)...")
        logger.info(f"待处理新闻数: {len(news_items)}")
        
        # 分批处理
        all_events = {}  # event_id -> [NewsItem]
        
        for i in range(0, len(news_items), batch_size):
            batch = news_items[i:i + batch_size]
            logger.info(f"处理批次 {i // batch_size + 1}/{(len(news_items) - 1) // batch_size + 1}")
            
            # 构建提示词
            batch_data = []
            for item in batch:
                batch_data.append({
                    "article_id": item.article_id,
                    "title": item.title,
                    "description": item.description,
                    "source": item.source
                })
            
            # 包含之前已识别的事件信息
            existing_events_info = ""
            if all_events:
                existing_events_info = "\n已识别的事件ID列表（供参考）:\n"
                for event_id, items in all_events.items():
                    existing_events_info += f"- {event_id}: {items[0].title[:50]}...\n"
            
            prompt = f"""你是一个专业的AI新闻事件聚类专家。请对以下新闻进行语义归类。

**归类标准：**
- 按"同一技术事件 / 模型版本 / 产品发布 / 关键论文"进行语义归类。
- 例如："GPT-5 发布"、"Llama 3.1 开源"、"DeepMind 提出新 AlphaFold 算法"等均属于独立的语义事件。
- 如果多条新闻讨论的是同一个事件（如同一个模型发布、同一篇论文、同一个技术突破），它们应该被归为同一个 event_id。
- event_id 应该是有意义的英文短语，用下划线连接，例如：gpt5_release_2025_q4, llama3_1_opensource

{existing_events_info}

**新闻数据：**
```json
{json.dumps(batch_data, ensure_ascii=False, indent=2)}
```

**输出要求：**
请以 JSON 数组格式返回，每条新闻包含以下字段：
- article_id: 文章ID
- event_id: 事件ID（使用有意义的英文短语，如果与已识别的事件相同，请使用相同的event_id）

输出格式示例：
```json
[
  {{"article_id": "xxx", "event_id": "gpt5_release"}},
  {{"article_id": "yyy", "event_id": "llama3_1_opensource"}}
]
```

请直接返回 JSON，不要添加额外说明。
"""
            
            # 调用 LLM
            for retry in range(self.max_retries):
                response = self._call_llm(prompt)
                results = self._parse_json_response(response)
                
                if results:
                    # 更新新闻条目
                    result_map = {r["article_id"]: r for r in results}
                    for item in batch:
                        if item.article_id in result_map:
                            event_id = result_map[item.article_id].get("event_id")
                            item.event_id = event_id
                            
                            if event_id not in all_events:
                                all_events[event_id] = []
                            all_events[event_id].append(item)
                    break
                else:
                    logger.warning(f"批次 {i // batch_size + 1} 解析失败，重试 {retry + 1}/{self.max_retries}")
                    if retry == self.max_retries - 1:
                        logger.error(f"批次 {i // batch_size + 1} 处理失败")
            
            await asyncio.sleep(1)
        
        # 更新每条新闻的 event_count
        for event_id, items in all_events.items():
            count = len(items)
            for item in items:
                item.event_count = count
        
        logger.info(f"归类完成：识别出 {len(all_events)} 个独立事件")
        for event_id, items in sorted(all_events.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            logger.info(f"  - {event_id}: {len(items)} 条新闻")
        
        return news_items
    
    async def step3_deduplicate(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """
        第三步：去重 (Deduplication)
        在每个事件中，仅保留一条最权威、信息质量最高的新闻
        
        Args:
            news_items: 归类后的新闻列表
            
        Returns:
            去重后的新闻列表
        """
        logger.info("=" * 60)
        logger.info("【第三步】开始去重 (Deduplication)...")
        
        # 按 event_id 分组
        events = defaultdict(list)
        for item in news_items:
            events[item.event_id].append(item)
        
        logger.info(f"待处理事件数: {len(events)}")
        
        deduplicated_items = []
        
        for event_id, items in events.items():
            if len(items) == 1:
                # 只有一条新闻，直接保留
                items[0].dedup_decision = "保留"
                items[0].dedup_reason = "唯一来源"
                deduplicated_items.append(items[0])
                continue
            
            logger.info(f"处理事件: {event_id} ({len(items)} 条新闻)")
            
            # 构建提示词
            batch_data = []
            for item in items:
                batch_data.append({
                    "article_id": item.article_id,
                    "title": item.title,
                    "description": item.description,
                    "source": item.source,
                    "url": item.url,
                    "publish_time": datetime.fromtimestamp(item.publish_time).strftime('%Y-%m-%d %H:%M')
                })
            
            prompt = f"""你是一个专业的AI新闻去重专家。以下是描述同一事件的多条新闻，请选出最权威、信息质量最高的一条。

**保留优先级（从高到低）：**
1. 官方核心信源: 官网发布、官方博客、arXiv 论文、GitHub Release
2. 核心人员解读: 作者、核心工程师或官方研究员的深度解读
3. 权威技术媒体: 对上述信源的深度、快速转述报道
4. 社交媒体/普通转述: 优先级最低

**事件ID:** {event_id}

**新闻列表：**
```json
{json.dumps(batch_data, ensure_ascii=False, indent=2)}
```

**输出要求：**
请选择一条最权威的新闻保留，其余标记为删除。以 JSON 数组格式返回：
- article_id: 文章ID
- dedup_decision: "保留" 或 "删除"
- dedup_reason: 判断理由（一句话）

输出格式示例：
```json
[
  {{"article_id": "xxx", "dedup_decision": "保留", "dedup_reason": "官方博客首发"}},
  {{"article_id": "yyy", "dedup_decision": "删除", "dedup_reason": "二次转述"}}
]
```

请直接返回 JSON，不要添加额外说明。
"""
            
            # 调用 LLM
            for retry in range(self.max_retries):
                response = self._call_llm(prompt)
                results = self._parse_json_response(response)
                
                if results:
                    result_map = {r["article_id"]: r for r in results}
                    for item in items:
                        if item.article_id in result_map:
                            r = result_map[item.article_id]
                            item.dedup_decision = r.get("dedup_decision")
                            item.dedup_reason = r.get("dedup_reason")
                            
                            if item.dedup_decision == "保留":
                                deduplicated_items.append(item)
                    break
                else:
                    logger.warning(f"事件 {event_id} 去重失败，重试 {retry + 1}/{self.max_retries}")
                    if retry == self.max_retries - 1:
                        # 失败时保留第一条
                        logger.error(f"事件 {event_id} 去重失败，默认保留第一条")
                        items[0].dedup_decision = "保留"
                        items[0].dedup_reason = "去重失败，默认保留"
                        deduplicated_items.append(items[0])
            
            await asyncio.sleep(0.5)
        
        logger.info(f"去重完成：保留 {len(deduplicated_items)}/{len(news_items)} 条新闻")
        return deduplicated_items
    
    async def step4_rank(self, news_items: List[NewsItem], batch_size: int = 20) -> List[NewsItem]:
        """
        第四步：排序 (Ranking)
        对最终保留的新闻条目进行价值判断
        
        Args:
            news_items: 去重后的新闻列表
            batch_size: 批处理大小
            
        Returns:
            排序后的新闻列表
        """
        logger.info("=" * 60)
        logger.info("【第四步】开始排序 (Ranking)...")
        logger.info(f"待评分新闻数: {len(news_items)}")
        
        # 分批处理
        for i in range(0, len(news_items), batch_size):
            batch = news_items[i:i + batch_size]
            logger.info(f"处理批次 {i // batch_size + 1}/{(len(news_items) - 1) // batch_size + 1}")
            
            # 构建提示词
            batch_data = []
            for item in batch:
                batch_data.append({
                    "article_id": item.article_id,
                    "title": item.title,
                    "description": item.description,
                    "source": item.source,
                    "event_count": item.event_count
                })
            
            prompt = f"""你是一个专业的AI技术影响力评估专家。请对以下新闻进行价值评分。

**评分维度：**

1. **技术影响力 (tech_impact)** [1-5分]:
   - 5分 (范式转换): 提出全新架构或理论，可能改变一个领域的走向 (如 Transformer)
   - 4分 (重大突破): 在关键能力上有巨大提升或开源了强大的基础模型
   - 3分 (显著改进): 现有方法上的重要改进，或发布了非常有用的工具/框架
   - 2分 (常规优化): 性能的小幅提升或常规版本迭代
   - 1分 (微小改进): 增量式更新

2. **行业影响范围 (industry_scope)** [1-5分]:
   - 5分 (全行业): 对几乎所有 AI 应用开发者和公司都产生影响
   - 4分 (多领域): 影响多个主要 AI 应用领域 (如 NLP, CV)
   - 3分 (特定领域): 深度影响一个垂直领域 (如 AI for Science)
   - 2分 (特定任务): 主要影响一个或少数几个具体任务
   - 1分 (小众场景): 影响范围非常有限

3. **热度 (hype_score)** [1-5分]:
   - 根据 event_count 映射：
     * 1-2篇 → 1分
     * 3-5篇 → 2分
     * 6-10篇 → 3分
     * 11-20篇 → 4分
     * >20篇 → 5分

**新闻数据：**
```json
{json.dumps(batch_data, ensure_ascii=False, indent=2)}
```

**输出要求：**
请以 JSON 数组格式返回，每条新闻包含以下字段：
- article_id: 文章ID
- tech_impact: 技术影响力评分 (1-5)
- industry_scope: 行业影响范围评分 (1-5)
- hype_score: 热度评分 (1-5，根据event_count计算)

输出格式示例：
```json
[
  {{"article_id": "xxx", "tech_impact": 5, "industry_scope": 5, "hype_score": 4}},
  {{"article_id": "yyy", "tech_impact": 3, "industry_scope": 3, "hype_score": 2}}
]
```

请直接返回 JSON，不要添加额外说明。
"""
            
            # 调用 LLM
            for retry in range(self.max_retries):
                response = self._call_llm(prompt)
                results = self._parse_json_response(response)
                
                if results:
                    result_map = {r["article_id"]: r for r in results}
                    for item in batch:
                        if item.article_id in result_map:
                            r = result_map[item.article_id]
                            item.tech_impact = r.get("tech_impact", 2)
                            item.industry_scope = r.get("industry_scope", 2)
                            item.hype_score = r.get("hype_score", 1)
                            
                            # 计算最终评分
                            item.final_score = (
                                item.tech_impact * 0.45 +
                                item.industry_scope * 0.2 +
                                item.hype_score * 0.35
                            )
                            
                            # 评级映射
                            if item.final_score >= 4.2:
                                item.ranking_level = "S"
                            elif item.final_score >= 3.5:
                                item.ranking_level = "A"
                            elif item.final_score >= 2.8:
                                item.ranking_level = "B"
                            else:
                                item.ranking_level = "C"
                    break
                else:
                    logger.warning(f"批次 {i // batch_size + 1} 评分失败，重试 {retry + 1}/{self.max_retries}")
                    if retry == self.max_retries - 1:
                        logger.error(f"批次 {i // batch_size + 1} 评分失败")
            
            await asyncio.sleep(1)
        
        # 按评分排序
        news_items.sort(key=lambda x: x.final_score, reverse=True)
        
        logger.info(f"排序完成：")
        logger.info(f"  S级: {sum(1 for x in news_items if x.ranking_level == 'S')} 条")
        logger.info(f"  A级: {sum(1 for x in news_items if x.ranking_level == 'A')} 条")
        logger.info(f"  B级: {sum(1 for x in news_items if x.ranking_level == 'B')} 条")
        logger.info(f"  C级: {sum(1 for x in news_items if x.ranking_level == 'C')} 条")
        
        return news_items
    
    def generate_final_report(self, news_items: List[NewsItem], quality_check: bool = True) -> Optional[str]:
        """
        生成最终报告
        
        Args:
            news_items: 排序后的新闻列表
            quality_check: 是否进行质量检查
            
        Returns:
            报告内容
        """
        logger.info("=" * 60)
        logger.info("【第五步】生成最终报告...")
        
        if not news_items:
            logger.warning("没有新闻可以生成报告")
            return None
        
        # 读取模板
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except Exception as e:
            logger.error(f"读取模板失败: {e}")
            return None
        
        # 按评级分组
        news_by_level = defaultdict(list)
        for item in news_items:
            news_by_level[item.ranking_level].append(item)
        
        # 计算覆盖日期范围（用于提示模型正确填写头部区间）
        publish_times = [item.publish_time for item in news_items if item.publish_time]
        if publish_times:
            date_range_start = datetime.fromtimestamp(min(publish_times)).strftime('%Y-%m-%d')
            date_range_end = datetime.fromtimestamp(max(publish_times)).strftime('%Y-%m-%d')
        else:
            today_str = datetime.now().strftime('%Y-%m-%d')
            date_range_start = today_str
            date_range_end = today_str

        # 格式化新闻数据
        formatted_news = ""
        for level in ["S", "A", "B", "C"]:
            items = news_by_level[level]
            if items:
                formatted_news += f"\n## {level}级新闻 ({len(items)}条)\n\n"
                for i, item in enumerate(items, 1):
                    pub_date = datetime.fromtimestamp(item.publish_time).strftime('%Y-%m-%d %H:%M')
                    formatted_news += f"### [{i}] {item.title}\n"
                    formatted_news += f"- **来源**: {item.source}\n"
                    formatted_news += f"- **链接**: {item.url}\n"
                    formatted_news += f"- **发布时间**: {pub_date}\n"
                    formatted_news += f"- **评分**: {item.final_score:.2f} (技术影响:{item.tech_impact}, 行业范围:{item.industry_scope}, 热度:{item.hype_score})\n"
                    formatted_news += f"- **事件热度**: {item.event_count} 条相关报道\n"
                    formatted_news += f"- **摘要**: {item.description}\n"
                    
                    # 添加参考链接
                    if item.reference_links:
                        try:
                            ref_links = json.loads(item.reference_links)
                            if ref_links:
                                formatted_news += f"- **原始来源**:\n"
                                for ref in ref_links:
                                    formatted_news += f"  - [{ref['title']}]({ref['url']}) (类型: {ref['type']})\n"
                        except:
                            pass
                    
                    formatted_news += "\n"
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        prompt = f"""你是一个专业的AI前沿科技分析师。请根据以下经过筛选、归类、去重和排序的新闻数据，编写一份高质量的AI前沿动态速报。

**当前日期**: {today_str}
**报告覆盖日期范围（务必用于文首括号区间）**: {date_range_start} 至 {date_range_end}

**报告模板和要求:**
{template_content}

**经过处理的新闻数据:**
{formatted_news}

**特别指令:**
1. 严格遵循模板格式，一级标题和二级标题必须与模板一致
2. 新闻已按 S/A/B/C 级别排序，优先关注 S 级和 A 级新闻
3. 深度解读部分要有实质内容，结合技术背景和行业影响进行分析
4. 如果新闻数据中提供了"原始来源"，标题链接必须使用原始来源URL
5. Source 字段优先填写原始来源名称（如 OpenAI, arXiv 等）
6. 语言风格要专业、客观、有洞察力
7. 输出必须是 Markdown 格式
8. 三级标题基于内容分析生成，要有个性化和洞察力

请生成完整的报告内容。
"""
        
        # 调用 LLM 生成报告
        max_attempts = 3 if quality_check else 1
        
        for attempt in range(max_attempts):
            logger.info(f"正在生成报告 (尝试 {attempt + 1}/{max_attempts})...")
            
            report_content = self._call_llm(prompt, temperature=0.3)
            
            if not report_content:
                logger.error("报告生成失败")
                continue
            
            # 质量检查
            if quality_check and attempt < max_attempts - 1:
                if self._check_report_quality(report_content, template_content):
                    logger.info("报告质量检查通过")
                    return report_content
                else:
                    logger.warning(f"报告质量检查未通过，重新生成 (尝试 {attempt + 2}/{max_attempts})")
                    # 添加质量反馈到提示词
                    prompt += "\n\n**质量问题**: 上一次生成的报告格式或内容不符合要求，请严格按照模板生成。"
            else:
                return report_content
        
        return report_content
    
    def _check_report_quality(self, report: str, template: str) -> bool:
        """
        检查报告质量
        
        Args:
            report: 生成的报告
            template: 模板内容
            
        Returns:
            是否通过质量检查
        """
        # 简单检查：是否包含关键章节
        required_sections = ["AI前沿动态速报", "本周焦点", "深度解读"]
        
        for section in required_sections:
            if section not in report:
                logger.warning(f"报告缺少必需章节: {section}")
                return False
        
        # 检查报告长度
        if len(report) < 500:
            logger.warning("报告内容过短")
            return False
        
        return True
    
    async def run(self, days: int = 3, save_intermediate: bool = True) -> Optional[str]:
        """
        运行完整的处理流程
        
        Args:
            days: 获取最近N天的数据
            save_intermediate: 是否保存中间结果
            
        Returns:
            最终报告内容
        """
        logger.info("=" * 60)
        logger.info("GeminiAIReportAgent 开始运行")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        # 1. 获取数据
        news_items = await self.fetch_articles_from_db(days=days)
        if not news_items:
            logger.error("未获取到任何新闻数据")
            return None
        
        # 2. 过滤
        news_items = await self.step1_filter(news_items)
        if save_intermediate:
            self._save_intermediate_results(news_items, "01_filtered")
        
        # 3. 归类
        news_items = await self.step2_cluster(news_items)
        if save_intermediate:
            self._save_intermediate_results(news_items, "02_clustered")
        
        # 4. 去重
        news_items = await self.step3_deduplicate(news_items)
        if save_intermediate:
            self._save_intermediate_results(news_items, "03_deduplicated")
        
        # 5. 排序
        news_items = await self.step4_rank(news_items)
        if save_intermediate:
            self._save_intermediate_results(news_items, "04_ranked")
        
        # 6. 生成报告
        report_content = self.generate_final_report(news_items, quality_check=True)
        
        if report_content:
            # 保存最终报告
            output_dir = Path("final_reports")
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / f"AI_Report_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info("=" * 60)
            logger.info(f"报告生成成功！耗时: {elapsed:.2f}秒")
            logger.info(f"报告保存至: {output_file}")
            logger.info("=" * 60)
            
            return report_content
        else:
            logger.error("报告生成失败")
            return None
    
    def _save_intermediate_results(self, news_items: List[NewsItem], stage: str):
        """保存中间结果"""
        output_dir = Path("final_reports") / "intermediate"
        output_dir.mkdir(exist_ok=True, parents=True)
        
        output_file = output_dir / f"{stage}_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        
        data = [item.to_dict() for item in news_items]
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"中间结果已保存: {output_file}")


if __name__ == "__main__":
    async def test_agent():
        agent = GeminiAIReportAgent(max_retries=2)
        await agent.run(days=3, save_intermediate=True)
    
    asyncio.run(test_agent())

