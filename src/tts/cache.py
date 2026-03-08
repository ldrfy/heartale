"""TTS 音频缓存与预取的公共工具。"""

import threading
from pathlib import Path

from .. import PATH_TEMP_TTS


class TtsAudioCache:
    """管理不同 TTS 后端共享的音频缓存。"""

    _startup_cleanup_done = False
    _startup_cleanup_lock = threading.Lock()

    def __init__(self, cache_dir: Path | None = None):
        """初始化音频缓存管理器

        Args:
            cache_dir (Path | None, optional): 缓存目录. Defaults to None.
        """
        self._cache_dir = cache_dir or PATH_TEMP_TTS
        self._download_lock = threading.Lock()
        self._cache_locks = {}
        self._retain_lock = threading.Lock()
        self._retain_counts = {}
        self._cleanup_cache_once_per_process()

    def _cleanup_cache_once_per_process(self):
        """在当前进程中只执行一次缓存目录清理。"""
        with self._startup_cleanup_lock:
            if type(self)._startup_cleanup_done:
                return
            self._cleanup_cache_dir()
            type(self)._startup_cleanup_done = True

    def _cleanup_cache_dir(self):
        """清理异常退出后遗留在缓存目录中的音频文件。"""
        try:
            for path in self._cache_dir.iterdir():
                if not path.is_file():
                    continue
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
                except OSError:
                    continue
        except FileNotFoundError:
            pass

    def find_cached_file(self, cache_key: str):
        """根据缓存键查找已存在的音频文件

        Args:
            cache_key (str): 缓存键

        Returns:
            Path | None: 已存在的缓存文件路径
        """
        matches = sorted(self._cache_dir.glob(f"{cache_key}.*"))
        if matches:
            return matches[0]
        return None

    def get_cache_lock(self, cache_key: str):
        """获取指定缓存键对应的互斥锁

        Args:
            cache_key (str): 缓存键

        Returns:
            threading.Lock: 对应缓存键的互斥锁
        """
        with self._download_lock:
            lock = self._cache_locks.get(cache_key)
            if lock is None:
                lock = threading.Lock()
                self._cache_locks[cache_key] = lock
            return lock

    def retain(self, path):
        """保留音频文件，增加引用计数

        Args:
            path (Path | str | None): 音频文件路径

        Returns:
            Path | None: 保留后的音频文件路径
        """
        if path is None:
            return None

        path = Path(path)
        with self._retain_lock:
            self._retain_counts[path] = self._retain_counts.get(path, 0) + 1
        return path

    def release(self, path):
        """释放音频文件，引用归零时删除

        Args:
            path (Path | str | None): 音频文件路径
        """
        if path is None:
            return

        path = Path(path)
        delete_now = False
        with self._retain_lock:
            count = self._retain_counts.get(path, 0)
            if count <= 1:
                self._retain_counts.pop(path, None)
                delete_now = True
            else:
                self._retain_counts[path] = count - 1

        if delete_now:
            self.delete_cached_file(path)

    def delete_cached_file(self, path: Path):
        """删除缓存目录中的音频文件

        Args:
            path (Path): 音频文件路径
        """
        try:
            resolved = path.resolve()
            cache_root = self._cache_dir.resolve()
            if resolved.parent != cache_root:
                return
            if resolved.exists():
                resolved.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return


class AudioPrefetchSlot:
    """保留一条已预取音频，供下一次播放直接使用。"""

    def __init__(self, tts):
        """初始化单槽音频预取器

        Args:
            tts (THS): 具体的 TTS 实例
        """
        self._tts = tts
        self._lock = threading.Lock()
        self._text = None
        self._path = None

    def prefetch(self, text: str):
        """预取下一条待播放的音频

        Args:
            text (str): 待转语音文本

        Returns:
            Path | None: 预取后的音频文件路径
        """
        text = (text or "").strip()
        if not text:
            return None

        with self._lock:
            if self._text == text and self._path is not None:
                return self._path

        path = self._tts.acquire(text)
        if path is None:
            return None

        old_path = None
        with self._lock:
            if self._text == text and self._path is not None:
                old_path = path
            else:
                old_path = self._path
                self._text = text
                self._path = path

        if old_path is not None and old_path != path:
            self._tts.release(old_path)
        elif old_path == path:
            self._tts.release(path)
        return path

    def take(self, text: str):
        """取出已预取音频，不存在时同步获取

        Args:
            text (str): 待转语音文本

        Returns:
            Path | None: 可直接播放的音频文件路径
        """
        text = (text or "").strip()
        if not text:
            return None

        with self._lock:
            if self._text == text and self._path is not None:
                path = self._path
                self._text = None
                self._path = None
                return path

        return self._tts.acquire(text)

    def clear(self):
        """清空预取槽并释放保留的音频文件"""
        with self._lock:
            path = self._path
            self._text = None
            self._path = None
        if path is not None:
            self._tts.release(path)
