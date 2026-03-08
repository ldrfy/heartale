"""加载章节正文并维护阅读进度的公共工具。"""

import threading
import time
from datetime import datetime

from gettext import gettext as _

from ..entity import LibraryDB
from ..entity.book import Book
from ..entity.time_read import TIME_READ_WAY_READ, TimeRead
from ..utils.text import split_text


class BookData:
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

    def get_chap_txt_pos(self):
        """本章节的位置，需要保存

        Returns:
            int: 当前段落在章节中的字符位置
        """
        return self.chap_txt_p2s[self.chap_txt_n]

    def is_chap_end(self):
        """这一章节是不是要结束了

        Returns:
            bool: 当前章节是否已经读完
        """
        if self.chap_txt_n >= len(self.chap_txts):
            return True
        return False


class Server:
    """获取待阅读文本的基础类
    """

    def __init__(self, key: str):
        """初始化阅读服务基类

        Args:
            key (str): 用于配置中区分使用本地什么服务
        """

        self.key = key
        # 书名
        self.book: Book = None
        self.bd: BookData = BookData()

        self.chap_names = []
        self.read_time = time.time()
        self._chap_txt_cache = {}
        self._chap_txt_cache_lock = threading.Lock()

    def initialize(self, book: Book):
        """子类需要自定义异步初始化一些操作

        Returns:
            str: 比如书名等待阅读的文本
        """
        self.book = book

        # 子类设置目录
        # self.chap_names = self._get_chap_names()

        self.bd.update_chap_txts(
            self.load_chap_txt(self.book.chap_n),
            self.book.chap_txt_pos
        )

        return f"{self.book.name} {self.get_chap_name()}"

    def next(self):
        """子类需要自定义接下来要阅读的文本，并保存本地阅读进度等信息
        """
        return _("Each call should refresh the text and save reading information.")

    def get_chap_txt(self, chap_n=-1):
        """子类需要自定义获取章节文本

        Args:
            chap_n (int, optional): 章节索引. Defaults to -1.

        Returns:
            str: 章节正文
        """
        if chap_n < 0:
            return self.bd.chap_txt
        # 子类 实现异步获取章节文本
        return ""

    def load_chap_txt(self, chap_n=-1):
        """加载章节正文，优先复用内存缓存

        Args:
            chap_n (int, optional): 章节索引. Defaults to -1.

        Returns:
            str: 章节正文
        """
        if chap_n < 0:
            return self.get_chap_txt(chap_n)

        with self._chap_txt_cache_lock:
            cached = self._chap_txt_cache.get(chap_n)
        if cached is not None:
            return cached

        chap_txt = self.get_chap_txt(chap_n)
        self._store_chap_txt_cache(chap_n, chap_txt)
        return chap_txt

    def prefetch_chap_txt(self, chap_n: int):
        """预取指定章节正文到缓存

        Args:
            chap_n (int): 章节索引

        Returns:
            str | None: 预取到的章节正文
        """
        if chap_n < 0 or chap_n >= len(self.chap_names):
            return None
        return self.load_chap_txt(chap_n)

    def prefetch_next_chap_txt(self, chap_n=-1):
        """预取下一章节正文到缓存

        Args:
            chap_n (int, optional): 当前章节索引. Defaults to -1.

        Returns:
            str | None: 预取到的章节正文
        """
        if chap_n < 0:
            chap_n = self.book.chap_n
        return self.prefetch_chap_txt(chap_n + 1)

    def evict_chap_txt_cache(self, keep=None):
        """移除不再需要的章节缓存

        Args:
            keep (set[int] | None, optional): 需要保留的章节索引集合. Defaults to None.
        """
        keep_set = {i for i in (keep or set()) if isinstance(i, int) and i >= 0}
        with self._chap_txt_cache_lock:
            self._prune_chap_txt_cache_locked(keep_set)

    def _store_chap_txt_cache(self, chap_n: int, chap_txt: str):
        """写入章节缓存，并按窗口策略裁剪缓存

        Args:
            chap_n (int): 章节索引
            chap_txt (str): 章节正文
        """
        keep = {chap_n}
        if chap_n + 1 < len(self.chap_names):
            keep.add(chap_n + 1)
        with self._chap_txt_cache_lock:
            self._chap_txt_cache[chap_n] = chap_txt
            self._prune_chap_txt_cache_locked(keep)

    def _prune_chap_txt_cache_locked(self, keep):
        """在已加锁状态下裁剪章节缓存

        Args:
            keep (set[int]): 需要保留的章节索引集合
        """
        for chap_n in list(self._chap_txt_cache.keys()):
            if chap_n not in keep:
                self._chap_txt_cache.pop(chap_n, None)

    # --------  基础方法   -------- #

    def get_chap_name(self, chap_n=-1):
        """获取章节目录

        Args:
            chap_n (int, optional): 章节索引. Defaults to -1.

        Returns:
            str: 章节标题
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
        if not self.bd.chap_txt_p2s:
            self.bd.chap_txt_n = 0
            self.book.chap_txt_pos = 0
            return

        safe_idx = max(0, min(int(chap_txt_n), len(self.bd.chap_txt_p2s) - 1))
        self.bd.chap_txt_n = safe_idx
        self.book.chap_txt_pos = self.bd.chap_txt_p2s[safe_idx]

    def save_read_progress(
        self,
        chap_n: int,
        chap_txt_pos: int,
        way=TIME_READ_WAY_READ,
        seconds_override: float | None = None,
    ):
        """异步保存阅读进度

        Args:
            book_data (dict): 书籍信息

        Raises:
            ValueError: 当进度保存出错时抛出异常
        """

        w = len(self.bd.chap_txts[self.bd.chap_txt_n])
        if seconds_override is None:
            sec = time.time() - self.read_time
        else:
            sec = max(0.0, float(seconds_override))

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
