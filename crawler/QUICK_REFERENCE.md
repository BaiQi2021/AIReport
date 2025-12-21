# Crawler模块快速参考

## 🚀 快速开始

### 运行所有爬虫
```bash
python main.py
```

### 运行特定爬虫
```bash
python main.py --crawler qbitai
python main.py --crawler company  # 所有公司爬虫
python main.py --crawler news     # 所有新闻爬虫
```

### 并发模式
```bash
python main.py --concurrent --max-concurrent 5
```

## 📦 常用导入

```python
# 调度器
from crawler.scheduler import run_all_crawlers, CrawlerScheduler

# 注册中心
from crawler import get_global_registry, CrawlerType

# 基类
from crawler import BaseWebScraper

# 工具
from crawler import setup_logger, get_current_timestamp

# 配置
from crawler.constants import (
    CRAWLER_CONFIGS,
    DEFAULT_CRAWLER_CONFIG,
    SCHEDULER_CONFIG
)
```

## 🔧 常用操作

### 列出所有爬虫
```python
from crawler import get_global_registry

registry = get_global_registry()
registry.list_crawlers()
```

### 运行所有爬虫
```python
from crawler.scheduler import run_all_crawlers

results = await run_all_crawlers(
    days=7,
    max_concurrent=3,
    use_incremental=True
)
```

### 运行特定类型爬虫
```python
from crawler.scheduler import CrawlerScheduler
from crawler import CrawlerType

scheduler = CrawlerScheduler(days=7)
await scheduler.run_crawlers_by_type(CrawlerType.COMPANY)
```

### 动态运行单个爬虫
```python
from crawler import get_global_registry

registry = get_global_registry()
runner = registry.get_crawler_runner('qbitai')
if runner:
    await runner(days=7)
```

## 🆕 添加新爬虫

### 1. 创建爬虫文件
```python
# crawler/my_scraper.py
from crawler import BaseWebScraper
from typing import Dict, List, Optional

class MyScraper(BaseWebScraper):
    def __init__(self):
        super().__init__(
            base_url="https://example.com",
            company_name="example"
        )
    
    async def get_article_list(self, page: int = 1) -> List[Dict]:
        # 实现获取文章列表
        html = await self.fetch_page(self.base_url)
        # ... 解析逻辑
        return articles
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        # 实现获取文章详情
        html = await self.fetch_page(url)
        # ... 解析逻辑
        return article

async def run_my_crawler(days: int = 7):
    """运行爬虫的入口函数"""
    async with MyScraper() as scraper:
        articles = await scraper.get_article_list()
        # ... 处理和保存逻辑
```

### 2. 添加配置
```python
# crawler/constants.py
CRAWLER_CONFIGS = [
    # ... 现有配置 ...
    {
        'key': 'my_crawler',
        'name': 'My Crawler',
        'module': 'crawler.my_scraper',
        'class': 'MyScraper',
        'runner': 'run_my_crawler',
        'type': 'company',  # 或 'news', 'tools'
        'enabled': True,
        'priority': 1,
        'description': '我的爬虫',
        'db_table': 'company_article',
    },
]
```

### 3. 运行测试
```bash
python main.py --crawler my_crawler --days 1
```

## 📁 文件结构

```
crawler/
├── __init__.py              # 模块导出
├── constants.py             # 配置常量 ⭐
├── crawler_registry.py      # 注册中心 ⭐
├── scheduler.py             # 调度器 ⭐
├── base_scraper.py          # 基类 ⭐
├── utils.py                 # 工具函数
├── proxy_pool.py            # 代理池
│
├── anthropic_scraper.py     # 具体爬虫实现
├── google_ai_scraper.py
├── meta_microsoft_scraper.py
├── openai_scraper.py
├── ai_companies_scraper.py
├── qbitai_scraper.py
└── ai_tools_scraper.py
```

## 🎯 核心概念

### 爬虫类型
- `COMPANY` - AI公司官网
- `NEWS` - 新闻媒体
- `TOOLS` - AI工具博客

### 配置文件
- `constants.py` - 所有配置的唯一来源
- 修改配置后无需重启（部分配置）

### 注册中心
- 自动发现和加载爬虫
- 动态导入，无硬编码

### 调度器
- 支持并发执行
- 支持增量更新
- 自动跳过最近更新的数据源

## 🔍 调试技巧

### 查看所有注册的爬虫
```bash
python -c "from crawler import get_global_registry; get_global_registry().list_crawlers()"
```

### 测试单个爬虫
```python
from crawler import get_global_registry

registry = get_global_registry()
crawler_info = registry.get_crawler('qbitai')
print(crawler_info)

# 获取爬虫类
CrawlerClass = registry.get_crawler_class('qbitai')
print(CrawlerClass)

# 获取runner函数
runner = registry.get_crawler_runner('qbitai')
print(runner)
```

### 测试爬虫运行
```bash
# 只爬取1天的数据，快速测试
python main.py --crawler qbitai --days 1 --skip-report
```

## ⚙️ 配置参数

### 调度器配置
```python
SCHEDULER_CONFIG = {
    'max_concurrent': 3,            # 最大并发数
    'use_incremental': True,        # 增量更新
    'crawler_delay': 2,             # 爬虫间延迟(秒)
    'incremental_threshold': 3600,  # 增量阈值(秒)
}
```

### 爬虫配置
```python
DEFAULT_CRAWLER_CONFIG = {
    'days': 7,                      # 爬取天数
    'max_articles_per_source': 20,  # 每源最大文章数
    'request_delay': 2,             # 请求延迟(秒)
    'timeout': 30,                  # 超时(秒)
    'retry_times': 3,               # 重试次数
}
```

## 🐛 常见问题

### Q: 找不到爬虫？
```python
# 检查爬虫是否注册
from crawler import get_global_registry
registry = get_global_registry()
registry.list_crawlers()
```

### Q: 爬虫运行失败？
```bash
# 查看详细日志
python main.py --crawler xxx --days 1
```

### Q: 如何禁用某个爬虫？
```python
# 在 constants.py 中设置
{
    'key': 'xxx',
    'enabled': False,  # 禁用
    # ...
}
```

### Q: 如何调整并发数？
```bash
python main.py --concurrent --max-concurrent 5
```

## 📚 更多文档

- **完整文档**: `crawler/README.md`
- **迁移指南**: `MIGRATION_GUIDE.md`
- **重构总结**: `REFACTORING_SUMMARY.md`

## 💡 最佳实践

1. ✅ 使用异步上下文管理器
2. ✅ 从配置文件读取参数
3. ✅ 使用注册中心动态加载
4. ✅ 添加完整的类型提示
5. ✅ 编写清晰的docstring
6. ✅ 测试单个爬虫后再批量运行

## 🎉 快速命令

```bash
# 开发测试
python main.py --crawler qbitai --days 1 --skip-report

# 生产运行
python main.py --concurrent --max-concurrent 3

# 只生成报告
python main.py --skip-crawl

# 只爬取数据
python main.py --skip-report

# 查看帮助
python main.py --help
```

---

**提示**: 这是快速参考，详细信息请查看完整文档！

