"""文字转语音并下载。"""

import mimetypes
from pathlib import Path

import requests

from .. import PATH_TEMP_TTS
from ..entity import LibraryDB
from .cache import TtsAudioCache


class THS:
    """音频下载
    """

    def __init__(self, key, default_config):
        self.key = key
        self.default_config = dict(default_config or {})
        self._audio_cache = TtsAudioCache()

        db = LibraryDB()
        self.c = db.get_config(key, self.default_config)
        db.close()
        self.c = self._normalize_config(self.c)

    def _normalize_config(self, config):
        """保证配置字段完整，并与默认配置兼容。"""
        if not isinstance(config, dict):
            config = {}

        merged = dict(self.default_config)
        merged.update(config)
        return merged

    def reload_config(self):
        """从数据库重新加载配置。"""
        db = LibraryDB()
        self.c = db.get_config(self.key, self.default_config)
        db.close()
        self.c = self._normalize_config(self.c)
        return dict(self.c)

    def set_config(self, config):
        """设置配置

        Args:
            config (dict): 待保存的配置
        """
        config = self._normalize_config(config)

        db = LibraryDB()
        db.set_config(self.key, config)
        db.close()

        self.c = config

    def get_config(self):
        """返回当前配置副本，避免外部误改内部状态

        Returns:
            dict: 当前配置副本
        """
        return dict(self.c)

    def update_config_fields(self, field_parsers: dict, **kwargs):
        """按后端提供的字段解析器更新配置

        Args:
            field_parsers (dict): 配置字段与解析函数的映射
            **kwargs: 待更新的配置项

        Returns:
            dict: 更新后的配置
        """
        cfg = self.get_config()
        for field, parser in field_parsers.items():
            if field not in kwargs or kwargs[field] is None:
                continue
            cfg[field] = parser(kwargs[field])

        self._validate_config(cfg)
        self.set_config(cfg)
        return cfg

    def validate_required_fields(self, cfg: dict, fields):
        """校验必填配置项非空

        Args:
            cfg (dict): 待校验的配置
            fields (list[str] | tuple[str, ...]): 必填字段列表
        """
        for field in fields:
            if not cfg.get(field):
                raise ValueError(f"{field} can not be empty")

    def validate_int_range(self, cfg: dict, field: str, minimum: int, maximum: int):
        """校验整数配置项的取值范围

        Args:
            cfg (dict): 待校验的配置
            field (str): 字段名
            minimum (int): 最小值
            maximum (int): 最大值
        """
        value = int(cfg[field])
        if not minimum <= value <= maximum:
            raise ValueError(
                f"{field} must be between {minimum} and {maximum}")

    def _validate_config(self, cfg: dict):
        """校验配置

        Args:
            cfg (dict): 待校验的配置

        Returns:
            dict: 校验后的配置
        """
        return cfg

    def download_with_cache(self, cache_key: str, loader):
        """优先从缓存获取音频，不存在时调用加载器生成

        Args:
            cache_key (str): 缓存键
            loader (Callable): 实际下载或生成音频的回调

        Returns:
            Path: 缓存中的音频路径或新生成的音频路径
        """
        with self._audio_cache.get_cache_lock(cache_key):
            cached = self._audio_cache.find_cached_file(cache_key)
            if cached is not None:
                return cached
            return loader()

    def acquire(self, text, file_name=None):
        """获取音频文件并增加引用计数

        Args:
            text (str): 待转语音文本
            file_name (str, optional): 指定缓存文件名. Defaults to None.

        Returns:
            Path | None: 可用的音频文件路径
        """
        for _ in range(2):
            path = self.download(text, file_name=file_name)
            if path is None:
                return None

            retained_path = self.retain(path)
            if retained_path is None:
                return None

            if Path(retained_path).exists():
                return retained_path

            self.release(retained_path)
        return None

    def retain(self, path):
        """保留音频文件，避免仍在使用时被删除

        Args:
            path (Path | str | None): 音频文件路径

        Returns:
            Path | None: 保留后的音频文件路径
        """
        return self._audio_cache.retain(path)

    def release(self, path):
        """释放音频文件，引用归零时删除缓存

        Args:
            path (Path | str | None): 音频文件路径
        """
        self._audio_cache.release(path)

    def download(self, text, file_name=None):
        """文字转语音，并下载

        Args:
            text (str): 待转语音文本
            file_name (str, optional): 指定缓存文件名. Defaults to None.

        Returns:
            Path | None: 下载后的音频文件路径
        """
        raise NotImplementedError


def infer_audio_extension(response: requests.Response) -> str:
    """根据响应头推断音频文件扩展名。

    Args:
        response (requests.Response): HTTP 响应对象

    Returns:
        str: 推断出的文件扩展名
    """
    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    if content_type:
        ext = mimetypes.guess_extension(content_type)
        if ext is not None:
            return ext
    if "wav" in content_type:
        return ".wav"
    if "mpeg" in content_type or "mp3" in content_type:
        return ".mp3"
    return ".bin"


def download_stream_to_cache(url: str, params: dict, file_name: str):
    """请求远程 TTS 服务并将音频流写入缓存文件。

    Args:
        url (str): 远程 TTS 请求地址
        params (dict): 请求参数
        file_name (str): 缓存文件名前缀

    Returns:
        Path: 下载后的音频文件路径
    """
    with requests.get(
        url,
        timeout=15,
        stream=True,
        params=params,
    ) as response:
        response.raise_for_status()
        file_name = file_name + infer_audio_extension(response)
        out_path = PATH_TEMP_TTS / file_name
        tmp_path = out_path.with_suffix(f"{out_path.suffix}.part")

        with open(tmp_path, "wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                output_file.write(chunk)
        tmp_path.replace(out_path)
        return out_path
