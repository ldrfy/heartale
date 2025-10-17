"""阅读本地txt文件"""
import hashlib
import re
import shutil
from pathlib import Path

from charset_normalizer import from_path

from .. import PATH_CONFIG_BOOKS
from ..entity.book import Book
from ..utils.debug import get_logger
from . import Server


class TxtServer(Server):
    """阅读app相关的webapi"""

    def __init__(self):
        """初始化应用API

        Args:
            conf (dict): 配置 conf["legado"]
        """
        self.chap_p2s = []
        super().__init__("txt")

    def initialize(self, book: Book):
        """异步初始化"""
        self.book = book

        self.chap_names, self.chap_p2s = self._get_chap_names()
        self.bd.update_chap_txts(
            self.get_chap_txt(self.book.chap_n),
            self.book.chap_txt_pos
        )

        return f"{self.book.name} {self.get_chap_name()}"

    def next(self):
        """下一步

        Returns:
            str: 需要转音频的文本
        """

        if self.bd.is_chap_end():
            self.book.chap_n += 1

            self.bd.update_chap_txts(self.get_chap_txt(self.book.chap_n))
            return self.get_chap_name()

        txt = self.bd.chap_txts[self.bd.chap_txt_n]

        # 一些异常
        if len(self.bd.chap_txts) > 1:
            super().save_read_progress(self.get_chap_n(), self.bd.get_chap_txt_pos())
        self.bd.chap_txt_n += 1

        return txt

    def get_chap_txt(self, chap_n=-1):
        if chap_n < 0:
            return super().get_chap_txt(chap_n)

        with open(self.book.path, "r", encoding=self.book.encoding, errors="ignore") as f:
            if chap_n + 1 == len(self.chap_p2s):
                return f.read()[self.chap_p2s[chap_n]:]

            return f.read()[self.chap_p2s[chap_n]: self.chap_p2s[chap_n + 1]]

    def _get_chap_names(self):

        with open(self.book.path, "r", encoding=self.book.encoding, errors="ignore") as f:
            text = f.read()
        return parse_chap_names(text)


VOLUME_PATTERN = r'^第([一二三四五六七八九十\d]+)卷\s*(.*)'  # 匹配卷号
CHAPTER_PATTERN = r'^第([一二三四五六七八九十百千\d]+)章\s*(.*)'  # 匹配章号


VOLUME_PATTERN2 = r'第([一二三四五六七八九十\d]+)卷\s*(.*)'  # 匹配卷号
CHAPTER_PATTERN2 = r'第([一二三四五六七八九十百千\d]+)章\s*(.*)'  # 匹配章号


def parse_chap_names(file_content, volume_pattern=VOLUME_PATTERN, chapter_pattern=CHAPTER_PATTERN):
    """

    Args:
        file_content (str): _description_

    Returns:
        _type_: _description_
    """

    current_volume = None
    chap_names = []
    chap_ps = []

    words = 0
    for line in file_content.split("\n"):
        # 匹配卷号
        volume_match = re.search(volume_pattern, line)
        if volume_match:
            current_volume = volume_match.group()  # 获取当前卷
            words += len(line + "\n")
            continue  # 继续找章

        # 匹配章号
        chapter_match = re.search(chapter_pattern, line)
        if chapter_match:
            current_chapter = chapter_match.group()
            if current_volume:
                chap_names.append(f"{current_volume} {current_chapter}")
                current_volume = None  # 重置卷号
            else:
                chap_names.append(f"{current_chapter}")
            chap_ps.append(words)
        words += len(line + "\n")

    if len(chap_names) == 0:
        return parse_chap_names(file_content, VOLUME_PATTERN2, CHAPTER_PATTERN2)

    return chap_names, chap_ps


def cal_md5(path: Path, chunk_size: int = 8192) -> str:
    """计算md5

    Args:
        path (Path): _description_
        chunk_size (int, optional): _description_. Defaults to 8192.

    Returns:
        str: _description_
    """
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_encoding(path: Path, sample_size: int = 65536) -> str:
    """探测编码

    Args:
        path (Path): _description_
        sample_size (int, optional): _description_. Defaults to 65536.

    Raises:
        ValueError: _description_

    Returns:
        str: _description_
    """
    print(f"探测文件编码: {path}")
    encodings = ["gbk", "gb2312", "utf-8-sig", "utf-8"]
    raw = path.open("rb").read(sample_size)
    for enc in encodings:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError as e:
            get_logger().error("尝试用 %s 解码失败: %s", enc, e)

            continue
    result = from_path(path).best()
    return result.encoding
    # raise ValueError(f"Unable to recognize file encoding: {path}")


def path2book(src: str, cfg_dir: Path = PATH_CONFIG_BOOKS) -> Book:
    """根据路径初始化

    Args:
        src (str): _description_
        cfg_dir (Path | None, optional): _description_. Defaults to None.

    Returns:
        Book: _description_
    """
    src_path = Path(src)
    if not src_path.is_file():
        raise FileNotFoundError(f"File not found: {src}")
    if src_path.suffix.lower() not in [".txt"]:
        raise ValueError(f"Unsupported file type: {src_path.suffix}")
    enc = detect_encoding(src_path)

    chap_all = 0
    with open(src, "r", encoding=enc, errors="ignore") as file:
        f_txt = file.read()
    txt_all = len(f_txt)
    chap_names, _chap_ps = parse_chap_names(f_txt)
    chap_all = len(chap_names)

    dest = cfg_dir / src_path.name
    shutil.copy(src_path, dest)
    md5 = cal_md5(dest)
    return Book(str(dest), dest.stem, "", 0, chap_all, 0, 0, txt_all, enc, md5)
