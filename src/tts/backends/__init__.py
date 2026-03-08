"""TTS 后端实现集合。"""

import argparse

from ...entity import LibraryDB
from .android import AndroidTtsBackend

TTS_BACKEND_CONFIG_KEY = "tts_backend"
TTS_BACKEND_ANDROID = "tts_android"

_BACKEND_FACTORIES = {
    TTS_BACKEND_ANDROID: AndroidTtsBackend,
}


def list_tts_backend_names() -> list[str]:
    """返回当前支持的 TTS 后端名称列表。

    Returns:
        list[str]: 可用后端名称列表
    """
    return sorted(_BACKEND_FACTORIES)


def get_active_tts_backend_name() -> str:
    """读取当前活动的 TTS 后端名称。

    Returns:
        str: 当前活动后端名称
    """
    db = LibraryDB()
    try:
        backend_name = db.get_config(
            TTS_BACKEND_CONFIG_KEY, TTS_BACKEND_ANDROID)
    finally:
        db.close()

    if backend_name not in _BACKEND_FACTORIES:
        return TTS_BACKEND_ANDROID
    return str(backend_name)


def set_active_tts_backend_name(backend_name: str) -> str:
    """保存当前活动的 TTS 后端名称。

    Args:
        backend_name (str): 待保存的后端名称

    Returns:
        str: 实际保存的后端名称
    """
    backend_name = str(backend_name).strip()
    if backend_name not in _BACKEND_FACTORIES:
        raise ValueError(f"Unsupported TTS backend: {backend_name}")

    db = LibraryDB()
    try:
        db.set_config(TTS_BACKEND_CONFIG_KEY, backend_name)
    finally:
        db.close()
    return backend_name


def create_tts_backend(backend_name: str | None = None):
    """创建指定名称的 TTS 后端实例。

    Args:
        backend_name (str | None, optional): 后端名称. Defaults to None.

    Returns:
        THS: 对应的 TTS 后端实例
    """
    resolved_name = backend_name or TTS_BACKEND_ANDROID
    if resolved_name not in _BACKEND_FACTORIES:
        raise ValueError(f"Unsupported TTS backend: {resolved_name}")
    return _BACKEND_FACTORIES[resolved_name]()


def create_active_tts_backend():
    """创建当前活动的 TTS 后端实例。

    Returns:
        THS: 当前活动的 TTS 后端实例
    """
    return create_tts_backend(get_active_tts_backend_name())


def build_active_tts_override_kwargs(cli_args: argparse.Namespace) -> dict:
    """提取当前活动 TTS 后端的命令行覆盖配置。

    Args:
        cli_args (argparse.Namespace): 命令行参数对象

    Returns:
        dict: 当前活动后端支持的覆盖配置
    """
    backend_name = get_active_tts_backend_name()
    if backend_name == TTS_BACKEND_ANDROID:
        return _build_tts_android_override_kwargs(cli_args)
    return {}


def apply_active_tts_overrides(tts, cli_args: argparse.Namespace) -> None:
    """将命令行覆盖配置写入当前活动 TTS 后端实例。

    Args:
        tts (THS): TTS 实例
        cli_args (argparse.Namespace): 命令行参数对象
    """
    kwargs = build_active_tts_override_kwargs(cli_args)
    if kwargs:
        tts.update_config(**kwargs)


def _build_tts_android_override_kwargs(cli_args: argparse.Namespace) -> dict:
    """从命令行参数中提取 Android TTS 覆盖配置。

    Args:
        cli_args (argparse.Namespace): 命令行参数对象

    Returns:
        dict: 可直接传给 `update_config` 的配置项
    """
    kwargs = {}
    if cli_args.tts_android_url:
        kwargs["url_base"] = cli_args.tts_android_url
    if cli_args.tts_android_engine:
        kwargs["engine"] = cli_args.tts_android_engine
    if cli_args.tts_android_rate is not None:
        kwargs["rate"] = cli_args.tts_android_rate
    if cli_args.tts_android_pitch is not None:
        kwargs["pitch"] = cli_args.tts_android_pitch
    return kwargs


__all__ = [
    "TTS_BACKEND_ANDROID",
    "create_active_tts_backend",
    "create_tts_backend",
    "get_active_tts_backend_name",
    "list_tts_backend_names",
    "set_active_tts_backend_name",
]
