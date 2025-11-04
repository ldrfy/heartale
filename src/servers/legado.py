"""阅读app 相关的webapi"""
import datetime
import hashlib
import json
import time
from gettext import gettext as _
from urllib.parse import parse_qs, quote, urlparse, urlsplit, urlunsplit

import requests

from ..entity import LibraryDB
from ..entity.book import BOOK_FMT_LEGADO, Book
from ..entity.time_read import TIME_READ_WAY_READ
from . import Server

# 常量定义
CHAP_POS = "durChapterPos"
CHAP_INDEX = "durChapterIndex"
CHAP_TITLE = "durChapterTitle"
CHAP_TXT_N = "durChapterTxtN"


def bu(book_data: dict):
    """_summary_

    Args:
        book_data (dict): _description_

    Returns:
        str: _description_
    """
    return f'url={data2url(book_data["bookUrl"])}'


def data2url(url):
    """将书籍信息URL编码

    Args:
        url (str): url

    Returns:
        str: 编码以后的图书信息url
    """
    return quote(url)


class LegadoServer(Server):
    """阅读app相关的webapi"""

    def __init__(self):
        """初始化应用API

        Args:
            conf (dict): 配置 conf["legado"]
        """
        # 书籍信息
        self.book_data = ""
        # 一般是内网地址: http://192.168.x.x:xxxx
        self.url_base = ""
        # 刚开始读取进度,但是不能保存云端
        self.init = True
        super().__init__("legado")

    def initialize(self, book: Book):
        self.book = book

        #  同步手机端阅读进度
        # self.book.path: http://192.168.x.x:xxxx
        self.url_base = self.book.path

        bs = get_book_shelf(self.url_base)
        for b in bs:
            if b["name"] == self.book.name and b["author"] == self.book.author:
                self.book_data = b
                break
        if not self.book_data:
            raise ValueError(_("Failed to fetch Legado book information."))

        self.book.name = self.book_data["name"]
        self.book.author = self.book_data["author"]
        self.book.chap_all = self.book_data["totalChapterNum"]
        self.book.chap_n = self.book_data[CHAP_INDEX]
        self.book.chap_txt_pos = self.book_data[CHAP_POS]

        self.chap_names = self._get_chap_names()

        self.bd.update_chap_txts(
            self.get_chap_txt(self.book.chap_n),
            self.book.chap_txt_pos
        )

        self.init = True
        self.save_read_progress(
            self.book.chap_n,
            self.book.chap_txt_pos
        )
        self.init = False

        return f"{self.book.name} {self.get_chap_name()}"

    def next(self):
        """下一步

        Returns:
            _type_: _description_
        """
        if self.bd.is_chap_end():
            self.book.chap_n += 1
            s = self.get_chap_name()

            self.book_data[CHAP_POS] = 0
            self.book_data[CHAP_INDEX] = self.book.chap_n
            self.book_data[CHAP_TITLE] = s

            self.bd.update_chap_txts(self.get_chap_txt(self.book.chap_n))

            return s

        txt = self.bd.chap_txts[self.bd.chap_txt_n]

        self._save_book_progress(self.book_data)
        self.bd.chap_txt_n += 1

        return txt

    def get_chap_txt(self, chap_n=-1):
        if chap_n < 0:
            return super().get_chap_txt(chap_n)

        url = f"{self.url_base}/getBookContent"
        params = f"{bu(self.book_data)}&index={chap_n}"

        resp = requests.get(f"{url}?{params}", timeout=10)
        return resp.json()["data"]

    def _get_chap_names(self):
        """异步获取书章节目录

        Args:
            book_data (dict): 书籍信息

        Returns:
            list: 章节目录，包含title等
        """
        url = f"{self.url_base}/getChapterList?{bu(self.book_data)}"
        resp = requests.get(url, timeout=10)
        return [d["title"] for d in resp.json()["data"]]

    def save_read_progress(self, chap_n: int, chap_txt_pos: int, way=TIME_READ_WAY_READ):
        """_summary_

        Args:
            chap_n (int): _description_
            chap_txt_pos (int): _description_
        """
        if not self.init:
            # 刚开始读取进度,但是不能保存云端
            self._save_book_progress(self.book_data)
        super().save_read_progress(chap_n, chap_txt_pos, way)

    def _save_book_progress(self, book_data: dict):
        """异步保存阅读进度

        Args:
            book_data (dict): 书籍信息

        Raises:
            ValueError: 当进度保存出错时抛出异常
        """
        # 获取当前时间戳（毫秒）
        dct = int(time.mktime(datetime.datetime.now().timetuple()) * 1000)

        # 构建请求数据
        data = {
            "name": self.book.name,
            "author": book_data["author"],
            CHAP_INDEX: self.get_chap_n(),
            CHAP_POS: self.get_chap_txt_pos(),
            "durChapterTime": dct,
            CHAP_TITLE: self.get_chap_name(),
        }

        json_data = json.dumps(data)
        headers = {'Content-Type': 'application/json'}

        resp = requests.post(f"{self.url_base}/saveBookProgress",
                             data=json_data, headers=headers, timeout=10)
        resp_json = resp.json()

        if not resp_json["isSuccess"]:
            raise ValueError(_("Failed to save reading progress!\n{error}").format(error=resp_json["errorMsg"]))


def get_book_shelf(url):
    """异步获取书架信息

    Args:
        book_n (int): 第几本书

    Returns:
        dict: 书籍信息
    """
    resp = requests.get(f"{url}/getBookshelf", timeout=10)
    if resp.status_code != 200:
        raise ValueError(_("大概率输入的网址错误，当前网址为：{}").format(url))
    return resp.json()["data"]


def get_txt_all(b):
    """_summary_

    Args:
        word_count (_type_): _description_

    Returns:
        _type_: _description_
    """
    if "wordCount" not in b:
        return 0
    word_count = b["wordCount"]
    if not word_count:
        return 0
    if "K" in word_count:
        return int(word_count.replace("K", "")) * 1000
    return int(word_count)


def sync_legado_books(book_ns=5, url_base="http://10.8.0.6:1122") -> dict:
    """导入Legado书籍信息，网络请求

    Args:
        book_n (int): 第几本书
        base_url (str): Legado基础URL

    Returns:
        dict: 书籍信息
    """
    sync = True
    s_error = ""
    try:
        lbs = get_book_shelf(url_base)
    except Exception as e:  # pylint: disable=broad-except
        sync = False
        s_error += _("Failed to fetch Legado book: {error}\n").format(error=e)
        print(e)
        return sync, s_error

    db = LibraryDB()
    book_ns = min(book_ns, len(lbs))
    for i, b in enumerate(lbs[:book_ns]):
        s_error += f"\n----- {i} -----\n"
        try:
            name = b["name"]
            author = b["author"]
            s_error += _("Synced Legado book: {name} Author: {author}\n").format(name=name, author=author)

            md5 = hashlib.md5(f"legado-{name}-{author}"
                              .encode("utf-8")).hexdigest()
            book = Book(url_base, name, author, b["durChapterIndex"],
                        b["durChapterTitle"], b["totalChapterNum"],
                        b["durChapterPos"], 0,
                        get_txt_all(b), "utf-8", md5)
            book.fmt = BOOK_FMT_LEGADO
            db.save_book(book)

        except Exception as e:  # pylint: disable=broad-except
            sync = False
            s_error += _("Parsing error: {error}\n").format(error=e)

    db.close()
    return sync, s_error
