"""CLI 与 GUI 共用的朗读执行器。"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from requests import RequestException

from ..servers import Server
from . import THS
from .cache import AudioPrefetchSlot


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


@dataclass(slots=True)
class TtsReadRunnerHooks:
    """定义朗读执行器在不同前端下的回调。"""

    play_audio: Callable[[Path | str], bool]
    should_stop: Callable[[], bool]
    on_first_audio_ready: Callable[[], None] = field(default=lambda: None)
    before_paragraph: Callable[[int, str], None] = field(
        default=lambda _idx, _text: None)
    after_paragraph: Callable[[int, float], None] = field(
        default=lambda _idx, _seconds: None
    )
    on_prefetch_error: Callable[[Exception],
                                None] = field(default=lambda _exc: None)


@dataclass(slots=True)
class TtsReadResult:
    """描述一次章节朗读执行结果。"""

    completed_chapter: bool = False
    missing_audio: bool = False
    playback_failed: bool = False
    stopped: bool = False


@dataclass(slots=True)
class TtsReadContext:
    """封装一次朗读执行所需的上下文。"""

    server: Server
    tts: THS | None
    prefetch_slot: AudioPrefetchSlot | None
    chap_txts: list[str]
    hooks: TtsReadRunnerHooks


@dataclass(slots=True)
class _RunnerState:
    """保存朗读执行过程中的临时状态。"""

    start_idx: int
    first_audio_ready: bool = False


def take_tts_audio(
    tts: THS | None,
    prefetch_slot: AudioPrefetchSlot | None,
    text: str,
) -> Path | None:
    """获取一条文本对应的音频文件。

    Args:
        tts (THS | None): TTS 服务实例
        prefetch_slot (AudioPrefetchSlot | None): 音频预取槽
        text (str): 待朗读文本

    Returns:
        Path | None: 可播放的音频文件路径
    """
    text = (text or "").strip()
    if not text or not tts or prefetch_slot is None:
        return None

    for _ in range(2):
        path = prefetch_slot.take(text)
        if path is None:
            return None

        if Path(path).exists():
            return Path(path)

        tts.release(path)
    return None


def release_tts_audio(tts: THS | None, audio_path: Path | str | None) -> None:
    """释放音频文件引用。

    Args:
        tts (THS | None): TTS 服务实例
        audio_path (Path | str | None): 音频文件路径
    """
    if tts and audio_path:
        tts.release(audio_path)


def prefetch_tts_audio(
    server: Server,
    prefetch_slot: AudioPrefetchSlot | None,
    text: str,
) -> None:
    """同步预取一条文本对应的音频。

    Args:
        server (Server): 阅读服务实例
        prefetch_slot (AudioPrefetchSlot | None): 音频预取槽
        text (str): 待预取文本
    """
    text = (text or "").strip()
    if not text or prefetch_slot is None:
        return
    try:
        ensure_next_chapter_prefetched_for_text(server, text)
    except (OSError, RuntimeError, ValueError, RequestException):
        pass
    prefetch_slot.prefetch(text)


def schedule_tts_prefetch(
    server: Server,
    prefetch_slot: AudioPrefetchSlot | None,
    text: str | None,
    should_stop: Callable[[], bool] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """异步预取下一条音频。

    Args:
        server (Server): 阅读服务实例
        prefetch_slot (AudioPrefetchSlot | None): 音频预取槽
        text (str | None): 待预取文本
        should_stop (Callable[[], bool] | None, optional): 停止检查回调
        on_error (Callable[[Exception], None] | None, optional): 预取异常回调
    """
    text = (text or "").strip()
    if not text or prefetch_slot is None:
        return
    if should_stop and should_stop():
        return

    def worker() -> None:
        if should_stop and should_stop():
            return
        try:
            prefetch_tts_audio(server, prefetch_slot, text)
        except Exception as exc:  # pylint: disable=broad-except
            if on_error:
                on_error(exc)

    threading.Thread(target=worker, daemon=True).start()


def run_tts_read_loop(context: TtsReadContext, start_idx: int) -> TtsReadResult:
    """执行一整章的朗读流程。

    Args:
        context (TtsReadContext): 朗读执行上下文
        start_idx (int): 起始段落索引

    Returns:
        TtsReadResult: 朗读执行结果
    """
    if not context.chap_txts:
        return TtsReadResult(completed_chapter=True)

    state = _RunnerState(start_idx=_clamp_start_idx(
        context.chap_txts, start_idx))
    _prime_first_audio(context, state)

    intro_result = _run_intro_texts(context, state)
    if intro_result is not None:
        return intro_result

    paragraph_result = _run_paragraph_texts(context, state)
    if paragraph_result is not None:
        return paragraph_result

    return TtsReadResult(completed_chapter=True)


def _clamp_start_idx(chap_txts: list[str], start_idx: int) -> int:
    """限制起始段落索引到合法范围内。

    Args:
        chap_txts (list[str]): 当前章节段落列表
        start_idx (int): 起始段落索引

    Returns:
        int: 合法的起始段落索引
    """
    return max(0, min(start_idx, len(chap_txts) - 1))


def _prime_first_audio(context: TtsReadContext, state: _RunnerState) -> None:
    """预热本次朗读的第一条音频。

    Args:
        context (TtsReadContext): 朗读执行上下文
        state (_RunnerState): 执行过程状态
    """
    start_text = get_start_read_text(
        context.server,
        context.chap_txts,
        state.start_idx,
    )
    if start_text:
        prefetch_tts_audio(context.server, context.prefetch_slot, start_text)


def _run_intro_texts(
    context: TtsReadContext,
    state: _RunnerState,
) -> TtsReadResult | None:
    """执行开场播报。

    Args:
        context (TtsReadContext): 朗读执行上下文
        state (_RunnerState): 执行过程状态

    Returns:
        TtsReadResult | None: 提前结束时返回结果，否则返回 None
    """
    intro_texts = build_intro_texts(context.server)
    for intro_idx, intro_text in enumerate(intro_texts):
        if context.hooks.should_stop():
            return TtsReadResult(stopped=True)
        if not intro_text:
            continue

        next_text = get_next_intro_text(
            intro_texts,
            intro_idx,
            state.start_idx,
            context.chap_txts,
        )
        result = _play_single_text(context, state, intro_text, next_text)
        if result is not None:
            return result
    return None


def _run_paragraph_texts(
    context: TtsReadContext,
    state: _RunnerState,
) -> TtsReadResult | None:
    """执行正文段落朗读。

    Args:
        context (TtsReadContext): 朗读执行上下文
        state (_RunnerState): 执行过程状态

    Returns:
        TtsReadResult | None: 提前结束时返回结果，否则返回 None
    """
    for idx in range(state.start_idx, len(context.chap_txts)):
        if context.hooks.should_stop():
            return TtsReadResult(stopped=True)

        text = (context.chap_txts[idx] or "").strip()
        if not text:
            continue

        next_text = get_next_tts_text(context.server, idx, context.chap_txts)
        result = _play_single_text(
            context,
            state,
            text,
            next_text,
            idx=idx,
        )
        if result is not None:
            return result
    return None


def _play_single_text(
    context: TtsReadContext,
    state: _RunnerState,
    text: str,
    next_text: str | None,
    idx: int | None = None,
) -> TtsReadResult | None:
    """播放单条文本并触发前后回调。

    Args:
        context (TtsReadContext): 朗读执行上下文
        state (_RunnerState): 执行过程状态
        text (str): 当前文本
        next_text (str | None): 下一条待预取文本
        idx (int | None, optional): 当前段落索引. Defaults to None.

    Returns:
        TtsReadResult | None: 提前结束时返回结果，否则返回 None
    """
    audio_path = take_tts_audio(context.tts, context.prefetch_slot, text)
    if not audio_path:
        return TtsReadResult(missing_audio=True)

    _ensure_first_audio_ready(context, state)
    schedule_tts_prefetch(
        context.server,
        context.prefetch_slot,
        next_text,
        should_stop=context.hooks.should_stop,
        on_error=context.hooks.on_prefetch_error,
    )

    if idx is not None:
        context.hooks.before_paragraph(idx, text)

    play_seconds = 0.0
    try:
        play_start = time.time()
        played_ok = context.hooks.play_audio(audio_path)
        play_seconds = max(0.0, time.time() - play_start)
    finally:
        release_tts_audio(context.tts, audio_path)

    if idx is not None:
        context.hooks.after_paragraph(idx, play_seconds)

    if played_ok:
        return None
    if context.hooks.should_stop():
        return TtsReadResult(stopped=True)
    return TtsReadResult(playback_failed=True)


def _ensure_first_audio_ready(context: TtsReadContext, state: _RunnerState) -> None:
    """确保首条音频就绪回调只触发一次。

    Args:
        context (TtsReadContext): 朗读执行上下文
        state (_RunnerState): 执行过程状态
    """
    if state.first_audio_ready:
        return
    context.hooks.on_first_audio_ready()
    state.first_audio_ready = True
