"""书籍实体类"""
from dataclasses import dataclass, field
from datetime import datetime

import gi
from gi.repository import GObject


@dataclass
class Book:
    """_summary_
    """
    path: str
    name: str
    chap_n: int
    chap_txt_pos: int
    # 读到哪里了
    txt_pos: int
    # 总字数
    txt_all: int
    encoding: str
    md5: str
    update_date: int = field(
        default_factory=lambda: int(datetime.now().timestamp()))
# -*- coding: utf-8 -*-


gi.require_version("GObject", "2.0")

class BookObject(GObject.GObject):
    """供 Gtk/Gio 模型使用的 GObject 封装"""
    path = GObject.Property(type=str)
    name = GObject.Property(type=str)
    chap_n = GObject.Property(type=int)
    chap_txt_pos = GObject.Property(type=int)
    txt_pos = GObject.Property(type=int)
    txt_all = GObject.Property(type=int)
    encoding = GObject.Property(type=str)
    md5 = GObject.Property(type=str)
    update_date = GObject.Property(type=int)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def from_dataclass(cls, b: Book) -> "BookObject":
        return cls(
            path=b.path,
            name=b.name,
            chap_n=b.chap_n,
            chap_txt_pos=b.chap_txt_pos,
            txt_pos=b.txt_pos,
            txt_all=b.txt_all,
            encoding=b.encoding,
            md5=b.md5,
            update_date=b.update_date,
        )

    def to_dataclass(self) -> Book:
        return Book(
            path=self.path,
            name=self.name,
            chap_n=self.chap_n,
            chap_txt_pos=self.chap_txt_pos,
            txt_pos=self.txt_pos,
            txt_all=self.txt_all,
            encoding=self.encoding,
            md5=self.md5,
            update_date=self.update_date,
        )
