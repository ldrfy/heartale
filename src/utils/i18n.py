"""应用语言配置相关工具。"""

import locale
import os

from ..entity import LibraryDB

APP_LANGUAGE_CONFIG_KEY = "app_language"
APP_LANGUAGE_AUTO = "auto"
APP_LANGUAGE_ZH_CN = "zh_CN"
APP_LANGUAGE_EN_US = "en_US"
APP_LANGUAGE_OPTIONS = [
    APP_LANGUAGE_AUTO,
    APP_LANGUAGE_ZH_CN,
    APP_LANGUAGE_EN_US,
]


def get_app_language() -> str:
    """读取应用语言设置。

    Returns:
        str: 当前保存的应用语言设置
    """
    db = LibraryDB()
    value = db.get_config(APP_LANGUAGE_CONFIG_KEY, APP_LANGUAGE_AUTO)
    db.close()

    language = str(value or APP_LANGUAGE_AUTO).strip()
    if language not in APP_LANGUAGE_OPTIONS:
        return APP_LANGUAGE_AUTO
    return language


def set_app_language(language: str) -> str:
    """保存应用语言设置。

    Args:
        language (str): 要保存的语言值

    Returns:
        str: 保存后的语言值
    """
    normalized = str(language or APP_LANGUAGE_AUTO).strip()
    if normalized not in APP_LANGUAGE_OPTIONS:
        normalized = APP_LANGUAGE_AUTO

    db = LibraryDB()
    db.set_config(APP_LANGUAGE_CONFIG_KEY, normalized)
    db.close()
    return normalized


def get_effective_app_language() -> str:
    """获取当前生效的应用语言。

    Returns:
        str: 当前生效的应用语言
    """
    configured = get_app_language()
    if configured != APP_LANGUAGE_AUTO:
        return configured

    lang, _encoding = locale.getlocale()
    if not lang:
        lang = os.environ.get("LANG", "")
    normalized = str(lang).replace("-", "_")
    if normalized.lower().startswith("zh"):
        return APP_LANGUAGE_ZH_CN
    if normalized.lower().startswith("en"):
        return APP_LANGUAGE_EN_US
    return APP_LANGUAGE_AUTO


def is_english_language() -> bool:
    """判断当前生效语言是否为英文。

    Returns:
        bool: 当前生效语言是否为英文
    """
    return get_effective_app_language() == APP_LANGUAGE_EN_US
