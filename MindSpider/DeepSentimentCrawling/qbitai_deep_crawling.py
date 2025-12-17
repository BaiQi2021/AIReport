#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量子位深度爬取脚本
爬取量子位官网近两周的文章和评论
"""

import asyncio
import sys
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    import config
    from media_platform.qbitai.core import QbitaiCrawler
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在MindSpider/DeepSentimentCrawling目录下执行此脚本")
    sys.exit(1)


class QbitaiDeepCrawling:
    """量子位深度爬取"""
    
    def __init__(self):
        """初始化"""
        self.crawler = QbitaiCrawler()
    
    async def run_qbitai_crawling(self, days: int = 14) -> Dict:
        """
        执行量子位爬取任务
        
        Args:
            days: 爬取最近多少天的内容，默认14天（近两周）
        
        Returns:
            爬取结果统计
        """
        print(f"🚀 开始执行量子位爬取任务（近 {days} 天）")
        print(f"📍 网址: https://www.qbitai.com/")
        print(f"📅 时间范围: {(datetime.now() - timedelta(days=days)).date()} 到 {datetime.now().date()}")
        
        try:
            # 启动爬虫
            await self.crawler.start()
            
            return {
                "success": True,
                "message": "量子位爬取任务完成"
            }
        except Exception as e:
            print(f"❌ 爬取失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='量子位深度爬取脚本')
    parser.add_argument('--days', type=int, default=14, help='爬取最近多少天的内容（默认14天）')
    parser.add_argument('--headless', action='store_true', default=True, help='无头浏览器模式')
    
    args = parser.parse_args()
    
    # 设置配置
    config.HEADLESS = args.headless
    
    # 执行爬取
    crawler = QbitaiDeepCrawling()
    result = await crawler.run_qbitai_crawling(days=args.days)
    
    if result['success']:
        print(f"✅ {result['message']}")
        sys.exit(0)
    else:
        print(f"❌ {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
