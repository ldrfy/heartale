'文字转语音并下载'
from .. import PATH_TEMP_TTS
from ..entity import LibraryDB


class THS():
    """音频下载
    """

    def __init__(self, key, default_config):
        self.key = key
        self.default_config = dict(default_config or {})

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
            config (dict): _description_
        """
        config = self._normalize_config(config)

        db = LibraryDB()
        db.set_config(self.key, config)
        db.close()

        self.c = config

    def get_config(self):
        """返回当前配置（副本），避免外部误改内部状态。"""
        return dict(self.c)

    def download(self, text, file_name=None):
        """文字转语音，并下载

        Args:
            text (str): _description_
            out_path (str, optional): _description_. Defaults to None.
        """
        print(text)
        ext = "xxx"
        return PATH_TEMP_TTS / file_name+ext
