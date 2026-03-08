"""CLI 与 GUI 共用的朗读流程辅助函数。"""

from ..servers import Server


def build_intro_texts(server: Server) -> list[str]:
    """构建当前章节朗读前的开场文本列表。

    Args:
        server (Server): 阅读服务实例

    Returns:
        list[str]: 开场文本列表
    """
    return [
        (server.book.name or "").strip(),
        (server.get_chap_name(server.get_chap_n()) or "").strip(),
    ]


def find_next_tts_idx(chap_txts: list[str], start: int) -> int | None:
    """查找下一段可朗读文本的索引。

    Args:
        chap_txts (list[str]): 当前章节段落列表
        start (int): 起始查找位置

    Returns:
        int | None: 下一段可朗读文本的索引
    """
    for idx in range(start, len(chap_txts)):
        if (chap_txts[idx] or "").strip():
            return idx
    return None


def get_first_tts_text(chap_txts: list[str], start_idx: int = 0) -> str | None:
    """获取从指定位置开始的第一段可朗读文本。

    Args:
        chap_txts (list[str]): 当前章节段落列表
        start_idx (int, optional): 起始位置. Defaults to 0.

    Returns:
        str | None: 第一段可朗读文本
    """
    next_idx = find_next_tts_idx(chap_txts, start_idx)
    if next_idx is None:
        return None
    return (chap_txts[next_idx] or "").strip()


def get_start_read_text(server: Server, chap_txts: list[str], start_idx: int) -> str | None:
    """获取本次朗读开始前应先准备的第一条文本。

    Args:
        server (Server): 阅读服务实例
        chap_txts (list[str]): 当前章节段落列表
        start_idx (int): 正文起始索引

    Returns:
        str | None: 第一条需要朗读的文本
    """
    for intro_text in build_intro_texts(server):
        intro_text = (intro_text or "").strip()
        if intro_text:
            return intro_text
    return get_first_tts_text(chap_txts, start_idx)


def get_next_intro_text(
    intro_texts: list[str],
    intro_idx: int,
    start_idx: int,
    chap_txts: list[str],
) -> str | None:
    """获取开场播报之后下一条需要预取的文本。

    Args:
        intro_texts (list[str]): 开场播报文本列表
        intro_idx (int): 当前播报文本索引
        start_idx (int): 正文起始索引
        chap_txts (list[str]): 当前章节段落列表

    Returns:
        str | None: 下一条需要预取的文本
    """
    for next_intro in intro_texts[intro_idx + 1:]:
        next_intro = (next_intro or "").strip()
        if next_intro:
            return next_intro
    return get_first_tts_text(chap_txts, start_idx)


def get_next_tts_text(server: Server, idx: int, chap_txts: list[str]) -> str | None:
    """获取当前段落之后下一条要预取的文本。

    Args:
        server (Server): 阅读服务实例
        idx (int): 当前段落索引
        chap_txts (list[str]): 当前章节段落列表

    Returns:
        str | None: 下一条要预取的文本
    """
    next_idx = find_next_tts_idx(chap_txts, idx + 1)
    if next_idx is not None:
        return (chap_txts[next_idx] or "").strip()

    next_chap_n = server.get_chap_n() + 1
    if next_chap_n >= len(server.chap_names):
        return None

    next_book_title = (server.book.name or "").strip()
    if next_book_title:
        return next_book_title
    return (server.get_chap_name(next_chap_n) or "").strip()


def ensure_next_chapter_prefetched_for_text(server: Server, text: str) -> None:
    """在跨章提示音预取时提前加载下一章正文。

    Args:
        server (Server): 阅读服务实例
        text (str): 当前待预取文本
    """
    if text != (server.book.name or "").strip():
        return
    next_chap_n = server.get_chap_n() + 1
    if next_chap_n >= len(server.chap_names):
        return
    server.prefetch_chap_txt(next_chap_n)
