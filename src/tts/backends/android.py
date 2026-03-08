"""Android TTS 后端实现。"""
import hashlib

from .. import THS, download_stream_to_cache

ANDROID_TTS_CONFIG_KEY = "tts_android"

DEFAULT_CONFIG = {
    "url_base": "http://192.168.1.33:1221/api/tts",
    "engine": "com.xiaomi.mibrain.speech",
    "rate": 50,
    "pitch": 100,
}


class AndroidTtsBackend(THS):
    """Android TTS 后端。"""

    def __init__(self):
        """初始化 Android TTS 服务。"""
        super().__init__(ANDROID_TTS_CONFIG_KEY, DEFAULT_CONFIG)

    def update_config(self, **kwargs):
        """按 Android TTS 的字段规则更新配置。

        Args:
            **kwargs: 待更新的配置项

        Returns:
            dict: 更新后的配置
        """
        return self.update_config_fields(
            {
                "url_base": lambda value: str(value).strip(),
                "engine": lambda value: str(value).strip(),
                "rate": int,
                "pitch": int,
            },
            **kwargs,
        )

    def _validate_config(self, cfg: dict):
        """校验 Android TTS 配置。

        Args:
            cfg (dict): 待校验的配置

        Returns:
            dict: 校验后的配置
        """
        self.validate_required_fields(cfg, ["url_base", "engine"])
        self.validate_int_range(cfg, "rate", 0, 100)
        self.validate_int_range(cfg, "pitch", 0, 100)
        return cfg

    def download(self, text, file_name=None):
        """文字转语音，并下载。

        Args:
            text (str): 待转语音文本
            file_name (str, optional): 指定缓存文件名. Defaults to None.

        Returns:
            Path | None: 下载后的音频文件路径
        """
        text = (text or "").strip()
        if not text:
            return None

        cache_key = file_name or self._build_cache_key(text)
        return self.download_with_cache(
            cache_key,
            lambda: download_stream(text, cache_key, self.c),
        )

    def _build_cache_key(self, text: str) -> str:
        """根据文本和配置生成缓存键。

        Args:
            text (str): 待转语音文本

        Returns:
            str: 音频缓存键
        """
        payload = "|".join([
            text,
            str(self.c["engine"]),
            str(self.c["rate"]),
            str(self.c["pitch"]),
        ])
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def download_stream(text: str, file_name: str, config: dict):
    """请求远程 TTS 服务并将音频流写入缓存文件。

    Args:
        text (str): 待转语音文本
        file_name (str): 缓存文件名前缀
        config (dict): TTS 配置

    Returns:
        Path: 下载后的音频文件路径
    """
    params = {
        "text": text,
        "engine": config["engine"],
        "rate": config["rate"],
        "pitch": config["pitch"],
    }
    return download_stream_to_cache(config["url_base"], params, file_name)
