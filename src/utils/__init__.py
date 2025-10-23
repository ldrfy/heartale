"""工具"""
import os
from datetime import datetime

from gi.repository import Gio, Gtk  # type: ignore

PACKAGE_URL = "https://github.com/ldrfy/heartale"


def open_url(url: str):
    """打开链接

    Args:
        url (str): _description_
    """
    launcher = Gtk.UriLauncher.new(url)
    launcher.launch(None, None, None)


def open_folder(folder_path: str):
    """打开文件夹

    Args:
        folder_path (str): _description_
    """
    if os.path.isfile(folder_path):
        folder_path = os.path.dirname(folder_path)
    uri = f"file://{folder_path}"
    print(f"打开文件夹：{uri}")
    Gio.AppInfo.launch_default_for_uri(uri, None)


def get_file_size(path: str) -> int:
    """获取文件大小，单位字节

    Args:
        path (str): _description_

    Returns:
        int: _description_
    """

    size_bytes = 0
    try:
        size_bytes = os.path.getsize(path)
    except Exception as e:  # pylint: disable=broad-except
        print(f"无法获取文件大小：{path}: {e}")

    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        size_kb = size_bytes / 1024
        return f"{size_kb:.2f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.2f} MB"

    size_gb = size_bytes / (1024 * 1024 * 1024)
    return f"{size_gb:.2f} GB"


def sec2str(sec: int) -> str:
    """将秒转换为可读时间字符串

    Args:
        sec (int): 时间长度，单位秒

    Returns:
        str: 可读时间，如 "45s", "3'15''", "2h5'", "1d2h", "3w2d"
    """
    constant_minute = 60
    constant_hour = 60 * constant_minute
    constant_day = 24 * constant_hour
    constant_week = 7 * constant_day
    constant_month = 30 * constant_day
    constant_year = 365 * constant_day

    sec = int(sec)

    if sec < constant_minute:
        return f"{sec}s"
    if sec < constant_hour:
        minutes = sec // constant_minute
        seconds = sec % constant_minute
        return f"{minutes}'{seconds}''"
    if sec < constant_day:
        hours = sec // constant_hour
        minutes = (sec % constant_hour) // constant_minute
        return f"{hours}h{minutes}'"
    if sec < constant_week:
        days = sec // constant_day
        hours = (sec % constant_day) // constant_hour
        return f"{days}d{hours}h"
    if sec < constant_month:
        weeks = sec // constant_week
        days = (sec % constant_week) // constant_day
        return f"{weeks}w{days}d"
    if sec < constant_year:
        months = sec // constant_month
        days = (sec % constant_month) // constant_day
        return f"{months}m{days}d"

    years = sec // constant_year
    days = (sec % constant_year) // constant_day
    return f"{years}y{days}d"


def get_time(timestamp: int) -> str:
    """时间戳转字符串

    Args:
        timestamp (int): _description_

    Returns:
        str: _description_
    """
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
