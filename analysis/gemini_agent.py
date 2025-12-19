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
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time

from openai import OpenAI
import httpx
from sqlalchemy import select, desc, or_, delete

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
                 reference_links: Optional[str] = None,
                 original_id: Optional[str] = None,
                 source_table: Optional[str] = None):
        self.article_id = article_id
        self.title = title
        self.description = description
        self.content = content  # 保存完整内容，在具体使用时再按需截取
        self.url = url
        self.source = source  # 来源：qbitai, openai, google等
        self.publish_time = publish_time
        self.reference_links = reference_links
        
        # 数据库回溯字段
        self.original_id = original_id
        self.source_table = source_table
        
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
    
    def __init__(self, max_retries: int = 5):
        """
        初始化 Agent
        
        Args:
            max_retries: 每个步骤的最大重试次数
        """
        self.api_key = settings.REPORT_ENGINE_API_KEY
        self.base_url = settings.REPORT_ENGINE_BASE_URL
        self.model_name = settings.REPORT_ENGINE_MODEL_NAME or "gemini-3-pro-preview"
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
                    reference_links=art.reference_links,
                    original_id=art.article_id,
                    source_table="qbitai_article"
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
                    reference_links=art.reference_links,
                    original_id=art.article_id,
                    source_table="company_article"
                ))
        
        logger.info(f"共获取 {len(news_items)} 条新闻数据")
        return news_items
    
    async def _delete_articles_from_db(self, items_to_delete: List[NewsItem]):
        """
        从数据库中删除指定的文章
        
        Args:
            items_to_delete: 需要删除的新闻条目列表
        """
        if not items_to_delete:
            return

        logger.info(f"正在从数据库删除 {len(items_to_delete)} 条无效/重复数据...")
        
        # 按表分组
        qbitai_ids = []
        company_ids = []
        
        for item in items_to_delete:
            if not item.original_id or not item.source_table:
                logger.warning(f"无法删除文章 {item.article_id}: 缺少原始ID或表信息")
                continue
                
            if item.source_table == "qbitai_article":
                qbitai_ids.append(item.original_id)
            elif item.source_table == "company_article":
                company_ids.append(item.original_id)
        
        async with get_session() as session:
            try:
                if qbitai_ids:
                    stmt = delete(QbitaiArticle).where(QbitaiArticle.article_id.in_(qbitai_ids))
                    result = await session.execute(stmt)
                    logger.info(f"已删除 {result.rowcount} 条 Qbitai 数据")
                
                if company_ids:
                    stmt = delete(CompanyArticle).where(CompanyArticle.article_id.in_(company_ids))
                    result = await session.execute(stmt)
                    logger.info(f"已删除 {result.rowcount} 条 Company 数据")
                
                await session.commit()
            except Exception as e:
                logger.error(f"删除数据库数据失败: {e}")
                await session.rollback()

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

        items_to_delete = []

        # 1. 预过滤：剔除内容过短或无内容的新闻
        valid_news_items = []
        for item in news_items:
            # 简单的规则过滤：内容长度少于100字符视为无效内容
            # 注意：NewsItem 初始化时已截取前1000字符，这里判断的是截取后的长度
            # 但如果原内容本身就很少，这里也能检测出来
            if item.content and len(item.content.strip()) >= 50:
                valid_news_items.append(item)
            else:
                logger.info(f"预过滤剔除（内容过少）: {item.title} (ID: {item.article_id})")
                items_to_delete.append(item)
        
        # 删除预过滤掉的数据
        if items_to_delete:
            await self._delete_articles_from_db(items_to_delete)
            items_to_delete = [] # 清空列表以便复用

        news_items = valid_news_items
        logger.info(f"待处理新闻数: {len(news_items)}, 批处理大小: {batch_size}")
        
        filtered_items = []
        rejected_items = []
        
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
                            else:
                                rejected_items.append(item)
                    break
                else:
                    logger.warning(f"批次 {i // batch_size + 1} 解析失败，重试 {retry + 1}/{self.max_retries}")
                    if retry == self.max_retries - 1:
                        logger.error(f"批次 {i // batch_size + 1} 处理失败，跳过")
            
            # 避免 API 限流
            await asyncio.sleep(1)
        
        # 删除被剔除的数据
        if rejected_items:
            logger.info(f"正在删除 {len(rejected_items)} 条被过滤的新闻...")
            await self._delete_articles_from_db(rejected_items)
            
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
        deleted_items = []
        
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
            
            prompt = f"""你是一个专业的AI新闻去重专家。以下是描述同一事件的多条新闻，请选出最权威、信息质量最高的**最多三条**。

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
请选择最多三条最权威的新闻保留（如果只有1-3条，可全部保留；如果超过3条，请筛选出最好的3条），其余标记为删除。以 JSON 数组格式返回：
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
                            else:
                                deleted_items.append(item)
                    break
                else:
                    logger.warning(f"事件 {event_id} 去重失败，重试 {retry + 1}/{self.max_retries}")
                    if retry == self.max_retries - 1:
                        # 失败时保留第一条
                        logger.error(f"事件 {event_id} 去重失败，默认保留第一条")
                        items[0].dedup_decision = "保留"
                        items[0].dedup_reason = "去重失败，默认保留"
                        deduplicated_items.append(items[0])
                        # 其余的暂时不动，避免误删
            
            await asyncio.sleep(0.5)
        
        # 删除被去重的数据
        if deleted_items:
            logger.info(f"正在删除 {len(deleted_items)} 条重复新闻...")
            await self._delete_articles_from_db(deleted_items)
            
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
                                item.tech_impact * 0.5 +
                                item.industry_scope * 0.3 +
                                item.hype_score * 0.2
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

    def search_arxiv(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        搜索 arXiv 论文
        
        Args:
            query: 搜索查询字符串 (例如 "all:LLM")
            max_results: 最大结果数
            
        Returns:
            论文列表 [{'title': ..., 'url': ..., 'summary': ...}]
        """
        base_url = "http://export.arxiv.org/api/query"
        
        # 简单清理 query
        query = query.replace('"', '%22')
        
        # 构建查询参数
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        # 手动拼接 URL 以确保 encoded 正确，或者使用 urllib.parse.quote 但保留 API 特殊字符
        # 这里使用 urllib.parse.urlencode 应该足够安全
        try:
            query_string = urllib.parse.urlencode(params, safe=':')
            url = f"{base_url}?{query_string}"
            
            logger.info(f"正在调用 arXiv API: {url}")
            
            # 遵守 API 规则，增加延时
            time.sleep(3)
            
            # 设置 User-Agent
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'AIReportAgent/1.0 (mailto:your_email@example.com)'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                xml_data = response.read()
                
            root = ET.fromstring(xml_data)
            # 处理 namespace
            # Atom feed 通常有默认 namespace，ElementTree 解析时需要在 tag 前加 {uri}
            # 获取 root 的 namespace
            ns_match = root.tag.split('}')[0] + '}' if '}' in root.tag else ''
            
            papers = []
            entries = root.findall(f'{ns_match}entry')
            
            for entry in entries:
                try:
                    title_elem = entry.find(f'{ns_match}title')
                    id_elem = entry.find(f'{ns_match}id')
                    summary_elem = entry.find(f'{ns_match}summary')
                    published_elem = entry.find(f'{ns_match}published')
                    
                    title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None else "No Title"
                    link = id_elem.text.strip() if id_elem is not None else ""
                    summary = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None else ""
                    published = published_elem.text.strip() if published_elem is not None else ""
                    
                    # 转换 article ID link 到 abstract page link
                    # arXiv API id 通常是 http://arxiv.org/abs/xxxx.xxxx
                    # 有时是 http://arxiv.org/api/xxxx
                    if link:
                        link = link.replace("/api/", "/abs/")
                    
                    papers.append({
                        "title": title,
                        "url": link,
                        "summary": summary[:200] + "...",
                        "published": published,
                        "source": "arXiv",
                        "type": "Paper"
                    })
                except Exception as e:
                    logger.warning(f"解析 arXiv entry 失败: {e}")
                    continue
                
            return papers
            
        except Exception as e:
            logger.error(f"arXiv 搜索失败: {e}")
            return []

    async def step5_fetch_arxiv_papers(self, news_items: List[NewsItem]) -> List[Dict[str, str]]:
        """
        第五步：获取相关 arXiv 论文
        
        Args:
            news_items: 排序后的新闻列表
            
        Returns:
            相关论文列表
        """
        logger.info("=" * 60)
        logger.info("【第五步】获取相关 arXiv 论文...")
        
        # 选取所有 S/A 级新闻，确保覆盖面
        target_items = [item for item in news_items if item.ranking_level in ["S", "A"]]
        
        # 如果 S/A 级太少，补充 B 级前几名
        if len(target_items) < 5:
            b_items = [item for item in news_items if item.ranking_level == "B"]
            target_items.extend(b_items[:5 - len(target_items)])
            
        if not target_items:
            target_items = news_items[:5]
            
        if not target_items:
            return []
            
        # 1. 提取搜索关键词
        titles = "\n".join([f"- {item.title}" for item in target_items])
        prompt = f"""请根据以下 AI 领域的热点新闻标题，构建用于 arXiv 搜索的查询关键词列表。

新闻标题：
{titles}

要求：
1. 分析每条新闻的核心技术实体（如模型名称 "Gemini 3", "Claude Sonnet" 或技术术语 "World Model", "Scaling Law"）。
2. 构建 5-8 个独立的查询字符串，旨在尽可能覆盖这些新闻对应的主题。
3. 格式：每行一个查询字符串，使用 `all:` 或 `ti:` 前缀。
4. 示例：
all:"Gemini 3"
ti:"World Model" AND all:Genie
all:"Large Language Model" AND all:Reasoning

请直接返回查询字符串列表，每行一个。
"""
        response = self._call_llm(prompt)
        if not response:
            queries = ["all:Artificial Intelligence"]
        else:
            queries = [line.strip().strip('`').strip('"') for line in response.split('\n') if line.strip() and not line.strip().startswith('```')]
        
        # 限制查询数量，避免过多请求
        queries = queries[:8]
        logger.info(f"生成的 arXiv 查询: {queries}")
        
        all_papers = []
        seen_ids = set()
        
        # 2. 执行搜索 (串行执行以遵守限流)
        for query in queries:
            if not query:
                continue
            # 清理 query
            if "search_query=" in query:
                query = query.replace("search_query=", "")
                
            # 每个 query 取 5 条，总共可能获取 25-40 条
            papers = self.search_arxiv(query, max_results=5) 
            
            for paper in papers:
                # 使用 URL 作为去重键
                if paper['url'] not in seen_ids:
                    all_papers.append(paper)
                    seen_ids.add(paper['url'])
            
        logger.info(f"共获取到 {len(all_papers)} 篇不重复的 arXiv 论文")
        return all_papers
    
    def _validate_news_item_format(self, content: str) -> Tuple[bool, str]:
        """验证新闻条目的 Markdown 格式"""
        required_patterns = [
            (r"### \*\*.*?\*\*", "标题格式错误，应为 ### **标题**"),
            (r"\[阅读原文\]\(.*?\)", "缺少阅读原文链接或格式错误"),
            (r"> \*\*概要\*\*:.*", "缺少概要或格式错误"),
            (r"\*\*💡内容详解\*\*", "缺少'💡内容详解'分节"),
            (r"- \*\*.*?\*\*", "缺少要点标题或格式错误")
        ]
        
        import re
        for pattern, error_msg in required_patterns:
            if not re.search(pattern, content, re.MULTILINE):
                return False, error_msg
        return True, ""

    def _get_primary_source_url(self, item: NewsItem) -> str:
        """
        获取优先级最高的信源 URL
        
        优先级顺序：
        1. 官方核心信源 (official, blog, github 等)
        2. arXiv 论文
        3. 权威技术媒体
        4. 原始新闻 URL (兜底)
        
        Args:
            item: 新闻条目
            
        Returns:
            优先级最高的 URL
        """
        # 如果新闻本身来自官方源（非量子位等二手媒体），直接返回
        non_official_sources = ["量子位", "qbitai", "36kr", "机器之心", "新智元"]
        if item.source and not any(s.lower() in item.source.lower() for s in non_official_sources):
            return item.url
        
        # 尝试从 reference_links 中选择最佳链接
        if not item.reference_links:
            return item.url
            
        try:
            refs = json.loads(item.reference_links)
            if not refs:
                return item.url
            
            # 定义信源优先级
            priority_order = [
                ("official", 100),      # 官方发布
                ("blog", 90),           # 官方博客
                ("github", 85),         # GitHub Release
                ("arxiv", 80),          # arXiv 论文
                ("paper", 75),          # 论文
                ("announcement", 70),   # 公告
                ("external", 50),       # 外部链接
                ("social", 20),         # 社交媒体
            ]
            
            # 根据 URL 特征和 type 字段判断优先级
            def get_priority(ref: dict) -> int:
                url = ref.get("url", "").lower()
                ref_type = ref.get("type", "").lower()
                
                # 根据 URL 域名判断
                if any(domain in url for domain in ["openai.com", "blog.google", "ai.meta.com", "anthropic.com", "deepmind.google"]):
                    return 100  # 官方核心域名最高优先级
                if "arxiv.org" in url:
                    return 80
                if "github.com" in url:
                    return 85
                    
                # 根据 type 字段判断
                for ptype, score in priority_order:
                    if ptype in ref_type:
                        return score
                        
                return 30  # 默认低优先级
            
            # 按优先级排序并返回最高的
            sorted_refs = sorted(refs, key=get_priority, reverse=True)
            best_ref = sorted_refs[0]
            
            # 只有当最佳链接优先级高于默认时才使用
            if get_priority(best_ref) >= 50:
                return best_ref.get("url", item.url)
                
        except Exception as e:
            logger.warning(f"解析 reference_links 失败: {e}")
        
        return item.url

    async def _generate_event_entries_batch(self, batch_events: List[Dict], candidate_papers: List[Dict] = None) -> List[Dict[str, str]]:
        """
        按事件生成报告条目（每个事件综合其下所有新闻）
        
        Args:
            batch_events: 事件列表，每个事件包含 {"event_id", "best_item", "all_items", "event_score"}
            candidate_papers: 候选 arXiv 论文列表
            
        Returns:
            生成的条目列表，每项包含 {"event_id", "category", "markdown_content"}
        """
        batch_data = []
        for event in batch_events:
            event_id = event["event_id"]
            all_items = event["all_items"]  # 该事件下的所有新闻（去重后保留的，最多3条）
            best_item = event["best_item"]
            
            # 获取优先级最高的官方信源 URL（从最佳新闻中获取）
            primary_url = self._get_primary_source_url(best_item)
            
            # 综合所有新闻的内容
            combined_content = ""
            sources_info = []
            for idx, item in enumerate(all_items, 1):
                item_url = self._get_primary_source_url(item)
                sources_info.append({
                    "source": item.source,
                    "url": item_url,
                    "title": item.title
                })
                combined_content += f"\n--- 来源 {idx}: {item.source} ---\n"
                combined_content += f"标题: {item.title}\n"
                combined_content += f"内容: {item.content}\n"
            
            pub_date = datetime.fromtimestamp(best_item.publish_time).strftime('%Y-%m-%d %H:%M')
            
            batch_data.append({
                "event_id": event_id,
                "primary_title": best_item.title,  # 使用最高分新闻的标题作为主标题
                "primary_url": primary_url,  # 使用优先级最高的官方信源
                "primary_source": best_item.source,
                "publish_time": pub_date,
                "news_count": len(all_items),
                "combined_content": combined_content,  # 综合所有新闻的内容
                "all_sources": sources_info  # 所有来源信息
            })

        # 构建候选论文上下文
        papers_context = ""
        if candidate_papers:
            papers_list = []
            for p in candidate_papers:
                papers_list.append(f"- Title: {p.get('title')}\n  URL: {p.get('url')}")
            papers_context = "\n".join(papers_list)

        prompt = f"""你是一个专业的AI技术分析师。请为以下**事件**生成符合报告格式的Markdown内容块。

**重要说明：**
- 每个事件可能包含多条来自不同来源的新闻报道
- 请综合所有来源的信息，生成一个完整、不重复的事件报告
- 优先使用官方来源的信息，辅以其他来源的补充细节

**候选 arXiv 论文库：**
{papers_context if papers_context else "(无候选论文)"}

**输出要求：**
对于每一个事件，请执行以下操作：
1. **分类**：将其归入以下三类之一：
   - "Infrastructure" (AI基础设施: 芯片, 算力, 框架, 数据工程等)
   - "Model" (AI模型与技术: 基础模型, 算法创新, 训练技术等)
   - "Application" (AI应用与智能体: 具体应用, Agent, 行业落地等)

2. **生成Markdown内容**：严格遵循以下Markdown格式模板生成内容。
   
   **模板格式：**
   ```markdown
   ### **[事件标题 - 基于主标题优化]**
   
   [阅读原文]([primary_url])  `[Publish_Time]`
   
   > **概要**: [综合多个来源，用3-4句话简练概括核心事件]
   
   **💡内容详解**
   (综合所有来源的信息，提炼关键技术点，关键点数量至少大于3点)

    - **关键点大标题 1**
    （需要详细对关键点进行解释，关键点解释的数量根据要点动态调整）
        - **关键点解释1**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        - **关键点解释2**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        ……

    - **关键点大标题 2**
    （需要详细对关键点进行解释，关键点解释的数量根据要点动态调整）
        - **关键点解释1**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        - **关键点解释2**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        ……

    - **关键点大标题 3**
    （需要详细对关键点进行解释，关键点解释的数量根据要点动态调整）
        - **关键点解释1**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        - **关键点解释2**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）   
        ……
    ……

    [相关论文]([URL])
   ```

   **关于 [阅读原文] 的特别说明：**
   - 必须使用提供的 primary_url，这是优先级最高的官方核心信源
   - 禁止使用量子位、36kr等二手媒体链接

   **关于 [相关论文] 的特别说明：**
   - 请在"候选 arXiv 论文库"中查找与当前事件**高度相关**的论文
   - 如果找到匹配的论文，请将 `[相关论文]([URL])` 替换为实际的论文链接
   - **如果没有找到高度相关的论文，请务必删除这一行**

**事件数据：**
```json
{json.dumps(batch_data, ensure_ascii=False, indent=2)}
```

**返回格式：**
请返回一个 JSON 数组，包含每个事件的生成结果：
```json
[
  {{
    "event_id": "xxx",
    "category": "Infrastructure", 
    "markdown_content": "### **标题**..."
  }},
  ...
]
```
请只返回 JSON。
"""
        
        for retry in range(self.max_retries):
            response = self._call_llm(prompt, temperature=0.3)
            results = self._parse_json_response(response)
            if results:
                # 验证格式
                valid_results = []
                errors = []
                for item in results:
                    is_valid, error = self._validate_news_item_format(item.get("markdown_content", ""))
                    if is_valid:
                        valid_results.append(item)
                    else:
                        errors.append(f"事件 '{item.get('event_id', 'Unknown')}' 格式错误: {error}")
                
                if not errors:
                    return valid_results
                
                # 如果有错误且还有重试次数，将错误加入 prompt 重试
                logger.warning(f"批次生成存在格式错误: {'; '.join(errors)}")
                if retry < self.max_retries - 1:
                    prompt += f"\n\n**修正要求**: 上次生成存在以下格式错误，请严格修正：\n" + "\n".join(errors)
                    continue
                else:
                    return valid_results
            
            await asyncio.sleep(1)
            
        return []

    async def _generate_news_entries_batch(self, batch_items: List[NewsItem], candidate_papers: List[Dict] = None) -> List[Dict[str, str]]:
        """
        分批生成新闻条目内容 (并发处理)
        
        Args:
            batch_items: 这一批的新闻列表
            candidate_papers: 候选 arXiv 论文列表
            
        Returns:
            生成的条目列表，每项包含 {"article_id", "category", "markdown_content"}
        """
        batch_data = []
        for item in batch_items:
            pub_date = datetime.fromtimestamp(item.publish_time).strftime('%Y-%m-%d %H:%M')
            
            # 获取优先级最高的官方信源 URL
            primary_url = self._get_primary_source_url(item)
            
            batch_data.append({
                "article_id": item.article_id,
                "title": item.title,
                "source": item.source,
                "url": primary_url,  # 使用优先级最高的官方信源
                "publish_time": pub_date,
                "content": item.content,  # 使用完整内容进行深度阅读
            })

        # 构建候选论文上下文
        papers_context = ""
        if candidate_papers:
            papers_list = []
            for p in candidate_papers:
                papers_list.append(f"- Title: {p.get('title')}\n  URL: {p.get('url')}")
            papers_context = "\n".join(papers_list)

        prompt = f"""你是一个专业的AI技术分析师。请为以下新闻生成符合报告格式的Markdown内容块。

**候选 arXiv 论文库：**
{papers_context if papers_context else "(无候选论文)"}

**输出要求：**
对于每一条新闻，请执行以下操作：
1. **分类**：将其归入以下三类之一：
   - "Infrastructure" (AI基础设施: 芯片, 算力, 框架, 数据工程等)
   - "Model" (AI模型与技术: 基础模型, 算法创新, 训练技术等)
   - "Application" (AI应用与智能体: 具体应用, Agent, 行业落地等)

2. **生成Markdown内容**：严格遵循以下Markdown格式模板生成内容。
   
   **模板格式：**
   ```markdown
   ### **[新闻标题]**
   
   [阅读原文]([URL])  `[Publish_Time]`
   
   > **概要**: [3-4句话简练概括核心事件]
   
   **💡内容详解**
   (内容详解是对关键技术的罗列，关键点数量至少大于3点，请对关键技术进行详细解读，此处不用添加概述)

    - **关键点大标题 1**
    （需要详细对关键点进行解释，关键点解释的数量根据要点动态调整）
        - **关键点解释1**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        - **关键点解释2**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        ……

    - **关键点大标题 2**
    （需要详细对关键点进行解释，关键点解释的数量根据要点动态调整）
        - **关键点解释1**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        - **关键点解释2**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        ……

    - **关键点大标题 3**
    （需要详细对关键点进行解释，关键点解释的数量根据要点动态调整）
        - **关键点解释1**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）
        - **关键点解释2**
        （另起一段详细解释该技术，要有具体技术细节，不超过200字）   
        ……
    ……

    [相关论文]([URL])
   ```

   **关于 [相关论文] 的特别说明：**
   - 请在“候选 arXiv 论文库”中查找与当前新闻**高度相关**的论文（标题或内容匹配）。
   - 如果找到匹配的论文，请将 `[相关论文]([URL])` 替换为实际的论文链接，例如 `[相关论文](https://arxiv.org/abs/2412.xxxxx)`。
   - 如果有多篇相关，可以列出多行，格式均为 `[相关论文](URL)` 或 `[相关论文: Title](URL)`。
   - **如果没有找到高度相关的论文，请务必删除 `[相关论文]([URL])` 这一行，不要保留空行或占位符。**

**新闻数据：**
```json
{json.dumps(batch_data, ensure_ascii=False, indent=2)}
```

**返回格式：**
请返回一个 JSON 数组，包含每条新闻的生成结果：
```json
[
  {{
    "article_id": "xxx",
    "category": "Infrastructure", 
    "markdown_content": "### **标题**..."
  }},
  ...
]
```
请只返回 JSON。
"""
        
        for retry in range(self.max_retries):
            response = self._call_llm(prompt, temperature=0.3)
            results = self._parse_json_response(response)
            if results:
                # 验证格式
                valid_results = []
                errors = []
                for item in results:
                    is_valid, error = self._validate_news_item_format(item.get("markdown_content", ""))
                    if is_valid:
                        valid_results.append(item)
                    else:
                        errors.append(f"文章 '{item.get('title', 'Unknown')}' 格式错误: {error}")
                
                if not errors:
                    return valid_results
                
                # 如果有错误且还有重试次数，将错误加入 prompt 重试
                logger.warning(f"批次生成存在格式错误: {'; '.join(errors)}")
                if retry < self.max_retries - 1:
                    prompt += f"\n\n**修正要求**: 上次生成存在以下格式错误，请严格修正，确保Markdown格式完全符合模板：\n" + "\n".join(errors)
                    continue
                else:
                    # 最后一次重试，仅返回有效的
                    return valid_results
            
            await asyncio.sleep(1)
            
        return []

    async def generate_final_report(self, news_items: List[NewsItem], arxiv_papers: List[Dict] = None, quality_check: bool = True, days: int = 7) -> Optional[str]:
        """
        生成最终报告 (多轮生成模式)
        
        Args:
            news_items: 排序后的新闻列表
            arxiv_papers: 相关 arXiv 论文列表
            quality_check: 是否进行质量检查
            days: 报告覆盖的天数范围
            
        Returns:
            报告内容
        """
        logger.info("=" * 60)
        logger.info("【第六步】生成最终报告 (多轮生成模式)...")
        
        if not news_items:
            logger.warning("没有新闻可以生成报告")
            return None

        # 1. 准备数据：按事件整体排序，每个事件使用最高分新闻作为排序依据
        # 首先按 event_id 分组
        event_groups = defaultdict(list)
        for item in news_items:
            event_groups[item.event_id].append(item)
        
        # 每个事件选择最高分的新闻作为排序代表，但保留该事件的全部新闻用于生成
        event_representatives = []
        for event_id, items in event_groups.items():
            # 按 final_score 排序
            sorted_event_items = sorted(items, key=lambda x: x.final_score, reverse=True)
            best_item = sorted_event_items[0]
            event_representatives.append({
                "event_id": event_id,
                "best_item": best_item,
                "event_score": best_item.final_score,  # 事件分数 = 代表新闻的分数
                "all_items": sorted_event_items  # 保留该事件的全部新闻（去重后最多3条）
            })
        
        # 按事件分数排序
        event_representatives.sort(key=lambda x: x["event_score"], reverse=True)
        
        # 取前10个事件
        target_count = 10
        top_events = event_representatives[:target_count]
        
        logger.info(f"共识别 {len(event_groups)} 个独立事件，将为前 {len(top_events)} 个事件生成详细报告")
        for i, e in enumerate(top_events, 1):
            logger.info(f"  [{i}] {e['event_id']}: 分数={e['event_score']:.2f}, 包含 {len(e['all_items'])} 条新闻, 代表: {e['best_item'].title[:40]}...")

        # 2. 分批生成内容 (按事件生成，每个事件综合其下所有新闻)
        batch_size = 3  # 每批处理3个事件
        generated_entries = []
        
        for i in range(0, len(top_events), batch_size):
            batch_events = top_events[i:i + batch_size]
            logger.info(f"正在生成报告详情：批次 {i // batch_size + 1} (共 {len(batch_events)} 个事件)")
            
            # 按事件生成内容，每个事件使用其下所有新闻
            entries = await self._generate_event_entries_batch(batch_events, candidate_papers=arxiv_papers)
            if entries:
                generated_entries.extend(entries)
            else:
                logger.error(f"批次 {i // batch_size + 1} 生成失败")
        
        # 用于后续速览生成的代表新闻列表
        valid_items = [e["best_item"] for e in top_events]

        # 3. 组织内容 并 提取已使用的链接
        # 建立 article_id 到 news_item 的映射，方便获取额外信息
        item_map = {item.article_id: item for item in valid_items}
        
        category_map = {
            "Infrastructure": [],
            "Model": [],
            "Application": []
        }
        
        # 用于记录在正文中已经出现过的链接，避免在拓展阅读中重复
        used_urls = set()
        link_pattern = re.compile(r'\[.*?\]\((https?://.*?)\)')
        
        for entry in generated_entries:
            cat = entry.get("category", "Model")
            if cat not in category_map:
                cat = "Model"  # Fallback
            
            content = entry.get("markdown_content", "")
            category_map[cat].append(content)
            
            # 提取正文中的所有链接
            found_links = link_pattern.findall(content)
            for link in found_links:
                # 简单标准化
                clean_link = link.strip().rstrip('/')
                used_urls.add(clean_link)
                # 针对 arXiv，同时记录 abs 和 pdf 版本以防万一
                if "arxiv.org/abs/" in clean_link:
                    used_urls.add(clean_link.replace("/abs/", "/pdf/"))
                elif "arxiv.org/pdf/" in clean_link:
                    used_urls.add(clean_link.replace("/pdf/", "/abs/"))

        # 4. 生成"本期速览" (使用与详细报告相同的 valid_items)
        top_items = valid_items  # 速览和详细报告使用相同的新闻列表
        overview_prompt = f"""请为以下新闻生成"本期速览"列表。
要求：
- 每条新闻用一行 Markdown 列表项表示。
- 格式：* **[[标签]]** [**新闻标题**]: [1-2句话核心看点]
- 标签示例：[大模型], [芯片], [应用]等
- 必须严格遵守上述格式，不要添加其他内容。

新闻数据：
{json.dumps([{"title": item.title, "description": item.description} for item in top_items], ensure_ascii=False, indent=2)}

请直接返回 Markdown 列表。
"""
        overview_content = self._call_llm(overview_prompt) or "生成失败"
        
        # 简单验证概览格式
        if "**[[" not in overview_content:
             logger.warning("概览格式可能不符合要求，尝试修复...")
             # 简单的重试逻辑
             overview_prompt += "\n\n**修正要求**: 上次生成格式不正确。请确保每行以 '* **[[标签]]**' 开头。"
             retry_content = self._call_llm(overview_prompt)
             if retry_content and "**[[" in retry_content:
                 overview_content = retry_content

        # 5. 解析“本期速览”标签，构建 标题->标签 映射，便于拓展阅读分组
        title_tag_map = {}
        tag_line_pattern = re.compile(r"\*\s+\*\*\[\[(?P<tag>.+?)\]\]\*\*\s+\[\*\*(?P<title>.+?)\*\*\]")
        for line in overview_content.splitlines():
            m = tag_line_pattern.search(line)
            if m:
                title_tag_map[m.group("title").strip()] = m.group("tag").strip()

        # 建立 event_id -> category 的映射 (用于非 Top 10 新闻的标签回退)
        # 同时建立 article_id -> category 的映射
        id_category_map = {}
        event_category_map = {}
        for entry in generated_entries:
            cat = entry.get("category", "Model")
            # 映射英文分类到中文标签
            cn_cat = {
                "Infrastructure": "[基础设施]",
                "Model": "[模型与技术]",
                "Application": "[应用与智能体]"
            }.get(cat, "[其他]")
            event_id = entry.get("event_id")
            event_category_map[event_id] = cn_cat
            # 同时为该事件下的所有文章建立映射
            for e in top_events:
                if e["event_id"] == event_id:
                    for item in e["all_items"]:
                        id_category_map[item.article_id] = cn_cat
                    break

        # 6. 生成“拓展阅读” (Reference Links)
        # 这里收集所有新闻（包括 C 级）的参考链接，以及 arXiv 论文
        reference_section = ""
        # 候选链接列表，结构: {'markdown': str, 'type': 'arxiv'|'other', 'tag': str}
        candidates = []
        
        seen_urls = set(used_urls)
        used_arxiv_urls = {u for u in used_urls if "arxiv.org" in u}
        
        def is_valid_ref_link(url: str, title: str) -> bool:
            if not url or not title:
                return False
            # 过滤社交分享链接
            if any(x in url for x in ["facebook.com/sharer", "twitter.com/intent", "linkedin.com/share", "reddit.com/submit", "weibo.com", "service.weibo.com"]):
                return False
            # 过滤通用主页 (例如 https://blog.google/ )
            # 简单的启发式：如果 URL 很短或者是根域名，可能不是具体的文章
            if url.count('/') < 3: 
                 return False
            return True
        
        # 6.1 收集独立 arXiv 论文
        if arxiv_papers:
            for paper in arxiv_papers:
                url = paper['url']
                # 如果该论文已在正文中引用，则不放入拓展阅读
                if url in used_arxiv_urls:
                    continue
                    
                if url not in seen_urls:
                    candidates.append({
                        "markdown": f"* [{paper['title']}]({url}) - arXiv",
                        "type": "arxiv",
                        "tag": "[前沿研究]"
                    })
                    seen_urls.add(url)
        
        # 6.2 收集新闻参考链接
        for item in news_items:
            if not item.reference_links:
                continue
                
            # 确定标签
            tag = title_tag_map.get(item.title)
            if not tag:
                # 回退到分类
                tag = id_category_map.get(item.article_id, "[行业动态]")
            
            try:
                refs = json.loads(item.reference_links)
                for ref in refs:
                    url = ref.get('url', '')
                    title = ref.get('title', 'Ref')
                    
                    if url and url not in seen_urls and is_valid_ref_link(url, title):
                        is_arxiv = "arxiv.org" in url
                        source_tag = f" - {ref.get('type', 'Reference')}"
                        
                        candidates.append({
                            "markdown": f"* [{title}]({url}){source_tag}",
                            "type": "arxiv" if is_arxiv else "other",
                            "tag": tag
                        })
                        seen_urls.add(url)
            except:
                pass
        
        # 6.3 筛选逻辑 (Total 25, Arxiv 15, Other 10)
        MAX_TOTAL = 25
        TARGET_ARXIV = 15 # 60%
        
        arxiv_candidates = [c for c in candidates if c['type'] == 'arxiv']
        other_candidates = [c for c in candidates if c['type'] == 'other']
        
        final_list = []
        
        # 1. 优先取 arXiv
        take_arxiv = min(len(arxiv_candidates), TARGET_ARXIV)
        final_list.extend(arxiv_candidates[:take_arxiv])
        
        # 2. 填补其他
        remaining_slots = MAX_TOTAL - len(final_list)
        take_other = min(len(other_candidates), remaining_slots)
        final_list.extend(other_candidates[:take_other])
        
        # 3. 如果还有空位且有剩余 arXiv，继续填
        if len(final_list) < MAX_TOTAL and len(arxiv_candidates) > take_arxiv:
            rest_slots = MAX_TOTAL - len(final_list)
            final_list.extend(arxiv_candidates[take_arxiv : take_arxiv + rest_slots])
            
        # 6.4 按标签分组输出
        grouped_links = defaultdict(list)
        for item in final_list:
            grouped_links[item['tag']].append(item['markdown'])
            
        sections = []
        # 输出 Top 标签 (按速览顺序)
        sorted_top_tags = []
        for t in title_tag_map.values():
            if t not in sorted_top_tags: sorted_top_tags.append(t)
            
        for tag in sorted_top_tags:
            if tag in grouped_links:
                sections.append(f"### {tag}\n" + chr(10).join(grouped_links[tag]))
                del grouped_links[tag]
        
        # 输出 [前沿研究] (arXiv)
        if "[前沿研究]" in grouped_links:
             sections.append(f"### [前沿研究]\n" + chr(10).join(grouped_links["[前沿研究]"]))
             del grouped_links["[前沿研究]"]
             
        # 输出剩余
        for tag, links in grouped_links.items():
            sections.append(f"### {tag}\n" + chr(10).join(links))
            
        reference_section = "\n\n".join(sections)

        # 6. 最终组装
        # 使用 days 参数计算日期范围，而不是根据新闻发布时间
        today = datetime.now()
        date_range_end = today.strftime('%Y-%m-%d')
        date_range_start = (today - timedelta(days=days - 1)).strftime('%Y-%m-%d')

        final_report = f"""# AI 前沿动态速报 ({date_range_start} 至 {date_range_end})

## ⚡ 本期速览

{overview_content}

---

## 1. AI 基础设施

{chr(10).join(category_map["Infrastructure"]) if category_map["Infrastructure"] else "*(本期无相关内容)*"}

---

## 2. AI 模型与技术

{chr(10).join(category_map["Model"]) if category_map["Model"] else "*(本期无相关内容)*"}

---

## 3. AI 应用与智能体

{chr(10).join(category_map["Application"]) if category_map["Application"] else "*(本期无相关内容)*"}

---

## 拓展阅读

{reference_section}
"""
        return final_report

    def generate_final_report_old(self, news_items: List[NewsItem], quality_check: bool = True) -> Optional[str]:
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
4. 如果新闻数据中提供了"原始来源"，阅读原文的链接必须使用官方核心信源来源URL，禁止使用量子位自身链接
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
            
        # 6. 获取 arXiv 论文
        arxiv_papers = await self.step5_fetch_arxiv_papers(news_items)
        if save_intermediate:
            # 保存 arXiv 结果（简单包装一下以便复用保存逻辑，或者直接存json）
            arxiv_output_dir = Path("final_reports") / "intermediate"
            arxiv_output_dir.mkdir(exist_ok=True, parents=True)
            arxiv_output_file = arxiv_output_dir / f"05_arxiv_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
            with open(arxiv_output_file, 'w', encoding='utf-8') as f:
                json.dump(arxiv_papers, f, ensure_ascii=False, indent=2)
            logger.info(f"中间结果已保存: {arxiv_output_file}")
        
        # 7. 生成报告
        report_content = await self.generate_final_report(news_items, arxiv_papers=arxiv_papers, quality_check=True, days=days)
        
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

