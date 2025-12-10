'文字转语音并下载'
from .. import PATH_TEMP_TTS
from ..entity import LibraryDB


class THS():
    """音频下载
    """

    def __init__(self, key, default_config):
        self.key = key

        db = LibraryDB()
        self.c = db.get_config(key, default_config)
        db.close()

    def set_config(self, config):
        """设置配置

        Args:
            config (dict): _description_
        """
        db = LibraryDB()
        db.set_config(self.key, config)
        db.close()

        self.c = config

    def download(self, text, file_name=None):
        """文字转语音，并下载

        Args:
            text (str): _description_
            out_path (str, optional): _description_. Defaults to None.
        """
        print(text)
        ext = "xxx"
        return PATH_TEMP_TTS / file_name+ext
