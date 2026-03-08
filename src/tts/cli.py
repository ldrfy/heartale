"""命令行场景下的 TTS 配置辅助函数。"""

import argparse

from . import THS


def build_tts_override_kwargs(cli_args: argparse.Namespace) -> dict:
    """从命令行参数中提取 TTS 覆盖配置。

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


def apply_tts_overrides(tts: THS, cli_args: argparse.Namespace) -> None:
    """将命令行中的 TTS 覆盖项写入实例配置。

    Args:
        tts (THS): TTS 实例
        cli_args (argparse.Namespace): 命令行参数对象
    """
    kwargs = build_tts_override_kwargs(cli_args)
    if kwargs:
        tts.update_config(**kwargs)
