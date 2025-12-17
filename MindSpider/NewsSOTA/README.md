# NewsSOTA - AI前沿报告生成器

此模块通过分析本地数据库中的量子位(QbitAI)新闻数据，利用 Google Gemini API 自动生成 AI 前沿动态速报。

## 依赖

- Google Gemini API Key
- 本地数据库中已有爬取好的量子位数据 (QbitAI)
- Python 依赖: `google-generativeai` (已添加至根目录 requirements.txt)

## 配置

1. 确保根目录的 `config.py` 或 `.env` 文件中配置了数据库连接信息。
2. 在 `config.py` 或 `.env` 中设置 `GEMINI_API_KEY`:

   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

## 使用方法

在项目根目录下运行:

```bash
python NewsSOTA/main.py
```

或者进入目录运行:

```bash
cd NewsSOTA
python main.py
```

程序将：
1. 连接数据库获取最近 3 天的量子位文章。
2. 调用 Gemini API 生成 Markdown 格式的报告。
3. 将报告保存为 `NewsSOTA/AI_Report_YYYY-MM-DD.md`。

## 注意事项

- 请确保数据库中 `qbitai_article` 表有近期数据。如果为空，请先运行 `DeepSentimentCrawling/run_qbitai_crawler.py` (或相应爬虫脚本) 获取数据。

