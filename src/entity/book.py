"""书籍实体类"""
from dataclasses import dataclass, field
from datetime import datetime

from gi.repository import GObject  # type: ignore

BOOK_FMT_TXT = 0
BOOK_FMT_LEGADO = 1
BOOK_FMT_EPUB = 2
BOOK_FMT_MOBI = 3
BOOK_FMT_PDF = 4
BOOK_FMT_DJVU = 5

@dataclass
class Book:
    """_summary_
    """
    path: str
    name: str
    author: str
    # 读到第几章节
    chap_n: int
    # 总章节数
    chap_all: int
    # 章节内读到哪里了
    chap_txt_pos: int
    # 读到哪里了
    txt_pos: int
    # 总字数
    txt_all: int
    encoding: str
    md5: str
    # 类型，比如 0 txt, 1 legado, 2 epub, 3 mobi, 4 pdf, 5 djvu
    fmt: int = BOOK_FMT_TXT
    update_date: int = field(
        default_factory=lambda: int(datetime.now().timestamp()))


class BookObject(GObject.GObject):
    """供 Gtk/Gio 模型使用的 GObject 封装"""
    path = GObject.Property(type=str)
    name = GObject.Property(type=str)
    author = GObject.Property(type=str)
    chap_n = GObject.Property(type=int)
    chap_all = GObject.Property(type=int)
    chap_txt_pos = GObject.Property(type=int)
    txt_pos = GObject.Property(type=int)
    txt_all = GObject.Property(type=int)
    encoding = GObject.Property(type=str)
    md5 = GObject.Property(type=str)
    fmt = GObject.Property(type=int)
    update_date = GObject.Property(type=int)

    def __init__(self, **kwargs):
        """_summary_
        """
        super().__init__(**kwargs)

    @classmethod
    def from_dataclass(cls, b: Book) -> "BookObject":
        """_summary_

        Args:
            b (Book): _description_

        Returns:
            BookObject: _description_
        """
        return cls(
            path=b.path,
            name=b.name,
            author=b.author,
            chap_n=b.chap_n,
            chap_all=b.chap_all,
            chap_txt_pos=b.chap_txt_pos,
            txt_pos=b.txt_pos,
            txt_all=b.txt_all,
            encoding=b.encoding,
            md5=b.md5,
            fmt=b.fmt,
            update_date=b.update_date,
        )

    def to_dataclass(self) -> Book:
        """_summary_

        Returns:
            Book: _description_
        """
        return Book(
            path=self.path,
            name=self.name,
            author=self.author,
            chap_n=self.chap_n,
            chap_all=self.chap_all,
            chap_txt_pos=self.chap_txt_pos,
            txt_pos=self.txt_pos,
            txt_all=self.txt_all,
            encoding=self.encoding,
            md5=self.md5,
            fmt=self.fmt,
            update_date=self.update_date,
        )
