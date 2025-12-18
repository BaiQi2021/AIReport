#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawler Configuration
定义所有爬虫目标网站的配置
"""

from typing import Dict, List

# AI公司爬虫配置
COMPANY_CRAWLERS = {
    'openai': {
        'name': 'OpenAI',
        'enabled': True,
        'priority': 1,
        'description': 'OpenAI官方新闻',
        'urls': {
            'news': 'https://openai.com/news/',
            'news_zh': 'https://openai.com/zh-Hans-CN/news/',
        }
    },
    'anthropic': {
        'name': 'Anthropic',
        'enabled': True,
        'priority': 1,
        'description': 'Anthropic官方新闻和研究',
        'urls': {
            'news': 'https://www.anthropic.com/news',
            'research': 'https://www.anthropic.com/research',
        }
    },
    'google_deepmind': {
        'name': 'Google DeepMind',
        'enabled': True,
        'priority': 1,
        'description': 'Google DeepMind官方博客',
        'urls': {
            'blog': 'https://deepmind.google/blog/',
        }
    },
    'meta': {
        'name': 'Meta AI',
        'enabled': True,
        'priority': 1,
        'description': 'Meta AI研究论文和博客',
        'urls': {
            'publications': 'https://ai.meta.com/results/?content_types%5B0%5D=publication',
            'blog': 'https://ai.meta.com/blog/',
        }
    },
    'qwen': {
        'name': 'Qwen',
        'enabled': True,
        'priority': 1,
        'description': 'Qwen研究进展',
        'urls': {
            'research': 'https://qwen.ai/research',
        }
    },
    'xai': {
        'name': 'xAI',
        'enabled': True,
        'priority': 1,
        'description': 'xAI (Grok)官方新闻',
        'urls': {
            'news': 'https://x.ai/news',
        }
    },
    'microsoft': {
        'name': 'Microsoft AI',
        'enabled': True,
        'priority': 2,
        'description': 'Microsoft AI新闻',
        'urls': {
            'news': 'https://news.microsoft.com/source/topics/ai/',
        }
    },
    'nvidia': {
        'name': 'NVIDIA',
        'enabled': True,
        'priority': 2,
        'description': 'NVIDIA AI新闻',
        'urls': {
            'news': 'https://nvidianews.nvidia.com/',
        }
    },
}

# AI工具博客配置
AI_TOOLS_CRAWLERS = {
    'heygen': {
        'name': 'HeyGen',
        'enabled': True,
        'priority': 2,
        'description': 'AI视频生成工具',
        'url': 'https://www.heygen.com/blog',
    },
    'creatify': {
        'name': 'Creatify',
        'enabled': True,
        'priority': 2,
        'description': 'AI视频创作工具',
        'url': 'https://creatify.ai/zh/blog',
    },
    'synthesia': {
        'name': 'Synthesia',
        'enabled': True,
        'priority': 2,
        'description': 'AI视频生成平台',
        'url': 'https://www.synthesia.io/blog',
    },
    'invideo': {
        'name': 'InVideo AI',
        'enabled': True,
        'priority': 3,
        'description': 'AI视频编辑工具',
        'url': 'https://invideo.io/blog/',
    },
    'veed': {
        'name': 'VEED.IO',
        'enabled': True,
        'priority': 3,
        'description': 'AI视频编辑平台',
        'url': 'https://landing.veed.io/blog',
    },
    'simplified': {
        'name': 'Simplified',
        'enabled': True,
        'priority': 3,
        'description': 'AI内容创作平台',
        'url': 'https://simplified.com/blog',
    },
    'predis': {
        'name': 'Predis.ai',
        'enabled': True,
        'priority': 3,
        'description': 'AI社交媒体工具',
        'url': 'https://predis.ai/resources/blog/',
    },
    'quickads': {
        'name': 'QuickAds',
        'enabled': True,
        'priority': 3,
        'description': 'AI广告创作工具',
        'url': 'https://www.quickads.ai/blogs',
    },
    'lovart': {
        'name': 'Lovat',
        'enabled': True,
        'priority': 3,
        'description': 'AI艺术创作工具',
        'url': 'https://www.lovart.ai/zh/news',
    },
    'cursor': {
        'name': 'Cursor',
        'enabled': True,
        'priority': 2,
        'description': 'AI编程工具',
        'url': 'https://cursor.com/cn/blog',
    },
}

# 新闻网站爬虫配置
NEWS_CRAWLERS = {
    'qbitai': {
        'name': '量子位',
        'enabled': True,
        'priority': 1,
        'description': '国内主要AI科技新闻媒体',
        'url': 'https://www.qbitai.com',
        'crawler_type': 'qbitai',
    },
}

# 爬虫默认配置
DEFAULT_CRAWLER_CONFIG = {
    'days': 7,
    'max_articles_per_source': 20,
    'request_delay': 2,
    'timeout': 30,
    'retry_times': 3,
    'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


def get_enabled_company_crawlers() -> List[Dict]:
    """获取所有启用的公司爬虫"""
    enabled = []
    for key, config in COMPANY_CRAWLERS.items():
        if config.get('enabled', False):
            enabled.append({
                'key': key,
                **config
            })
    enabled.sort(key=lambda x: x.get('priority', 999))
    return enabled


def get_enabled_tools_crawlers() -> List[Dict]:
    """获取所有启用的AI工具爬虫"""
    enabled = []
    for key, config in AI_TOOLS_CRAWLERS.items():
        if config.get('enabled', False):
            enabled.append({
                'key': key,
                **config
            })
    enabled.sort(key=lambda x: x.get('priority', 999))
    return enabled


def get_enabled_news_crawlers() -> List[Dict]:
    """获取所有启用的新闻爬虫"""
    enabled = []
    for key, config in NEWS_CRAWLERS.items():
        if config.get('enabled', False):
            enabled.append({
                'key': key,
                **config
            })
    enabled.sort(key=lambda x: x.get('priority', 999))
    return enabled


def get_crawler_config(crawler_key: str) -> Dict:
    """获取特定爬虫的配置"""
    if crawler_key in COMPANY_CRAWLERS:
        return COMPANY_CRAWLERS[crawler_key]
    elif crawler_key in AI_TOOLS_CRAWLERS:
        return AI_TOOLS_CRAWLERS[crawler_key]
    elif crawler_key in NEWS_CRAWLERS:
        return NEWS_CRAWLERS[crawler_key]
    else:
        return {}
