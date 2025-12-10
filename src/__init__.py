"初始化"
import os
from pathlib import Path

PATH_CONFIG = Path(os.getenv("XDG_CONFIG_HOME",
                             Path.home() / ".config")) / "heartale"

PATH_CONFIG_BOOKS = PATH_CONFIG / "books"

os.makedirs(PATH_CONFIG_BOOKS, exist_ok=True)

PATH_TEMP = Path(os.getenv("XDG_CACHE_HOME",
                           Path.home() / ".cache")) / "heartale"

PATH_TEMP_TTS = PATH_TEMP / "tts"

os.makedirs(PATH_TEMP_TTS, exist_ok=True)
