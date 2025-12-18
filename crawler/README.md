# Crawler模块文档

## 📁 文件结构

```
crawler/
├── __init__.py              # 模块统一导出接口
├── constants.py             # 配置常量（新增）
├── base_scraper.py          # 爬虫基类（优化）
├── crawler_registry.py      # 爬虫注册中心（优化）
├── scheduler.py             # 统一调度器（重构）
├── proxy_pool.py            # 代理池管理
├── utils.py                 # 工具函数
│
├── anthropic_scraper.py     # Anthropic爬虫
├── google_ai_scraper.py     # Google AI爬虫
├── meta_microsoft_scraper.py # Meta/Microsoft爬虫
├── openai_scraper.py        # OpenAI爬虫
├── ai_companies_scraper.py  # NVIDIA等公司爬虫
├── qbitai_scraper.py        # 量子位爬虫
├── news_scraper.py          # 新闻媒体爬虫
└── ai_tools_scraper.py      # AI工具爬虫
```

## 🔄 重构改进

### 1. 新增文件

- **`__init__.py`**: 统一的模块导出接口，方便外部导入
- **`constants.py`**: 集中管理所有配置常量，包括爬虫配置、调度器设置等

### 2. 优化的文件

#### `crawler_registry.py`
- ✅ 移除硬编码的爬虫导入
- ✅ 支持动态加载爬虫类和runner函数
- ✅ 从`constants.py`读取配置
- ✅ 增强类型提示和文档

#### `base_scraper.py`
- ✅ 增强类型提示
- ✅ 优化代码结构和文档
- ✅ 支持异步上下文管理器（`async with`）
- ✅ 从`constants.py`导入默认配置
- ✅ 改进错误处理和重试机制
- ✅ 提取`_classify_reference_link`方法提高可维护性

#### `scheduler.py`
- ✅ 合并了`scheduler.py`和`advanced_scheduler.py`
- ✅ 使用`crawler_registry`动态加载爬虫
- ✅ 移除所有硬编码的爬虫导入和映射
- ✅ 支持增量更新和并发执行
- ✅ 配置从`constants.py`读取

### 3. 删除的文件

- ❌ `crawler_config.py` - 功能合并到`constants.py`
- ❌ `advanced_scheduler.py` - 功能合并到`scheduler.py`

## 🚀 使用示例

### 基本使用

```python
from crawler.scheduler import run_all_crawlers

# 运行所有爬虫
results = await run_all_crawlers(
    days=7,                  # 爬取最近7天的数据
    max_concurrent=3,        # 最大并发数
    use_incremental=True     # 启用增量更新
)
```

### 注册新爬虫

在`constants.py`中添加配置：

```python
CRAWLER_CONFIGS = [
    # ... 现有配置 ...
    {
        'key': 'new_crawler',
        'name': 'New Crawler',
        'module': 'crawler.new_scraper',
        'class': 'NewScraper',
        'runner': 'run_new_crawler',
        'type': 'company',  # company/news/tools
        'enabled': True,
        'priority': 1,
        'description': '新爬虫描述',
        'db_table': 'company_article',
    },
]
```

然后实现对应的爬虫类即可，无需修改其他代码！

### 使用爬虫注册中心

```python
from crawler import get_global_registry

# 获取注册中心
registry = get_global_registry()

# 列出所有爬虫
registry.list_crawlers()

# 获取特定爬虫
crawler_info = registry.get_crawler('qbitai')

# 动态加载爬虫类
CrawlerClass = registry.get_crawler_class('qbitai')
scraper = CrawlerClass()

# 动态加载runner函数
runner_func = registry.get_crawler_runner('qbitai')
await runner_func(days=7)
```

### 自定义爬虫

继承`BaseWebScraper`创建新爬虫：

```python
from crawler import BaseWebScraper

class CustomScraper(BaseWebScraper):
    def __init__(self):
        super().__init__(
            base_url="https://example.com",
            company_name="example",
            use_proxy=False,
        )
    
    async def get_article_list(self, page: int = 1) -> List[Dict]:
        # 实现文章列表获取逻辑
        pass
    
    async def get_article_detail(self, article_id: str, url: str) -> Optional[Dict]:
        # 实现文章详情获取逻辑
        pass

# 使用异步上下文管理器
async with CustomScraper() as scraper:
    articles = await scraper.get_article_list()
```

## ⚙️ 配置说明

### 爬虫配置 (`constants.py`)

```python
DEFAULT_CRAWLER_CONFIG = {
    'days': 7,                      # 爬取天数
    'max_articles_per_source': 20,  # 每个来源最大文章数
    'request_delay': 2,             # 请求延迟（秒）
    'timeout': 30,                  # 超时时间（秒）
    'retry_times': 3,               # 重试次数
}
```

### 调度器配置 (`constants.py`)

```python
SCHEDULER_CONFIG = {
    'max_concurrent': 3,            # 最大并发数
    'use_incremental': True,        # 是否使用增量更新
    'crawler_delay': 2,             # 爬虫之间的延迟（秒）
    'incremental_threshold': 3600,  # 增量更新阈值（秒）
}
```

## 🎯 核心优势

### 1. 配置驱动
- 所有爬虫配置集中在`constants.py`
- 添加新爬虫只需修改配置文件
- 无需修改核心调度逻辑

### 2. 动态加载
- 使用`importlib`动态导入爬虫模块
- 避免硬编码导入和if-else判断
- 降低模块间耦合

### 3. 统一接口
- 通过`__init__.py`提供清晰的导出接口
- 使用`crawler_registry`统一管理爬虫
- 标准化的爬虫基类和抽象方法

### 4. 高可维护性
- 清晰的文件职责划分
- 完善的类型提示和文档
- 易于扩展和测试

### 5. 增强功能
- 支持增量更新，避免重复爬取
- 支持并发执行，提高效率
- 支持代理池，应对反爬虫
- 详细的执行统计和日志

## 📊 执行流程

```
用户调用 run_all_crawlers()
    ↓
创建 CrawlerScheduler 实例
    ↓
从 registry 获取所有启用的爬虫
    ↓
按类型（company/news/tools）分组
    ↓
对每个爬虫：
    - 检查是否需要增量更新
    - 动态加载 runner 函数
    - 使用信号量控制并发
    - 执行爬虫并跟踪结果
    ↓
输出执行摘要
```

## 🔧 维护指南

### 添加新爬虫

1. 在`crawler/`目录下创建爬虫文件（如`new_scraper.py`）
2. 继承`BaseWebScraper`实现爬虫类
3. 实现`run_new_crawler(days)`函数
4. 在`constants.py`的`CRAWLER_CONFIGS`中添加配置
5. 完成！scheduler会自动识别和运行

### 修改配置

- 修改爬虫参数：编辑`constants.py`中的`CRAWLER_CONFIGS`
- 修改调度器行为：编辑`constants.py`中的`SCHEDULER_CONFIG`
- 修改默认HTTP头：编辑`constants.py`中的`DEFAULT_HEADERS`

### 调试

```python
# 查看所有注册的爬虫
from crawler import get_global_registry
registry = get_global_registry()
registry.list_crawlers()

# 测试单个爬虫
crawler = registry.get_crawler('qbitai')
print(crawler)

# 动态加载测试
runner = registry.get_crawler_runner('qbitai')
await runner(days=1)
```

## 📝 注意事项

1. 所有爬虫的runner函数必须接受`days`参数
2. 新爬虫必须在`constants.py`中配置才能被调度器识别
3. 爬虫类名和runner函数名必须与配置中的`class`和`runner`字段匹配
4. 使用增量更新时，确保数据库表结构正确

## 🎉 总结

通过这次重构，crawler模块实现了：

- ✅ 更清晰的代码结构
- ✅ 更低的维护成本
- ✅ 更高的扩展性
- ✅ 更好的可测试性
- ✅ 更强的类型安全

现在添加新爬虫只需3步：编写爬虫代码 → 添加配置 → 完成！

