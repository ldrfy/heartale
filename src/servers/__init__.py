'''获取文本并自动跳转的配置'''

from datetime import datetime

from ..entity import LibraryDB
from ..entity.book import Book
from .tools import split_text


class BookData():
    """_summary_
    """

    def __init__(self):
        # 章节目录
        self.chap_names = []
        # 现在是第几个章节
        self.chap_n = 0
        # 这个章节的文本
        self.chap_txt = ""
        # 某章节的文本分割
        self.chap_txts = []
        # 某章节的文本分割所在位置
        self.chap_txt_p2s = [0]
        # 某章节的文本分割位置
        self.chap_txt_n = 0

    def set_data(self, chap_names, chap_n, chap_content, chap_txt_pos):
        """_summary_

        Args:
            chap_names (_type_): 目录
            chap_n (_type_): 第几个章节
            chap_content (_type_): 这个章节的文本
            chap_txt_pos (_type_): 读到这个章节的哪个位置了
        """
        self.set_chap_names(chap_names, chap_n)
        self.update_chap_txts(chap_content, chap_txt_pos)

    def set_chap_names(self, chap_names, chap_n):
        """初始化数据

        Args:
            chap_names (list): 章节名
            chap_n (int): 上次读到哪个章节了
        """
        # 防止保存数据太多
        self.chap_n = chap_n
        self.chap_names = chap_names

    def get_chap_name(self):
        """获取章节名字"""
        return self.chap_names[self.chap_n]

    def get_chap_txt(self):
        """获取章节文本"""
        return self.chap_txt

    def update_chap_txts(self, chap_content, chap_txt_pos=0):
        """分割章节的文本

        Args:
            chap_content (str): 章节文本
            chap_txt_pos (int): 已经读到这个章节的什么位置
        """
        self.chap_txts, self.chap_txt_p2s, self.chap_txt_n = \
            split_text(chap_content, chap_txt_pos)

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
        self._bd: BookData = BookData()

        self._chap_txt = ""

    def set_data(self, book: Book):
        """设置配置信息"""
        self.book = book

    def initialize(self):
        """异步初始化一些操作

        Returns:
            str: 比如书名等待阅读的文本
        """
        if not self.book:
            print("请先设置配置信息")
        return "initialize"

    def next(self):
        """接下来要阅读的文本，并保存本地阅读进度等信息
        """
        print("next")
        return "每次调用请自动刷新文本，并保存阅读信息"

    def get_chap_n(self):
        """获取当前章节编号

        Returns:
            int: 章节编号
        """
        return self._bd.chap_n

    def get_chap_txt(self, chap_n: int):
        """_summary_

        Args:
            chap_n (int): _description_

        Returns:
            _type_: _description_
        """
        print(f"获取章节文本 {chap_n}")
        return self._chap_txt

    def get_chap_names(self):
        """获取章节目录

        Args:
            book_data (dict): _description_

        Returns:
            list: 章节目录
        """
        return self._bd.chap_names

    def get_chap_name(self, chap_n: int):
        """获取章节目录

        Args:
            book_data (dict): _description_

        Returns:
            list: 章节目录
        """
        if chap_n < 0:
            return ""
        self._bd.chap_n = chap_n
        self.save_read_progress(chap_n, 0)
        return self.get_chap_names()[chap_n]

    def save_read_progress(self, chap_n: int, chap_txt_pos: int):
        """异步保存阅读进度

        Args:
            book_data (dict): 书籍信息

        Raises:
            ValueError: 当进度保存出错时抛出异常
        """

        self.book.chap_n = chap_n
        self.book.chap_txt_pos = chap_txt_pos
        self.book.update_date = int(datetime.now().timestamp())

        db = LibraryDB()
        db.update_book(self.book)
        db.close()
        print(f"保存进度 {self.book.chap_n}, {self.book.chap_txt_pos}")
