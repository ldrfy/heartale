"""阅读本地txt文件"""
import hashlib
import re
import shutil
from pathlib import Path

from ..entity.book import Book
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

    def initialize(self):
        """异步初始化"""

        print(f"文件位置：{self.book.path}")

        print(f"上次读取的位置：{self.book.chap_n}, {self.book.chap_txt_pos}")

        names, self.chap_p2s = self._get_chap_names()
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
            str: 需要转音频的文本
        """
        print(f"当前位置：{self._bd.chap_txt_n}/{len(self._bd.chap_txts)}")

        if self._bd.is_chap_end():
            self._bd.chap_n += 1

            self._bd.update_chap_txts(self._chap_txt)
            return self._bd.get_chap_name()

        txt = self._bd.chap_txts[self._bd.chap_txt_n]

        # 一些异常
        if len(self._bd.chap_txts) > 1:
            super().save_read_progress(self._bd.chap_n, self._bd.get_chap_txt_pos())
        self._bd.chap_txt_n += 1

        return txt

    def get_chap_txt(self, chap_n: int):
        with open(self.book.path, "r", encoding=self.book.encoding) as f:
            if chap_n + 1 == len(self.chap_p2s):
                return f.read()[self.chap_p2s[chap_n]:]

            return f.read()[self.chap_p2s[chap_n]: self.chap_p2s[chap_n + 1]]

    def _get_chap_names(self):

        with open(self.book.path, "r", encoding=self.book.encoding) as f:
            text = f.read()
        return parse_chap_names(text)


def parse_chap_names(file_content):
    """

    Args:
        file_content (str): _description_

    Returns:
        _type_: _description_
    """

    # 匹配 "第xx卷" 和 "第xx章"
    volume_pattern = r'^第([一二三四五六七八九十\d]+)卷\s*(.*)'  # 匹配卷号
    chapter_pattern = r'^第([一二三四五六七八九十百千\d]+)章\s*(.*)'  # 匹配章号

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
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "big5", "latin1"]
    raw = path.open("rb").read(sample_size)
    for enc in encodings:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to recognize file encoding: {path}")


def path2book(src: str, cfg_dir: Path | None = None) -> Book:
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

    txt_all = len(src_path.read_text(encoding=enc))

    if cfg_dir is None:
        cfg_dir = Path.home() / ".config" / "heartale" / "books"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    dest = cfg_dir / src_path.name
    shutil.copy(src_path, dest)
    md5 = cal_md5(dest)
    return Book(str(dest), dest.stem, 0, 0, 0, txt_all, enc, md5)
