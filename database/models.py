from sqlalchemy import Column, Integer, Text, String, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class QbitaiArticle(Base):
    __tablename__ = 'qbitai_article'
    id = Column(Integer, primary_key=True)
    article_id = Column(String(255), nullable=False, index=True, unique=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    content = Column(Text)
    article_url = Column(Text, nullable=False)
    author = Column(String(255))
    publish_time = Column(BigInteger, index=True)
    publish_date = Column(String(10), index=True)
    read_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    collect_count = Column(Integer, default=0)
    category = Column(String(100))
    tags = Column(Text)
    cover_image = Column(String(512))
    source_keyword = Column(String(255), default='')
    is_original = Column(Integer, default=1)
    reference_links = Column(Text)  # JSON格式存储文章中的参考链接
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)

class QbitaiArticleComment(Base):
    __tablename__ = 'qbitai_article_comment'
    id = Column(Integer, primary_key=True)
    comment_id = Column(String(255), nullable=False, index=True, unique=True)
    article_id = Column(String(255), nullable=False, index=True)
    user_name = Column(String(255))
    user_avatar = Column(String(512))
    content = Column(Text, nullable=False)
    publish_time = Column(BigInteger, index=True)
    publish_date = Column(String(10), index=True)
    like_count = Column(Integer, default=0)
    sub_comment_count = Column(Integer, default=0)
    parent_comment_id = Column(String(255))
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)

