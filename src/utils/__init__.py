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
    elif size_bytes < 1024 * 1024:
        size_kb = size_bytes / 1024
        return f"{size_kb:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.2f} MB"
    else:
        size_gb = size_bytes / (1024 * 1024 * 1024)
        return f"{size_gb:.2f} GB"


def get_time(timestamp: int) -> str:
    """时间戳转字符串

    Args:
        timestamp (int): _description_

    Returns:
        str: _description_
    """
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
