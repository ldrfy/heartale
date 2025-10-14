"""书籍实体类"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Book:
    """_summary_
    """
    path: str
    name: str
    chap_n: int
    chap_txt_pos: int
    encoding: str
    md5: str
    update_date: int = field(
        default_factory=lambda: int(datetime.now().timestamp()))
