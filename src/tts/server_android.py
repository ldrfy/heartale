"""服务"""
import hashlib
import mimetypes

import requests

from .. import PATH_TEMP_TTS
from . import THS

DEFAULT_CONFIG = {
    "url_base": "http://192.168.1.33:1221/api/tts",
    "engine": "com.xiaomi.mibrain.speech",
    "rate": 50,
    "pitch": 100
}


class TtsSA(THS):
    """阅读app相关的webapi"""

    def __init__(self):
        """初始化 Android TTS 服务"""
        super().__init__("server_android", DEFAULT_CONFIG)

    def update_config(self, **kwargs):
        """按 Android TTS 的字段规则更新配置

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
        """校验 Android TTS 配置

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
        """文字转语音，并下载

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
        """根据文本和配置生成缓存键

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


def get_ext(r: requests.Response):
    """根据响应头推断音频文件扩展名

    Args:
        r (requests.Response): HTTP 响应对象

    Returns:
        str: 推断出的文件扩展名
    """
    ct = r.headers.get("content-type", "").split(";")[0].strip()
    if ct:
        ext = mimetypes.guess_extension(ct)
        if ext is not None:
            return ext
    # 常见的替代判断
    if "wav" in ct:
        return ".wav"

    if "mpeg" in ct or "mp3" in ct:
        return ".mp3"

    return ".bin"


def download_stream(text: str, file_name: str, c: dict):
    """请求远程 TTS 服务并将音频流写入缓存文件

    Args:
        text (str): 待转语音文本
        file_name (str): 缓存文件名前缀
        c (dict): TTS 配置

    Returns:
        Path: 下载后的音频文件路径
    """

    params = {
        "text": text,
        "engine": c["engine"],
        "rate": c["rate"],
        "pitch": c["pitch"]
    }

    with requests.get(c["url_base"], timeout=15,
                      stream=True, params=params) as response:
        response.raise_for_status()
        # 根据 Content-Type 推断扩展名
        file_name = file_name + get_ext(response)

        written = 0
        chunk_size = 8192

        out_path = PATH_TEMP_TTS / file_name
        tmp_path = out_path.with_suffix(f"{out_path.suffix}.part")

        with open(tmp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
        tmp_path.replace(out_path)
        return out_path
