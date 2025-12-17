# -*- coding: utf-8 -*-
# @Author  : MindSpider
# @Time    : 2025/12/16
# @Desc    : 量子位爬虫辅助函数

from datetime import datetime
from typing import Dict, List, Optional


def parse_article_list(html_content: str) -> List[Dict]:
    """解析文章列表"""
    articles = []
    # HTML解析逻辑
    return articles


def parse_article_detail(html_content: str) -> Dict:
    """解析文章详情"""
    article = {
        'title': '',
        'content': '',
        'author': '',
        'publish_time': '',
    }
    # HTML解析逻辑
    return article


def parse_comments(html_content: str) -> List[Dict]:
    """解析评论"""
    comments = []
    # HTML解析逻辑
    return comments
