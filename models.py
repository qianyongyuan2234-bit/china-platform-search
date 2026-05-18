"""数据模型"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ContentType(Enum):
    TEXT = "文字"
    VIDEO = "视频"
    IMAGE = "图片"
    MIXED = "图文"


@dataclass
class SearchResult:
    title: str
    content: str = ""
    url: str = ""
    platform: str = ""
    author: str = ""
    content_type: str = ""
    time: str = ""
    image_url: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class SearchReport:
    keyword: str
    results: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
