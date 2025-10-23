'''获取文本并自动跳转的配置'''

import time
from datetime import datetime

from ..entity import LibraryDB
from ..entity.book import Book
from ..entity.time_read import TIME_READ_WAY_READ, TimeRead
from ..utils.text import split_text


class BookData():
    """某章节的分割
    """

    def __init__(self):
        # # 章节目录
        # self.chap_names = []
        # # 现在是第几个章节
        # self.chap_n = 0
        # 这个章节的文本
        self.chap_txt = ""
        # 某章节的文本分割
        self.chap_txts = []
        # 某章节的文本分割所在位置
        self.chap_txt_p2s = [0]

        # 变量
        # 某章节的文本分割位置
        self.chap_txt_n = 0

    def update_chap_txts(self, chap_content, chap_txt_pos=0):
        """分割章节的文本

        Args:
            chap_content (str): 章节文本
            chap_txt_pos (int): 已经读到这个章节的什么位置
        """
        self.chap_txt = chap_content
        self.chap_txts, self.chap_txt_p2s, self.chap_txt_n = \
            split_text(chap_content, chap_txt_pos)
        print("----", len(self.chap_txts), self.chap_txt_n)

    def get_chap_txt_pos(self):
        """本章节的位置，需要保存

        Returns:
            _type_: _description_
        """
        return self.chap_txt_p2s[self.chap_txt_n]

    def is_chap_end(self):
        """这一章节是不是要结束了

        Returns:
            _type_: _description_
        """
        if self.chap_txt_n >= len(self.chap_txts):
            return True
        return False


class Server:
    """获取待阅读文本的基础类
    """

    def __init__(self, key: str):
        """_summary_

        Args:
            key (str): 用于配置中区分使用本地什么服务
        """

        self.key = key
        # 书名
        self.book: Book = None
        self.bd: BookData = BookData()

        self.chap_names = []
        self.read_time = time.time()

    def initialize(self, book: Book):
        """子类需要自定义异步初始化一些操作

        Returns:
            str: 比如书名等待阅读的文本
        """
        self.book = book

        # 子类设置目录
        # self.chap_names = self._get_chap_names()

        self.bd.update_chap_txts(
            self.get_chap_txt(self.book.chap_n),
            self.book.chap_txt_pos
        )

        return f"{self.book.name} {self.get_chap_name()}"

    def next(self):
        """子类需要自定义接下来要阅读的文本，并保存本地阅读进度等信息
        """
        print("next")
        return "每次调用请自动刷新文本，并保存阅读信息"

    def get_chap_txt(self, chap_n=-1):
        """子类需要自定义获取章节文本

        Args:
            chap_n (int): _description_

        Returns:
            _type_: _description_
        """
        if chap_n < 0:
            return self.bd.chap_txt
        # 子类 实现异步获取章节文本
        return ""

    # --------  基础方法   -------- #

    def get_chap_name(self, chap_n=-1):
        """获取章节目录

        Args:
            book_data (dict): _description_

        Returns:
            list: 章节目录
        """
        if chap_n < 0:
            chap_n = self.book.chap_n
        else:
            self.book.chap_n = chap_n
        return self.chap_names[chap_n]

    def get_chap_n(self):
        """获取当前章节编号

        Returns:
            int: 章节编号
        """
        return self.book.chap_n

    def get_chap_txt_pos(self):
        """获取当前章节文本位置

        Returns:
            int: 章节文本位置
        """
        return self.book.chap_txt_pos

    def set_chap_txt_n(self, chap_txt_n: int):
        """设置当前章节文本位置

        Args:
            chap_txt_n (int): 章节文本位置
        """
        self.bd.chap_txt_n = chap_txt_n
        self.book.chap_txt_pos = self.bd.chap_txt_p2s[chap_txt_n]

    def save_read_progress(self, chap_n: int, chap_txt_pos: int, way=TIME_READ_WAY_READ):
        """异步保存阅读进度

        Args:
            book_data (dict): 书籍信息

        Raises:
            ValueError: 当进度保存出错时抛出异常
        """

        w = len(self.bd.chap_txts[self.bd.chap_txt_n])
        sec = time.time()-self.read_time
        print(sec)

        self.book.chap_n = chap_n
        self.book.chap_name = self.get_chap_name(chap_n)
        self.book.chap_txt_pos = chap_txt_pos
        self.book.update_date = int(datetime.now().timestamp())
        self.book.txt_pos += w

        td = TimeRead(md5=self.book.md5, name=self.book.name,
                      chap_n=chap_n, way=way, words=w, seconds=sec)

        db = LibraryDB()
        db.update_book(self.book)
        db.save_time_read(td)
        db.close()

        self.read_time = time.time()
