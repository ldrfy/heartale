'服务'
import mimetypes

import requests

from .. import PATH_TEMP_TTS
from . import THS

DEFAULT_CONFIG = {
    "url_base": "http://192.168.31.6:1221/api/tts",
    "engine": "com.xiaomi.mibrain.speech",
    "rate": 50,
    "pitch": 100
}


class TtsSA(THS):
    """阅读app相关的webapi"""

    def __init__(self):
        super().__init__("server_android", DEFAULT_CONFIG)

    def download(self, text, file_name=None):
        download_stream(text, file_name, self.c)


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


def download_stream(text: str, file_name: str, c: dict, print_log=False):
    """_summary_

    Args:
        text (str): _description_
        out_path (str): _description_
        timeout (int, optional): _description_. Defaults to 15.
        print_log (bool, optional): _description_. Defaults to False.

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

        total = int(response.headers.get("content-length") or 0)
        written = 0
        chunk_size = 8192

        out_path = PATH_TEMP_TTS / file_name

        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if total and print_log:
                    pct = written / total * 100
                    print(f"\r已下载: {written}/{total} bytes ({pct:.1f}%)",
                          end="", flush=True)
        if total:
            print("\n下载完成:", out_path)
        else:
            print("下载完成（总长度未知）:", out_path)
        return out_path


if __name__ == "__main__":
    data = {
        "text": "测试一下",
        "engine": "com.xiaomi.mibrain.speech",
        "rate": 50,
        "pitch": 100
    }
    file_path = download_stream("http://192.168.31.6:1221/api/tts",
                                "test", data,  print_log=True)
