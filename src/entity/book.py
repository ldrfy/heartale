"""书籍实体类"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from gettext import gettext as _

from gi.repository import GLib, GObject  # type: ignore

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
    # 章节名称
    chap_name: str
    # 总章节数
    chap_all: int
    # 章节内读到哪里了
    chap_txt_pos: int
    # 读了多少字了
    txt_pos: int
    # 总字数
    txt_all: int
    encoding: str
    md5: str
    # 类型，比如 0 txt, 1 legado, 2 epub, 3 mobi, 4 pdf, 5 djvu
    sort: float = 0.0
    fmt: int = BOOK_FMT_TXT
    create_date: int = field(
        default_factory=lambda: int(datetime.now().timestamp()))
    update_date: int = field(
        default_factory=lambda: int(datetime.now().timestamp()))
    id: Optional[int] = None

    def get_jd_str(self) -> str:
        """Return a formatted progress string."""
        pct = 0
        if self.txt_all > 0:
            pct = self.txt_pos * 100 / self.txt_all
        chap_str = "{chapter} ({current}/{total})".format(
            chapter=self.chap_name,
            current=self.chap_n,
            total=self.chap_all,
        )
        return _("{chapter} · Progress {percent:.2f}% ({position}/{total})").format(
            chapter=chap_str,
            percent=pct,
            position=self.txt_pos,
            total=self.txt_all,
        )

    def get_path(self) -> str:
        """Return the book path with the home directory shortened."""
        path_home = GLib.get_home_dir()
        return self.path.replace(path_home, '~')


class BookObject(GObject.GObject):
    """供 Gtk/Gio 模型使用的 GObject 封装"""
    path = GObject.Property(type=str)
    name = GObject.Property(type=str)
    author = GObject.Property(type=str)
    chap_n = GObject.Property(type=int)
    chap_name = GObject.Property(type=str)
    chap_all = GObject.Property(type=int)
    chap_txt_pos = GObject.Property(type=int)
    txt_pos = GObject.Property(type=int)
    txt_all = GObject.Property(type=int)
    encoding = GObject.Property(type=str)
    md5 = GObject.Property(type=str)
    sort = GObject.Property(type=float)
    fmt = GObject.Property(type=int)
    create_date = GObject.Property(type=int)
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
            chap_name=b.chap_name,
            chap_all=b.chap_all,
            chap_txt_pos=b.chap_txt_pos,
            txt_pos=b.txt_pos,
            txt_all=b.txt_all,
            encoding=b.encoding,
            md5=b.md5,
            sort=b.sort,
            fmt=b.fmt,
            create_date=b.create_date,
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
            chap_name=self.chap_name,
            chap_all=self.chap_all,
            chap_txt_pos=self.chap_txt_pos,
            txt_pos=self.txt_pos,
            txt_all=self.txt_all,
            encoding=self.encoding,
            md5=self.md5,
            sort=self.sort,
            fmt=self.fmt,
            create_date=self.create_date,
            update_date=self.update_date,
        )
