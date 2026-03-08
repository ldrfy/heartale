"""命令行朗读流程。"""

import argparse
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from gettext import gettext as _

from .entity import LibraryDB
from .entity.book import BOOK_FMT_LEGADO, BOOK_FMT_TXT, Book
from .entity.time_read import TIME_READ_WAY_LISTEN
from .servers.legado import LegadoServer
from .servers.txt import TxtServer
from .tts.cache import AudioPrefetchSlot
from .tts.cli import apply_tts_overrides
from .tts.read_flow import (build_intro_texts,
                            ensure_next_chapter_prefetched_for_text,
                            get_next_intro_text, get_next_tts_text,
                            get_start_read_text)
from .tts.server_android import TtsSA


@dataclass(slots=True)
class CliReadContext:
    """命令行朗读运行时上下文。"""

    server: LegadoServer | TxtServer
    tts: TtsSA
    prefetch_slot: AudioPrefetchSlot
    preview_chars: int


def run_read_book_cli(
    book_idx: int,
    preview_chars: int,
    cli_args: argparse.Namespace,
    print_bookshelf: Callable[[], None],
) -> int:
    """在命令行模式下朗读指定书籍

    Args:
        book_idx (int): 书籍索引，从 1 开始
        preview_chars (int): 每段预览显示的字符数
        cli_args (argparse.Namespace): 命令行参数对象
        print_bookshelf (Callable[[], None]): 输出书架列表的回调

    Returns:
        int: 命令执行返回码
    """
    code = _ensure_cli_audio_player()
    if code is not None:
        return code

    server = _build_reader_server(book_idx, print_bookshelf)
    if server is None:
        return 1

    tts = _build_cli_tts(cli_args)
    if tts is None:
        return 1

    print(_("Book[{index}]: {name}").format(index=book_idx, name=server.book.name))
    print(_("Chapter: {chapter}").format(chapter=server.get_chap_name(server.get_chap_n())))
    prefetch_slot = AudioPrefetchSlot(tts)
    context = CliReadContext(
        server=server,
        tts=tts,
        prefetch_slot=prefetch_slot,
        preview_chars=preview_chars,
    )
    _prefetch_next_chapter_cli(context.server)

    try:
        while True:
            code = _read_current_chapter_cli(context)
            if code is not None:
                return code

            if not _advance_to_next_chapter_cli(context.server):
                print(_("Finished all chapters"))
                return 0

            _prefetch_next_chapter_cli(context.server)
            print(_("Chapter: {chapter}").format(
                chapter=context.server.get_chap_name(context.server.get_chap_n())))
    finally:
        prefetch_slot.clear()


def _ensure_cli_audio_player() -> int | None:
    """检查命令行朗读所需的音频播放器是否可用。

    Returns:
        int | None: 出错时返回命令退出码，否则返回 None
    """
    if shutil.which("paplay"):
        return None
    print(_("paplay is not installed."))
    return 1


def _build_reader_server(book_idx: int, print_bookshelf: Callable[[], None]):
    """初始化命令行阅读服务。

    Args:
        book_idx (int): 书籍索引，从 1 开始
        print_bookshelf (Callable[[], None]): 输出书架列表的回调

    Returns:
        LegadoServer | TxtServer | None: 初始化后的阅读服务实例
    """
    book = _get_book_by_index(book_idx)
    if book is None:
        print(_("Book index out of range: {index}").format(index=book_idx))
        print_bookshelf()
        return None

    if book.fmt == BOOK_FMT_LEGADO:
        server = LegadoServer()
    elif book.fmt == BOOK_FMT_TXT:
        server = TxtServer()
    else:
        print(_("Unsupported book format: {fmt}").format(fmt=book.fmt))
        return None

    try:
        server.initialize(book)
    except Exception as exc:  # pylint: disable=broad-except
        print(_("Failed to initialize book: {error}").format(error=exc))
        return None
    return server


def _build_cli_tts(cli_args: argparse.Namespace) -> TtsSA | None:
    """初始化命令行朗读使用的 TTS 实例。

    Args:
        cli_args (argparse.Namespace): 命令行参数对象

    Returns:
        TtsSA | None: 初始化后的 TTS 实例
    """
    tts = TtsSA()
    tts.reload_config()
    try:
        apply_tts_overrides(tts, cli_args)
        tts.reload_config()
    except Exception as exc:  # pylint: disable=broad-except
        print(_("Invalid TTS config: {error}").format(error=exc))
        return None
    return tts


def _read_current_chapter_cli(context: CliReadContext) -> int | None:
    """朗读当前章节内容。

    Args:
        context (CliReadContext): 命令行朗读运行时上下文

    Returns:
        int | None: 出错时返回命令退出码，否则返回 None
    """
    server = context.server
    chap_txts = server.bd.chap_txts
    start_idx = max(0, min(server.bd.chap_txt_n, len(chap_txts) - 1)) if chap_txts else 0
    start_text = get_start_read_text(server, chap_txts, start_idx)
    if start_text:
        context.prefetch_slot.prefetch(start_text)

    code = _play_intro_texts_cli(context, chap_txts, start_idx)
    if code is not None:
        return code
    return _play_chapter_texts_cli(context, chap_txts, start_idx)


def _play_intro_texts_cli(
    context: CliReadContext,
    chap_txts,
    start_idx: int,
):
    """朗读书名和章节名等开场文本。

    Args:
        context (CliReadContext): 命令行朗读运行时上下文
        chap_txts (list[str]): 当前章节段落列表
        start_idx (int): 正文起始索引

    Returns:
        int | None: 出错时返回命令退出码，否则返回 None
    """
    server = context.server
    intro_texts = build_intro_texts(server)
    for intro_idx, intro_text in enumerate(intro_texts):
        if not intro_text:
            continue

        audio_path = context.prefetch_slot.take(intro_text)
        if not audio_path:
            print(_("Read aloud failed. Remote TTS service may be unavailable."))
            return 2

        _schedule_tts_prefetch_cli(
            server,
            context.prefetch_slot,
            get_next_intro_text(intro_texts, intro_idx, start_idx, chap_txts),
        )

        try:
            code = subprocess.run(["paplay", str(audio_path)], check=False).returncode
        finally:
            context.tts.release(audio_path)

        if code != 0:
            print(_("Audio playback failed"))
            return 2
    return None


def _play_chapter_texts_cli(
    context: CliReadContext,
    chap_txts,
    start_idx: int,
) -> int | None:
    """朗读当前章节的段落文本。

    Args:
        context (CliReadContext): 命令行朗读运行时上下文
        chap_txts (list[str]): 当前章节段落列表
        start_idx (int): 起始段落索引

    Returns:
        int | None: 出错时返回命令退出码，否则返回 None
    """
    for idx in range(start_idx, len(chap_txts)):
        text = (chap_txts[idx] or "").strip()
        if not text:
            continue

        compact_text = " ".join(text.split())
        preview = compact_text[:context.preview_chars]
        if len(compact_text) > context.preview_chars:
            preview += "..."
        print(_("[{current}/{total}] {preview}").format(
            current=idx + 1, total=len(chap_txts), preview=preview))

        audio_path = context.prefetch_slot.take(text)
        if not audio_path:
            print(_("Read aloud failed. Remote TTS service may be unavailable."))
            return 2

        _schedule_tts_prefetch_cli(
            context.server,
            context.prefetch_slot,
            get_next_tts_text(context.server, idx, chap_txts),
        )

        play_start = time.time()
        try:
            code = subprocess.run(["paplay", str(audio_path)], check=False).returncode
        finally:
            context.tts.release(audio_path)
        play_seconds = max(0.0, time.time() - play_start)

        context.server.set_chap_txt_n(idx)
        context.server.save_read_progress(
            context.server.get_chap_n(),
            context.server.get_chap_txt_pos(),
            way=TIME_READ_WAY_LISTEN,
            seconds_override=play_seconds,
        )

        if code != 0:
            print(_("Audio playback failed"))
            return 2
    return None


def _advance_to_next_chapter_cli(server) -> bool:
    """切换到下一章并加载正文。

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
    server.bd.update_chap_txts(server.load_chap_txt(next_chap_n), 0)
    return True


def _get_book_by_index(idx: int) -> Book | None:
    """根据索引读取书架中的书籍

    Args:
        idx (int): 书籍索引，从 1 开始

    Returns:
        Book | None: 对应的书籍对象
    """
    db = LibraryDB()
    try:
        books = list(db.iter_books())
        if idx < 1 or idx > len(books):
            return None
        selected = books[idx - 1]
        return db.get_book_by_md5(selected.md5) or selected
    finally:
        db.close()


def _prefetch_next_chapter_cli(server: LegadoServer | TxtServer) -> None:
    """异步预取下一章正文

    Args:
        server (LegadoServer | TxtServer): 阅读服务实例
    """
    threading.Thread(
        target=server.prefetch_next_chap_txt,
        args=(server.get_chap_n(),),
        daemon=True,
    ).start()


def _prefetch_tts_audio_cli(
    server: LegadoServer | TxtServer,
    slot: AudioPrefetchSlot,
    text: str,
) -> None:
    """异步预取命令行朗读所需的下一条音频

    Args:
        server (LegadoServer | TxtServer): 阅读服务实例
        slot (AudioPrefetchSlot): 音频预取槽
        text (str): 待预取文本
    """
    text = (text or "").strip()
    if not text:
        return

    ensure_next_chapter_prefetched_for_text(server, text)
    slot.prefetch(text)


def _schedule_tts_prefetch_cli(
    server: LegadoServer | TxtServer,
    slot: AudioPrefetchSlot,
    text: str | None,
) -> None:
    """启动后台线程预取下一条音频

    Args:
        server (LegadoServer | TxtServer): 阅读服务实例
        slot (AudioPrefetchSlot): 音频预取槽
        text (str | None): 待预取文本
    """
    text = (text or "").strip()
    if not text:
        return

    threading.Thread(
        target=_prefetch_tts_audio_cli,
        args=(server, slot, text),
        daemon=True,
    ).start()
