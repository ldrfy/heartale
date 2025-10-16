#!/usr/bin/env python3
# coding: utf-8
"""
library_db.py
Book 与 TimeRead 的 sqlite3 持久化实现。
"""

import hashlib
import re
import shutil
from pathlib import Path

from . import LibraryDB
from .book import Book
from .time_read import TimeRead


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


# -------------------------
# 示例用法
# -------------------------
if __name__ == "__main__":
    # 简单演示ca

    cal_md5("/home/yuh/.config/heartale/books/人道至尊-宅猪.txt")
    # db = LibraryDB("test_library.db")

    # # 示例：从本地文件导入并保存 Book
    # file_book = path2book(
    #     "/home/yuh/Downloads/firefox/万相之王.txt")  # 取消注释并修改路径使用
    # db.save_book(file_book)

    # # 按 md5 查询
    # q = db.get_book_by_md5("md5-example-123")
    # print("get_book_by_md5:", q)

    # # 模糊查名
    # res = db.search_books_by_name("示例")
    # print("search_books_by_name:", res)

    # # 保存 TimeRead 示例
    # tr0 = TimeRead(md5="md5-example-123", words=1200,
    #                seconds=900, dt=datetime.now())
    # db.save_time_read(tr0)

    # # 查询某天
    # today = datetime.now().date()
    # day_reads = db.get_time_reads_by_day(today)
    # print("day_reads:", day_reads)

    # # 查询某月
    # month_reads = db.get_time_reads_by_month(today.year, today.month)
    # print("month_reads:", len(month_reads))

    # # 查询某年
    # year_reads = db.get_time_reads_by_year(today.year)
    # print("year_reads:", len(year_reads))

    # db.close()
