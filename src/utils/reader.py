"""GUI 与 CLI 共用的阅读服务辅助函数。"""

import threading

from requests import RequestException

from ..entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from ..servers.legado import LegadoServer
from ..servers.txt import TxtServer
from .debug import get_logger


def create_reader_server(book: Book) -> LegadoServer | TxtServer:
    """根据书籍对象创建并初始化阅读服务。

    Args:
        book (Book): 书籍对象

    Returns:
        LegadoServer | TxtServer: 初始化后的阅读服务实例
    """
    if book.fmt == BOOK_FMT_LEGADO:
        server = LegadoServer()
    elif book.fmt == BOOK_FMT_TXT:
        server = TxtServer()
    else:
        raise ValueError(f"Unsupported book format: {book.fmt}")

    server.initialize(book)
    return server


def load_chapter_into_server(
    server: LegadoServer | TxtServer,
    chap_n: int,
    chap_txt_pos: int | None = None,
    save_progress: bool = False,
) -> str:
    """将指定章节正文加载到阅读服务中。

    Args:
        server (LegadoServer | TxtServer): 阅读服务实例
        chap_n (int): 章节索引
        chap_txt_pos (int | None, optional): 章节内段落位置. Defaults to None.
        save_progress (bool, optional): 是否先保存章节切换进度. Defaults to False.

    Returns:
        str: 章节标题
    """
    if save_progress:
        server.save_read_progress(chap_n, 0)

    if chap_txt_pos is None:
        chap_txt_pos = server.book.chap_txt_pos

    chap_name = server.get_chap_name(chap_n)
    server.bd.update_chap_txts(server.load_chap_txt(chap_n), chap_txt_pos)
    return chap_name


def advance_to_next_chapter(server: LegadoServer | TxtServer) -> bool:
    """切换到下一章并同步加载正文。

    Args:
        server (LegadoServer | TxtServer): 阅读服务实例

    Returns:
        bool: 是否成功切换到下一章
    """
    next_chap_n = server.book.chap_n + 1
    if next_chap_n >= len(server.chap_names):
        return False

    server.book.chap_n = next_chap_n
    server.book.chap_txt_pos = 0
    server.bd.chap_txt_n = 0
    load_chapter_into_server(server, next_chap_n, chap_txt_pos=0)
    return True


def prefetch_next_chapter_async(server: LegadoServer | TxtServer) -> None:
    """异步预取当前章节的下一章正文。

    Args:
        server (LegadoServer | TxtServer): 阅读服务实例
    """
    def worker() -> None:
        try:
            server.prefetch_next_chap_txt(server.get_chap_n())
        except (OSError, RuntimeError, ValueError, RequestException) as exc:
            get_logger().warning("Prefetch next chapter failed: %s", exc)

    threading.Thread(
        target=worker,
        daemon=True,
    ).start()
