#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Scheduler with Concurrent Execution and Incremental Updates
增强的调度器：支持并发执行和增量更新
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Callable
from sqlalchemy import select, func

from crawler import utils
from crawler.crawler_config import (
    get_enabled_company_crawlers,
    get_enabled_news_crawlers,
)
from database.models import CompanyArticle, QbitaiArticle
from database.db_session import get_session

# 导入所有爬虫
from crawler.qbitai_scraper import run_crawler as run_qbitai_crawler
from crawler.openai_scraper import run_openai_crawler
from crawler.anthropic_scraper import run_anthropic_crawler
from crawler.google_ai_scraper import run_google_ai_crawler
from crawler.china_ai_scraper import run_china_ai_crawler
from crawler.meta_microsoft_scraper import run_meta_microsoft_crawler
from crawler.news_scraper import run_jiqizhixin_crawler, run_xinzhiyuan_crawler

logger = utils.setup_logger()


class IncrementalUpdateManager:
    """增量更新管理器"""
    
    @staticmethod
    async def get_latest_article_time(company: str = None) -> datetime:
        """获取某公司最新文章的时间"""
        try:
            async with get_session() as session:
                if company:
                    stmt = select(func.max(CompanyArticle.publish_time)).where(
                        CompanyArticle.company == company
                    )
                else:
                    stmt = select(func.max(CompanyArticle.publish_time))
                
                result = await session.execute(stmt)
                max_timestamp = result.scalar()
                
                if max_timestamp:
                    return datetime.fromtimestamp(max_timestamp)
                else:
                    # 如果没有数据，返回7天前
                    return datetime.now() - timedelta(days=7)
        except Exception as e:
            logger.error(f"Failed to get latest article time: {e}")
            return datetime.now() - timedelta(days=7)
    
    @staticmethod
    async def get_latest_news_time(source: str = None) -> datetime:
        """获取某新闻源最新文章的时间"""
        try:
            async with get_session() as session:
                if source:
                    # 根据article_id前缀判断来源
                    stmt = select(func.max(QbitaiArticle.publish_time)).where(
                        QbitaiArticle.article_id.like(f"{source}_%")
                    )
                else:
                    stmt = select(func.max(QbitaiArticle.publish_time))
                
                result = await session.execute(stmt)
                max_timestamp = result.scalar()
                
                if max_timestamp:
                    return datetime.fromtimestamp(max_timestamp)
                else:
                    return datetime.now() - timedelta(days=7)
        except Exception as e:
            logger.error(f"Failed to get latest news time: {e}")
            return datetime.now() - timedelta(days=7)
    
    @staticmethod
    async def should_crawl(source: str, source_type: str = 'company') -> bool:
        """判断是否需要爬取（基于最后更新时间）"""
        try:
            if source_type == 'company':
                latest_time = await IncrementalUpdateManager.get_latest_article_time(source)
            else:
                latest_time = await IncrementalUpdateManager.get_latest_news_time(source)
            
            # 如果最新文章超过1小时，则需要爬取
            time_diff = datetime.now() - latest_time
            should_crawl = time_diff > timedelta(hours=1)
            
            if should_crawl:
                logger.info(f"Source {source} needs crawling (last update: {time_diff.total_seconds()/3600:.1f}h ago)")
            else:
                logger.info(f"Source {source} is up to date (last update: {time_diff.total_seconds()/60:.1f}m ago)")
            
            return should_crawl
        except Exception as e:
            logger.error(f"Error checking if should crawl {source}: {e}")
            return True  # 出错时默认爬取


class ConcurrentScheduler:
    """并发调度器"""
    
    def __init__(self, days: int = 7, max_concurrent: int = 3, use_incremental: bool = True):
        """
        Args:
            days: 爬取天数
            max_concurrent: 最大并发数
            use_incremental: 是否使用增量更新
        """
        self.days = days
        self.max_concurrent = max_concurrent
        self.use_incremental = use_incremental
        self.results = {
            'total_crawlers': 0,
            'success_crawlers': 0,
            'failed_crawlers': 0,
            'skipped_crawlers': 0,
            'crawlers': []
        }
        self.incremental_manager = IncrementalUpdateManager()
    
    async def run_crawler_with_tracking(
        self,
        crawler_name: str,
        crawler_key: str,
        crawler_func: Callable,
        source_type: str = 'company'
    ):
        """运行单个爬虫并跟踪结果"""
        self.results['total_crawlers'] += 1
        
        try:
            # 增量更新检查
            if self.use_incremental:
                should_crawl = await self.incremental_manager.should_crawl(crawler_key, source_type)
                if not should_crawl:
                    logger.info(f"⏭️  Skipping {crawler_name} (up to date)")
                    self.results['skipped_crawlers'] += 1
                    self.results['crawlers'].append({
                        'name': crawler_name,
                        'key': crawler_key,
                        'status': 'skipped',
                        'reason': 'up_to_date'
                    })
                    return
            
            logger.info(f"🎯 Starting {crawler_name}...")
            start_time = datetime.now()
            
            await crawler_func(days=self.days)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.results['success_crawlers'] += 1
            self.results['crawlers'].append({
                'name': crawler_name,
                'key': crawler_key,
                'status': 'success',
                'duration': duration
            })
            
            logger.info(f"✅ {crawler_name} completed in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ {crawler_name} failed: {e}")
            self.results['failed_crawlers'] += 1
            self.results['crawlers'].append({
                'name': crawler_name,
                'key': crawler_key,
                'status': 'failed',
                'error': str(e)
            })
    
    async def run_company_crawlers_concurrent(self):
        """并发运行公司爬虫"""
        enabled_crawlers = get_enabled_company_crawlers()
        
        logger.info("=" * 80)
        logger.info(f"📊 Running {len(enabled_crawlers)} company crawlers (max concurrent: {self.max_concurrent})")
        logger.info("=" * 80)
        
        # 创建爬虫任务映射
        crawler_map = {
            'openai': ('OpenAI', run_openai_crawler),
            'anthropic': ('Anthropic', run_anthropic_crawler),
            'google': ('Google AI & DeepMind', run_google_ai_crawler),
            'zhipu': ('Zhipu AI', run_china_ai_crawler),
            'alibaba': ('Alibaba Qwen', run_china_ai_crawler),
            'moonshot': ('Moonshot AI', run_china_ai_crawler),
            'meta': ('Meta AI', run_meta_microsoft_crawler),
            'microsoft': ('Microsoft AI', run_meta_microsoft_crawler),
        }
        
        # 创建任务
        tasks = []
        for crawler_config in enabled_crawlers:
            crawler_key = crawler_config['key']
            if crawler_key in crawler_map:
                name, func = crawler_map[crawler_key]
                task = self.run_crawler_with_tracking(name, crawler_key, func, 'company')
                tasks.append(task)
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def run_with_semaphore(task):
            async with semaphore:
                await task
                await asyncio.sleep(2)  # 爬虫间延迟
        
        # 并发执行
        await asyncio.gather(*[run_with_semaphore(task) for task in tasks])
    
    async def run_news_crawlers_concurrent(self):
        """并发运行新闻爬虫"""
        enabled_crawlers = get_enabled_news_crawlers()
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📰 Running {len(enabled_crawlers)} news crawlers (max concurrent: {self.max_concurrent})")
        logger.info("=" * 80)
        
        # 创建爬虫任务映射
        crawler_map = {
            'qbitai': ('量子位', run_qbitai_crawler),
            'jiqizhixin': ('机器之心', run_jiqizhixin_crawler),
            'xinzhiyuan': ('新智元', run_xinzhiyuan_crawler),
        }
        
        # 创建任务
        tasks = []
        for crawler_config in enabled_crawlers:
            crawler_key = crawler_config['key']
            if crawler_key in crawler_map:
                name, func = crawler_map[crawler_key]
                task = self.run_crawler_with_tracking(name, crawler_key, func, 'news')
                tasks.append(task)
        
        # 使用信号量控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def run_with_semaphore(task):
            async with semaphore:
                await task
                await asyncio.sleep(2)
        
        # 并发执行
        await asyncio.gather(*[run_with_semaphore(task) for task in tasks])
    
    async def run_all(self):
        """运行所有爬虫"""
        logger.info("🚀" * 40)
        logger.info("   AI REPORT - CONCURRENT CRAWLER SCHEDULER")
        logger.info("🚀" * 40)
        logger.info(f"📅 Date Range: Last {self.days} days")
        logger.info(f"⚡ Max Concurrent: {self.max_concurrent}")
        logger.info(f"🔄 Incremental Update: {'Enabled' if self.use_incremental else 'Disabled'}")
        logger.info(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")
        
        overall_start = datetime.now()
        
        # 并发运行公司爬虫
        await self.run_company_crawlers_concurrent()
        
        # 并发运行新闻爬虫
        await self.run_news_crawlers_concurrent()
        
        overall_end = datetime.now()
        overall_duration = (overall_end - overall_start).total_seconds()
        
        # 打印总结
        self.print_summary(overall_duration)
    
    def print_summary(self, total_duration: float):
        """打印执行摘要"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 CRAWLER EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Crawlers: {self.results['total_crawlers']}")
        logger.info(f"✅ Success: {self.results['success_crawlers']}")
        logger.info(f"⏭️  Skipped: {self.results['skipped_crawlers']}")
        logger.info(f"❌ Failed: {self.results['failed_crawlers']}")
        logger.info(f"⏱️  Total Duration: {total_duration:.2f}s ({total_duration/60:.2f} minutes)")
        
        if self.use_incremental:
            time_saved = self.results['skipped_crawlers'] * 30  # 假设每个爬虫平均30秒
            logger.info(f"⚡ Time Saved (Incremental): ~{time_saved}s")
        
        logger.info("")
        
        if self.results['crawlers']:
            logger.info("Crawler Details:")
            logger.info("-" * 80)
            for crawler in self.results['crawlers']:
                status_icon = {
                    'success': '✅',
                    'failed': '❌',
                    'skipped': '⏭️'
                }.get(crawler['status'], '❓')
                
                if crawler['status'] == 'success':
                    logger.info(f"{status_icon} {crawler['name']:25} | Duration: {crawler.get('duration', 0):.2f}s")
                elif crawler['status'] == 'skipped':
                    logger.info(f"{status_icon} {crawler['name']:25} | Reason: {crawler.get('reason', 'unknown')}")
                else:
                    logger.info(f"{status_icon} {crawler['name']:25} | Error: {crawler.get('error', 'Unknown')[:50]}")
        
        logger.info("=" * 80)
        logger.info(f"⏰ End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("🎉 All crawlers completed!")
        logger.info("=" * 80)


async def run_all_crawlers_concurrent(days: int = 7, max_concurrent: int = 3, use_incremental: bool = True):
    """并发运行所有爬虫的便捷函数"""
    scheduler = ConcurrentScheduler(
        days=days,
        max_concurrent=max_concurrent,
        use_incremental=use_incremental
    )
    await scheduler.run_all()
    return scheduler.results


if __name__ == "__main__":
    asyncio.run(run_all_crawlers_concurrent(days=7, max_concurrent=3, use_incremental=True))

