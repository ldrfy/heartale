"""获取阅读时间的基础类"""
from dataclasses import dataclass, field
from datetime import datetime
from gettext import gettext as _


@dataclass
class TimeRead:
    """_summary_
    """
    md5: str
    type: int = 0               # 类型，0-阅读，1-听书
    words: int = 0               # 阅读的字数（或页数）
    seconds: int = 0             # 本次阅读耗时，秒
    dt: datetime = field(default_factory=datetime.now)  # 完整时间
