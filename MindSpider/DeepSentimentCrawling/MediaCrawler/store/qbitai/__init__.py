# -*- coding: utf-8 -*-
# @Author  : MindSpider
# @Time    : 2025/12/16
# @Desc    : 量子位数据存储模块

import json
from typing import Dict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database.models import QbitaiArticle, QbitaiArticleComment
from database.db_session import get_session
from tools import utils


async def store_article(article_item: Dict):
    """
    存储量子位文章
    Args:
        article_item: 文章数据字典

    Returns:
        None
    """
    try:
        article_id = article_item.get("article_id")
        
        # 处理tags和其他JSON字段
        if isinstance(article_item.get('tags'), list):
            article_item['tags'] = json.dumps(article_item['tags'], ensure_ascii=False)
        
        async with get_session() as session:
            # 检查是否已存在
            stmt = select(QbitaiArticle).where(QbitaiArticle.article_id == article_id)
            res = await session.execute(stmt)
            db_article = res.scalar_one_or_none()
            
            if db_article:
                # 更新已有记录
                db_article.last_modify_ts = utils.get_current_timestamp()
                for key, value in article_item.items():
                    if hasattr(db_article, key) and key not in ['id', 'add_ts']:
                        setattr(db_article, key, value)
                utils.logger.info(f"[store.qbitai.store_article] 更新文章: {article_id}")
            else:
                # 创建新记录
                article_item["add_ts"] = utils.get_current_timestamp()
                article_item["last_modify_ts"] = utils.get_current_timestamp()
                db_article = QbitaiArticle(**article_item)
                session.add(db_article)
                utils.logger.info(f"[store.qbitai.store_article] 保存新文章: {article_id}")
            
            await session.commit()
    except Exception as e:
        utils.logger.error(f"[store.qbitai.store_article] 存储文章失败: {e}")
        raise


async def store_comment(comment_item: Dict):
    """
    存储量子位评论
    Args:
        comment_item: 评论数据字典

    Returns:
        None
    """
    try:
        comment_id = comment_item.get("comment_id")
        
        async with get_session() as session:
            # 检查是否已存在
            stmt = select(QbitaiArticleComment).where(QbitaiArticleComment.comment_id == comment_id)
            res = await session.execute(stmt)
            db_comment = res.scalar_one_or_none()
            
            if db_comment:
                # 更新已有记录
                db_comment.last_modify_ts = utils.get_current_timestamp()
                for key, value in comment_item.items():
                    if hasattr(db_comment, key) and key not in ['id', 'add_ts']:
                        setattr(db_comment, key, value)
                utils.logger.info(f"[store.qbitai.store_comment] 更新评论: {comment_id}")
            else:
                # 创建新记录
                comment_item["add_ts"] = utils.get_current_timestamp()
                comment_item["last_modify_ts"] = utils.get_current_timestamp()
                db_comment = QbitaiArticleComment(**comment_item)
                session.add(db_comment)
                utils.logger.info(f"[store.qbitai.store_comment] 保存新评论: {comment_id}")
            
            await session.commit()
    except Exception as e:
        utils.logger.error(f"[store.qbitai.store_comment] 存储评论失败: {e}")
        raise


async def batch_store_articles(articles: list):
    """
    批量存储文章
    Args:
        articles: 文章列表

    Returns:
        None
    """
    for article in articles:
        try:
            await store_article(article)
        except Exception as e:
            utils.logger.warning(f"[store.qbitai.batch_store_articles] 处理文章失败: {e}")
            continue


async def batch_store_comments(comments: list):
    """
    批量存储评论
    Args:
        comments: 评论列表

    Returns:
        None
    """
    for comment in comments:
        try:
            await store_comment(comment)
        except Exception as e:
            utils.logger.warning(f"[store.qbitai.batch_store_comments] 处理评论失败: {e}")
            continue
