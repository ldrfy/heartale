"""阅读app 相关的webapi"""
import asyncio
import datetime
import json
import time
from urllib.parse import quote

import requests

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
        super().__init__("legado")

    def initialize(self):

        # self.book_data = get_book_shelf(0, self.book.path)
        self.book_data = get_book_shelf(0, self.book.path)
        self.book.name = self.book_data["name"]

        self.book.chap_n = self.book_data[CHAP_INDEX]
        self.book.chap_txt_pos = self.book_data[CHAP_POS]
        self.save_read_progress(self.book.chap_n, self.book.chap_txt_pos)

        names = self._get_chap_names()
        self._bd.set_data(
            names,
            self.book.chap_n,
            self.get_chap_txt(self.book.chap_n),
            self.book.chap_txt_pos
        )

        return self.book.name + " " + self._bd.get_chap_name()

    def next(self):
        """下一步

        Returns:
            _type_: _description_
        """
        if self._bd.is_chap_end():
            self._bd.chap_n += 1
            s = self._bd.get_chap_name()

            self.book_data[CHAP_POS] = 0
            self.book_data[CHAP_INDEX] = self._bd.chap_n
            self.book_data[CHAP_TITLE] = s

            self._bd.update_chap_txts(self.get_chap_txt(self.book.chap_n))

            return s

        txt = self._bd.chap_txts[self._bd.chap_txt_n]

        self._save_book_progress(self.book_data)
        self._bd.chap_txt_n += 1

        return txt

    def get_chap_txt(self, chap_n):
        """异步获取书某一章节的文本

        Args:
            book_data (dict): 书籍信息

        Returns:
            str: 某一章节的文字
        """
        url = f"{self.book.path}/getBookContent"
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
        url = f"{self.book.path}/getChapterList?{bu(self.book_data)}"
        resp = requests.get(url, timeout=10)
        return [d["title"] for d in resp.json()["data"]]

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
            CHAP_INDEX: self._bd.chap_n,
            CHAP_POS: self._bd.get_chap_txt_pos(),
            "durChapterTime": dct,
            CHAP_TITLE: self._bd.get_chap_name(),
        }

        json_data = json.dumps(data)
        headers = {'Content-Type': 'application/json'}

        resp = requests.post(f"{self.book.path}/saveBookProgress",
                             data=json_data,
                             headers=headers,
                             timeout=10)
        resp_json = resp.json()

        if not resp_json["isSuccess"]:
            raise ValueError(f'进度保存错误！\n{resp_json["errorMsg"]}')
        super().save_read_progress(self._bd.chap_n, self._bd.get_chap_txt_pos())


async def get_book_shelf_async(book_n: int, url):
    """异步获取书架信息

    Args:
        book_n (int): 第几本书

    Returns:
        dict: 书籍信息
    """
    url = f"{url}/getBookshelf"
    resp = requests.get(url, timeout=10)
    return resp.json()["data"][book_n]


def get_book_shelf(book_n: int, base_url: str) -> dict:
    """_summary_

    Args:
        book_n (int): _description_
        base_url (str): _description_

    Returns:
        dict: _description_
    """
    return asyncio.run(get_book_shelf_async(book_n, base_url))
