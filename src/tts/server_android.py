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
        super().__init__("server_android", DEFAULT_CONFIG)

    def update_config(self, **kwargs):
        """按字段更新配置并持久化到 heartale.db。"""
        cfg = self.get_config()

        if "url_base" in kwargs and kwargs["url_base"] is not None:
            cfg["url_base"] = str(kwargs["url_base"]).strip()
        if "engine" in kwargs and kwargs["engine"] is not None:
            cfg["engine"] = str(kwargs["engine"]).strip()
        if "rate" in kwargs and kwargs["rate"] is not None:
            cfg["rate"] = int(kwargs["rate"])
        if "pitch" in kwargs and kwargs["pitch"] is not None:
            cfg["pitch"] = int(kwargs["pitch"])

        self._validate_config(cfg)
        self.set_config(cfg)
        return cfg

    def _validate_config(self, cfg: dict):
        if not cfg.get("url_base"):
            raise ValueError("url_base can not be empty")
        if not cfg.get("engine"):
            raise ValueError("engine can not be empty")
        if not 0 <= int(cfg["rate"]) <= 100:
            raise ValueError("rate must be between 0 and 100")
        if not 0 <= int(cfg["pitch"]) <= 100:
            raise ValueError("pitch must be between 0 and 100")

    def download(self, text, file_name=None):
        text = (text or "").strip()
        if not text:
            return None

        cache_key = file_name or self._build_cache_key(text)
        cached = self._find_cached_file(cache_key)
        if cached is not None:
            return cached

        return download_stream(text, cache_key, self.c)

    def _build_cache_key(self, text: str) -> str:
        payload = "|".join([
            text,
            str(self.c["engine"]),
            str(self.c["rate"]),
            str(self.c["pitch"]),
        ])
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _find_cached_file(self, cache_key: str):
        matches = sorted(PATH_TEMP_TTS.glob(f"{cache_key}.*"))
        if matches:
            return matches[0]
        return None


def get_ext(r: requests.Response):
    """_summary_

    Args:
        r (_type_): _description_

    Returns:
        str: _description_
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
    """_summary_

    Args:
        text (str): _description_
        file_name (str): _description_
        c (dict, optional): _description_. Defaults to 15.

    Returns:
        _type_: _description_
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

        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
        return out_path
