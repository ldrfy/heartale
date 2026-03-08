"""命令行朗读流程。"""

import argparse
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from gettext import gettext as _
from pathlib import Path

from .entity import LibraryDB
from .entity.book import Book
from .entity.time_read import TIME_READ_WAY_LISTEN
from .servers.legado import LegadoServer
from .servers.txt import TxtServer
from .tts import THS
from .tts.backends import apply_active_tts_overrides, create_active_tts_backend
from .tts.cache import AudioPrefetchSlot
from .tts.read_runner import (TtsReadContext, TtsReadRunnerHooks,
                              run_tts_read_loop)
from .utils.reader import (advance_to_next_chapter, create_reader_server,
                           prefetch_next_chapter_async)


@dataclass(slots=True)
class CliReadContext:
    """命令行朗读运行时上下文。"""

    server: LegadoServer | TxtServer
    tts: THS
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

    print(_("Book[{index}]: {name}").format(
        index=book_idx, name=server.book.name))
    print(_("Chapter: {chapter}").format(
        chapter=server.get_chap_name(server.get_chap_n())))
    prefetch_slot = AudioPrefetchSlot(tts)
    context = CliReadContext(
        server=server,
        tts=tts,
        prefetch_slot=prefetch_slot,
        preview_chars=preview_chars,
    )
    prefetch_next_chapter_async(context.server)

    try:
        while True:
            code = _read_current_chapter_cli(context)
            if code is not None:
                return code

            if not advance_to_next_chapter(context.server):
                print(_("Finished all chapters"))
                return 0

            prefetch_next_chapter_async(context.server)
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

    try:
        server = create_reader_server(book)
    except Exception as exc:  # pylint: disable=broad-except
        if str(exc).startswith("Unsupported book format:"):
            print(_("Unsupported book format: {fmt}").format(fmt=book.fmt))
        else:
            print(_("Failed to initialize book: {error}").format(error=exc))
        return None
    return server


def _build_cli_tts(cli_args: argparse.Namespace) -> THS | None:
    """初始化命令行朗读使用的 TTS 实例。

    Args:
        cli_args (argparse.Namespace): 命令行参数对象

    Returns:
        THS | None: 初始化后的 TTS 实例
    """
    tts = create_active_tts_backend()
    tts.reload_config()
    try:
        apply_active_tts_overrides(tts, cli_args)
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
    start_idx = max(0, min(server.bd.chap_txt_n, len(
        chap_txts) - 1)) if chap_txts else 0
    result = run_tts_read_loop(
        TtsReadContext(
            server=context.server,
            tts=context.tts,
            prefetch_slot=context.prefetch_slot,
            chap_txts=chap_txts,
            hooks=TtsReadRunnerHooks(
                play_audio=_play_audio_cli,
                should_stop=lambda: False,
                before_paragraph=lambda idx, text: _before_cli_tts_paragraph(
                    context, idx, len(chap_txts), text
                ),
                after_paragraph=lambda _idx, seconds: _save_cli_read_progress(
                    context.server, seconds
                ),
            ),
        ),
        start_idx=start_idx,
    )
    if result.missing_audio:
        print(_("Read aloud failed. Remote TTS service may be unavailable."))
        return 2
    if result.playback_failed:
        print(_("Audio playback failed"))
        return 2
    return None


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


def _play_audio_cli(audio_path) -> bool:
    """播放单个音频文件。

    Args:
        audio_path (Path | str): 音频文件路径

    Returns:
        bool: 是否播放成功
    """
    if not Path(audio_path).exists():
        return False
    return subprocess.run(["paplay", str(audio_path)], check=False).returncode == 0


def _print_paragraph_preview(
    context: CliReadContext,
    idx: int,
    total: int,
    text: str,
) -> None:
    """输出当前朗读段落的预览文本。

    Args:
        context (CliReadContext): 命令行朗读运行时上下文
        idx (int): 当前段落索引
        total (int): 当前章节总段数
        text (str): 当前段落文本
    """
    compact_text = " ".join(text.split())
    preview = compact_text[:context.preview_chars]
    if len(compact_text) > context.preview_chars:
        preview += "..."
    print(_("[{current}/{total}] {preview}").format(
        current=idx + 1,
        total=total,
        preview=preview,
    ))


def _before_cli_tts_paragraph(
    context: CliReadContext,
    idx: int,
    total: int,
    text: str,
) -> None:
    """在命令行朗读每段正文前同步当前位置并输出预览。

    Args:
        context (CliReadContext): 命令行朗读运行时上下文
        idx (int): 当前段落索引
        total (int): 当前章节总段数
        text (str): 当前段落文本
    """
    server = context.server
    server.set_chap_txt_n(idx)
    server.save_read_progress(
        server.get_chap_n(),
        server.get_paragraph_anchor_pos(idx),
        way=None,
    )
    _print_paragraph_preview(context, idx, total, text)


def _save_cli_read_progress(server: LegadoServer | TxtServer, seconds: float) -> None:
    """保存命令行朗读进度。

    Args:
        server (LegadoServer | TxtServer): 阅读服务实例
        seconds (float): 本段朗读耗时
    """
    server.save_read_progress(
        server.get_chap_n(),
        server.get_chap_txt_pos(),
        way=TIME_READ_WAY_LISTEN,
        seconds_override=seconds,
    )
