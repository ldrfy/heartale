'错误缓存'
import json
import logging
import os
import platform
import subprocess

from gi.repository import Adw, Gio, Gtk  # type: ignore


class InMemoryLogHandler(logging.Handler):
    """创建一个内存中的日志处理器

    Args:
        logging (_type_): _description_
    """

    def __init__(self, max_logs=20):
        super().__init__()
        self.log_buffer = []
        self.max_logs = max_logs

    def emit(self, record):
        log_entry = self.format(record)
        if len(self.log_buffer) >= self.max_logs:
            # 如果日志超过最大限制，删除最旧的日志
            self.log_buffer.pop(0)
        self.log_buffer.append(log_entry)

    def get_logs(self):
        """获取日志

        Returns:
            str: _description_
        """
        return "\n\n".join(self.log_buffer)


# 初始化日志系统
logger = logging.getLogger("heartale")
logger.setLevel(logging.DEBUG)

# 设置格式
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s\n[%(filename)s:%(lineno)d]\n%(message)s')
# 使用自定义内存日志处理器
in_memory_handler = InMemoryLogHandler(max_logs=10)
in_memory_handler.setFormatter(formatter)
logger.addHandler(in_memory_handler)


def get_logger():
    """提供给外部的接口

    Returns:
        _type_: _description_
    """
    return logger


def get_log_handler():
    """获取当前的内存日志

    Returns:
        _type_: _description_
    """
    return in_memory_handler


def get_os_release():
    """版本信息

    Returns:
        _type_: _description_
    """
    try:
        with open("/etc/os-release", "r", encoding="utf8") as f:
            return f.read()
    except FileNotFoundError:
        return "OS release info not found"


def get_gtk_msg(version):
    """gtk调试信息

    Args:
        version (str): _description_

    Returns:
        _type_: _description_
    """
    s = f"Version: {version}"
    s += f"\nSystem: {platform.system()}"
    s += f"\nRelease: {platform.release()}"

    gvs = Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()
    s += f"\nGTK Version: {gvs[0]}.{gvs[1]}.{gvs[2]}"

    avs = Adw.get_major_version(), Adw.get_minor_version(), Adw.get_micro_version()
    s += f"\nAdwaita Version: {avs[0]}.{avs[1]}.{avs[2]}"

    s += "\n\n******* debug log *******\n"
    s += get_log_handler().get_logs()

    s += "\n\n******* other *******\n"
    s += get_os_release()
    return s
