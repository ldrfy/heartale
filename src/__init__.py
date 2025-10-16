"初始化"
import os
from pathlib import Path

PATH_CONFIG = Path(os.getenv("XDG_CONFIG_HOME",
                   Path.home() / ".config")) / "heartale"
print(PATH_CONFIG)
PATH_CONFIG_BOOKS = PATH_CONFIG / "books"

os.makedirs(PATH_CONFIG_BOOKS, exist_ok=True)
