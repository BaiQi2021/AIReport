#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeminiAIReportAgent 测试脚本
用于快速测试 Agent 的各个功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.gemini_agent import GeminiAIReportAgent, NewsItem
from crawler import utils

logger = utils.logger


async def test_fetch_articles():
    """测试数据获取"""
    logger.info("=" * 60)
    logger.info("测试：数据获取")
    logger.info("=" * 60)
    
    agent = GeminiAIReportAgent()
    articles = await agent.fetch_articles_from_db(days=3, limit=50)
    
    logger.info(f"获取到 {len(articles)} 条新闻")
    if articles:
        logger.info(f"示例新闻：{articles[0].title}")
    
    return articles


async def test_filter(articles):
    """测试过滤功能"""
    logger.info("=" * 60)
    logger.info("测试：过滤功能")
    logger.info("=" * 60)
    
    agent = GeminiAIReportAgent()
    filtered = await agent.step1_filter(articles[:10], batch_size=5)
    
    logger.info(f"过滤前: {len(articles[:10])} 条")
    logger.info(f"过滤后: {len(filtered)} 条")
    
    for item in filtered:
        logger.info(f"  - {item.title[:50]}... ({item.filter_decision}: {item.filter_reason})")
    
    return filtered


async def test_cluster(articles):
    """测试归类功能"""
    logger.info("=" * 60)
    logger.info("测试：归类功能")
    logger.info("=" * 60)
    
    agent = GeminiAIReportAgent()
    
    # 先过滤
    filtered = await agent.step1_filter(articles[:15], batch_size=10)
    
    # 再归类
    clustered = await agent.step2_cluster(filtered, batch_size=10)
    
    # 按事件分组
    from collections import defaultdict
    events = defaultdict(list)
    for item in clustered:
        events[item.event_id].append(item)
    
    logger.info(f"识别出 {len(events)} 个独立事件")
    for event_id, items in sorted(events.items(), key=lambda x: len(x[1]), reverse=True):
        logger.info(f"  - 事件 {event_id}: {len(items)} 条新闻")
        for item in items:
            logger.info(f"    * {item.title[:50]}...")
    
    return clustered


async def test_deduplicate(articles):
    """测试去重功能"""
    logger.info("=" * 60)
    logger.info("测试：去重功能")
    logger.info("=" * 60)
    
    agent = GeminiAIReportAgent()
    
    # 完整流程：过滤 -> 归类 -> 去重
    filtered = await agent.step1_filter(articles[:20], batch_size=10)
    clustered = await agent.step2_cluster(filtered, batch_size=15)
    deduplicated = await agent.step3_deduplicate(clustered)
    
    logger.info(f"去重前: {len(clustered)} 条")
    logger.info(f"去重后: {len(deduplicated)} 条")
    
    for item in deduplicated:
        logger.info(f"  - {item.title[:50]}... ({item.dedup_reason})")
    
    return deduplicated


async def test_rank(articles):
    """测试排序功能"""
    logger.info("=" * 60)
    logger.info("测试：排序功能")
    logger.info("=" * 60)
    
    agent = GeminiAIReportAgent()
    
    # 完整流程：过滤 -> 归类 -> 去重 -> 排序
    filtered = await agent.step1_filter(articles[:20], batch_size=10)
    clustered = await agent.step2_cluster(filtered, batch_size=15)
    deduplicated = await agent.step3_deduplicate(clustered)
    ranked = await agent.step4_rank(deduplicated, batch_size=10)
    
    logger.info(f"排序完成：")
    logger.info(f"  S级: {sum(1 for x in ranked if x.ranking_level == 'S')} 条")
    logger.info(f"  A级: {sum(1 for x in ranked if x.ranking_level == 'A')} 条")
    logger.info(f"  B级: {sum(1 for x in ranked if x.ranking_level == 'B')} 条")
    logger.info(f"  C级: {sum(1 for x in ranked if x.ranking_level == 'C')} 条")
    
    logger.info("\n前5条新闻：")
    for i, item in enumerate(ranked[:5], 1):
        logger.info(f"  {i}. [{item.ranking_level}] {item.title[:50]}...")
        logger.info(f"     评分: {item.final_score:.2f} (技术:{item.tech_impact}, 行业:{item.industry_scope}, 热度:{item.hype_score})")
    
    return ranked


async def test_full_pipeline():
    """测试完整流程"""
    logger.info("=" * 60)
    logger.info("测试：完整流程")
    logger.info("=" * 60)
    
    agent = GeminiAIReportAgent(max_retries=2)
    report_content = await agent.run(days=3, save_intermediate=True)
    
    if report_content:
        logger.info("✓ 完整流程测试成功")
        logger.info(f"报告长度: {len(report_content)} 字符")
    else:
        logger.error("✗ 完整流程测试失败")


async def main():
    """主测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GeminiAIReportAgent 测试脚本")
    parser.add_argument("--test", type=str, default="all",
                       choices=["all", "fetch", "filter", "cluster", "deduplicate", "rank", "full"],
                       help="指定测试项目")
    
    args = parser.parse_args()
    
    # 初始化数据库
    from database.db_session import init_db
    await init_db()
    
    # 获取测试数据
    articles = []
    if args.test != "full":
        articles = await test_fetch_articles()
        if not articles:
            logger.error("未获取到测试数据，退出")
            return
    
    # 运行测试
    if args.test == "all":
        await test_filter(articles)
        await test_cluster(articles)
        await test_deduplicate(articles)
        await test_rank(articles)
    elif args.test == "fetch":
        pass  # 已经执行
    elif args.test == "filter":
        await test_filter(articles)
    elif args.test == "cluster":
        await test_cluster(articles)
    elif args.test == "deduplicate":
        await test_deduplicate(articles)
    elif args.test == "rank":
        await test_rank(articles)
    elif args.test == "full":
        await test_full_pipeline()
    
    logger.info("=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("测试被用户中断")
    except Exception as e:
        logger.exception(f"测试失败: {e}")

