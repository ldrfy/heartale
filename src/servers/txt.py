"""阅读本地txt文件"""
import hashlib
import os
import re
import shutil
from gettext import gettext as _
from pathlib import Path

from .. import PATH_CONFIG_BOOKS
from ..entity import LibraryDB
from ..entity.book import Book
from ..utils.debug import get_logger
from ..utils.i18n import is_english_language
from . import Server


class TxtServer(Server):
    """阅读app相关的webapi"""

    def __init__(self):
        """初始化应用API

        Args:
            conf (dict): 配置 conf["legado"]
        """
        self.chap_p2s = []
        super().__init__("txt")

    def initialize(self, book: Book):
        """异步初始化"""
        self.book = book

        self.chap_names, self.chap_p2s = self._get_chap_names()
        self.bd.update_chap_txts(
            self.load_chap_txt(self.book.chap_n),
            self.book.chap_txt_pos
        )

        return f"{self.book.name} {self.get_chap_name()}"

    def next(self):
        """下一步

        Returns:
            str: 需要转音频的文本
        """

        if self.bd.is_chap_end():
            self.book.chap_n += 1

            self.bd.update_chap_txts(self.load_chap_txt(self.book.chap_n))
            return self.get_chap_name()

        txt = self.bd.chap_txts[self.bd.chap_txt_n]

        # 一些异常
        if len(self.bd.chap_txts) > 1:
            super().save_read_progress(self.get_chap_n(), self.bd.get_chap_txt_pos())
        self.bd.chap_txt_n += 1

        return txt

    def get_chap_txt(self, chap_n=-1):
        """获取指定章节正文，并去掉开头重复的目录标题。

        Args:
            chap_n (int, optional): 章节索引. Defaults to -1.

        Returns:
            str: 章节正文
        """
        if chap_n < 0:
            return super().get_chap_txt(chap_n)

        with open(self.book.path, "r", encoding=self.book.encoding, errors="ignore") as f:
            if chap_n + 1 == len(self.chap_p2s):
                chap_txt = f.read()[self.chap_p2s[chap_n]:]
            else:
                chap_txt = f.read()[self.chap_p2s[chap_n]
                                  : self.chap_p2s[chap_n + 1]]

        return self._strip_leading_chap_name(chap_txt, chap_n)

    def _get_chap_names(self):
        """获取 txt 书籍的章节目录。

        Returns:
            tuple[list[str], list[int]]: 章节标题和对应偏移位置
        """
        if not os.path.isfile(self.book.path):
            raise FileNotFoundError(
                _("File not found: {path}").format(path=self.book.get_path()))

        with open(self.book.path, "r", encoding=self.book.encoding, errors="ignore") as f:
            text = f.read()
        rules = get_txt_parse_rules_for_book(self.book)
        return parse_chap_names_with_rules(text, rules)

    def _strip_leading_chap_name(self, chap_txt: str, chap_n: int) -> str:
        """去掉章节正文开头与目录重复的标题行。

        Args:
            chap_txt (str): 原始章节正文
            chap_n (int): 章节索引

        Returns:
            str: 去掉开头标题后的章节正文
        """
        lines = chap_txt.splitlines(keepends=True)
        if not lines:
            return chap_txt

        heading_candidates = self._get_heading_candidates(chap_n)
        if not heading_candidates:
            return chap_txt

        idx = 0
        removed = False
        max_scan_lines = min(len(lines), 4)
        while idx < max_scan_lines:
            line = lines[idx]
            if not line.strip():
                idx += 1
                continue
            if self._normalize_heading(line) not in heading_candidates:
                break
            removed = True
            idx += 1

        if not removed:
            return chap_txt

        stripped = "".join(lines[idx:]).lstrip("\ufeff")
        return stripped or chap_txt

    def _get_heading_candidates(self, chap_n: int) -> set[str]:
        """获取章节开头可能出现的标题文本集合。

        Args:
            chap_n (int): 章节索引

        Returns:
            set[str]: 可用于匹配开头标题的文本集合
        """
        chap_name = self.chap_names[chap_n].strip()
        candidates = {self._normalize_heading(chap_name)}

        for rule in TXT_PARSE_RULES:
            volume_match = re.search(rule["volume_pattern"], chap_name)
            if volume_match:
                candidates.add(self._normalize_heading(volume_match.group()))

            chapter_match = re.search(rule["chapter_pattern"], chap_name)
            if chapter_match:
                candidates.add(self._normalize_heading(chapter_match.group()))

        return {candidate for candidate in candidates if candidate}

    @staticmethod
    def _normalize_heading(text: str) -> str:
        """标准化标题文本，便于比较是否与目录重复。

        Args:
            text (str): 原始标题文本

        Returns:
            str: 归一化后的标题文本
        """
        return text.strip().lstrip("\ufeff")


TXT_PARSE_CONFIG_KEY = "txt_parse"
TXT_PARSE_RULES = [
    {
        "volume_pattern": r'第([一二三四五六七八九十\d]+)卷\s*(.*)',
        "chapter_pattern": r'第([一二三四五六七八九十百千\d]+)章\s*(.*)',
    },
    {
        "volume_pattern": r'[Vv]ol(?:ume)?\.?\s*([A-Za-z0-9IVXLC]+)\s*(.*)',
        "chapter_pattern": r'[Cc]h(?:apter)?\.?\s*([A-Za-z0-9IVXLC]+)\s*(.*)',
    },
]
TXT_PARSE_PRESETS = {
    "zh_CN": dict(TXT_PARSE_RULES[0]),
    "en_US": dict(TXT_PARSE_RULES[1]),
}
TXT_PARSE_DEFAULT_CONFIG = dict(TXT_PARSE_RULES[0])
TXT_PARSE_DEFAULT_CONFIG_EN = dict(TXT_PARSE_RULES[1])


def validate_book_txt_parse_overrides(
    volume_pattern: str | None,
    chapter_pattern: str | None,
) -> tuple[str, str]:
    """校验并规范化单本书的 txt 解析规则覆盖字段。

    Args:
        volume_pattern (str | None): 卷标题正则（空表示不覆盖）
        chapter_pattern (str | None): 章节标题正则（空表示不覆盖）

    Returns:
        tuple[str, str]: 校验后的 (volume_pattern, chapter_pattern)，未覆盖项返回空字符串
    """
    global_cfg = get_txt_parse_config()

    volume_pattern = (volume_pattern or "").strip()
    chapter_pattern = (chapter_pattern or "").strip()

    if volume_pattern:
        volume_pattern = _validate_regex_config(
            volume_pattern,
            global_cfg["volume_pattern"],
            "volume_pattern",
        )
    if chapter_pattern:
        chapter_pattern = _validate_regex_config(
            chapter_pattern,
            global_cfg["chapter_pattern"],
            "chapter_pattern",
        )

    return volume_pattern, chapter_pattern


def get_txt_parse_config() -> dict:
    """读取 txt 章节解析配置。

    Returns:
        dict: txt 章节解析配置
    """
    default_config = get_txt_parse_default_config()
    db = LibraryDB()
    cfg = db.get_config(TXT_PARSE_CONFIG_KEY, default_config)
    db.close()

    merged = dict(default_config)
    if isinstance(cfg, dict):
        merged.update(cfg)
    return merged


def get_txt_parse_default_config() -> dict:
    """获取当前界面语言对应的默认 txt 解析配置。

    Returns:
        dict: 默认 txt 解析配置
    """
    if is_english_language():
        return dict(TXT_PARSE_DEFAULT_CONFIG_EN)
    return dict(TXT_PARSE_DEFAULT_CONFIG)


def get_txt_parse_rules() -> list[dict[str, str]]:
    """读取并校验 txt 章节解析规则列表。

    Returns:
        list[dict[str, str]]: 章节解析规则列表
    """
    cfg = get_txt_parse_config()
    default_config = get_txt_parse_default_config()
    primary_rule = {
        "volume_pattern": _validate_regex_config(
            cfg.get("volume_pattern"),
            default_config["volume_pattern"],
            "volume_pattern",
        ),
        "chapter_pattern": _validate_regex_config(
            cfg.get("chapter_pattern"),
            default_config["chapter_pattern"],
            "chapter_pattern",
        ),
    }
    return [primary_rule, *TXT_PARSE_RULES]


def get_txt_parse_rules_for_book(book: Book) -> list[dict[str, str]]:
    """获取单本书的 txt 章节解析规则列表（支持回退到全局配置）。

    规则优先级：
    1) 书籍自定义规则（若设置）
    2) 全局规则
    3) 内置兜底规则（中英）

    Args:
        book (Book): 书籍对象

    Returns:
        list[dict[str, str]]: 章节解析规则列表
    """
    global_rules = get_txt_parse_rules()
    has_overrides = bool(
        str(getattr(book, "txt_volume_pattern", "")).strip()
        or str(getattr(book, "txt_chapter_pattern", "")).strip()
    )
    if not has_overrides:
        return global_rules

    global_primary = global_rules[0]
    book_primary = {
        "volume_pattern": _validate_regex_config(
            getattr(book, "txt_volume_pattern", ""),
            global_primary["volume_pattern"],
            "volume_pattern",
        ),
        "chapter_pattern": _validate_regex_config(
            getattr(book, "txt_chapter_pattern", ""),
            global_primary["chapter_pattern"],
            "chapter_pattern",
        ),
    }
    return [book_primary, *global_rules]


def set_txt_parse_config(**kwargs) -> dict:
    """保存 txt 章节解析配置。

    Args:
        **kwargs: 需要更新的正则配置

    Returns:
        dict: 保存后的 txt 章节解析配置
    """
    cfg = get_txt_parse_config()
    for key, default in get_txt_parse_default_config().items():
        if key in kwargs and kwargs[key] is not None:
            cfg[key] = _validate_regex_config(
                kwargs[key],
                default,
                key,
            )

    db = LibraryDB()
    db.set_config(TXT_PARSE_CONFIG_KEY, cfg)
    db.close()
    return cfg


def reset_txt_parse_config() -> dict:
    """恢复 txt 章节解析默认配置。

    Returns:
        dict: 默认 txt 章节解析配置
    """
    return set_txt_parse_config(**get_txt_parse_default_config())


def _validate_regex_config(value: str, default: str, field_name: str) -> str:
    """校验章节解析正则配置。

    Args:
        value (str): 待校验的正则文本
        default (str): 默认正则文本
        field_name (str): 配置字段名

    Returns:
        str: 合法的正则文本
    """
    pattern = str(value or default).strip()
    if not pattern:
        raise ValueError(
            _("{field} can not be empty").format(field=field_name))
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(
            _("Invalid regular expression for {field}: {error}").format(
                field=field_name,
                error=exc,
            )
        ) from exc
    return pattern


def parse_chap_names(
    file_content: str,
    volume_pattern: str | None = None,
    chapter_pattern: str | None = None,
):
    """解析 txt 书籍的章节目录。

    Args:
        file_content (str): txt 全文内容
        volume_pattern (str | None, optional): 主卷标题正则. Defaults to None.
        chapter_pattern (str | None, optional): 主章节标题正则. Defaults to None.

    Returns:
        tuple[list[str], list[int]]: 章节标题和对应偏移位置
    """
    primary_rule = _build_parse_rule(volume_pattern, chapter_pattern)
    return parse_chap_names_with_rules(
        file_content,
        [primary_rule, *get_txt_parse_rules()[1:]],
    )


def parse_chap_names_with_rules(
    file_content: str,
    rules: list[dict[str, str]],
) -> tuple[list[str], list[int]]:
    """使用给定规则列表解析 txt 书籍章节目录。

    Args:
        file_content (str): txt 全文内容
        rules (list[dict[str, str]]): 章节解析规则列表（按优先级顺序）

    Returns:
        tuple[list[str], list[int]]: 章节标题和对应偏移位置
    """
    expanded_rules = _expand_parse_rules_for_match(rules)
    for rule in expanded_rules:
        chap_names, chap_ps = _parse_chap_names_once(
            file_content,
            rule["volume_pattern"],
            rule["chapter_pattern"],
        )
        if chap_names:
            return chap_names, chap_ps
    return [], []


def _parse_chap_names_once(
    file_content: str,
    volume_pattern: str,
    chapter_pattern: str,
) -> tuple[list[str], list[int]]:
    """使用一组正则解析一次章节目录。

    Args:
        file_content (str): txt 全文内容
        volume_pattern (str): 卷标题正则
        chapter_pattern (str): 章节标题正则

    Returns:
        tuple[list[str], list[int]]: 章节标题和对应偏移位置
    """
    current_volume = None
    chap_names = []
    chap_ps = []

    words = 0
    for line in file_content.split("\n"):
        volume_match = re.search(volume_pattern, line)
        if volume_match:
            current_volume = volume_match.group()
            words += len(line + "\n")
            continue

        chapter_match = re.search(chapter_pattern, line)
        if chapter_match:
            current_chapter = chapter_match.group()
            if current_volume:
                chap_names.append(f"{current_volume} {current_chapter}")
                current_volume = None
            else:
                chap_names.append(current_chapter)
            chap_ps.append(words)
        words += len(line + "\n")

    return chap_names, chap_ps


def _build_parse_rule(
    volume_pattern: str | None,
    chapter_pattern: str | None,
) -> dict[str, str]:
    """构造并校验一条章节解析规则。

    Args:
        volume_pattern (str | None): 卷标题正则
        chapter_pattern (str | None): 章节标题正则

    Returns:
        dict[str, str]: 校验后的章节解析规则
    """
    default_config = get_txt_parse_default_config()
    return {
        "volume_pattern": _validate_regex_config(
            volume_pattern,
            default_config["volume_pattern"],
            "volume_pattern",
        ),
        "chapter_pattern": _validate_regex_config(
            chapter_pattern,
            default_config["chapter_pattern"],
            "chapter_pattern",
        ),
    }


def _expand_parse_rules_for_match(
    rules: list[dict[str, str]],
) -> list[dict[str, str]]:
    """扩展章节解析规则列表，自动补充带 ^ 的重试版本。

    Args:
        rules (list[dict[str, str]]): 基础章节解析规则列表

    Returns:
        list[dict[str, str]]: 实际用于匹配的章节解析规则列表
    """
    expanded_rules = []
    seen = set()
    for rule in rules:
        candidates = [rule, _with_line_start_anchor(rule)]
        for candidate in candidates:
            key = (
                candidate["volume_pattern"],
                candidate["chapter_pattern"],
            )
            if key in seen:
                continue
            seen.add(key)
            expanded_rules.append(candidate)
    return expanded_rules


def _with_line_start_anchor(rule: dict[str, str]) -> dict[str, str]:
    """为章节解析规则补充行首锚点。

    Args:
        rule (dict[str, str]): 原始章节解析规则

    Returns:
        dict[str, str]: 补充了行首锚点的章节解析规则
    """
    return {
        "volume_pattern": _ensure_line_start_anchor(rule["volume_pattern"]),
        "chapter_pattern": _ensure_line_start_anchor(rule["chapter_pattern"]),
    }


def _ensure_line_start_anchor(pattern: str) -> str:
    """确保正则以行首锚点开头。

    Args:
        pattern (str): 原始正则

    Returns:
        str: 带行首锚点的正则
    """
    stripped = pattern.lstrip()
    if stripped.startswith("^"):
        return pattern
    return f"^{pattern}"


def cal_md5(path: Path, chunk_size: int = 8192) -> str:
    """计算md5

    Args:
        path (Path): _description_
        chunk_size (int, optional): _description_. Defaults to 8192.

    Returns:
        str: _description_
    """
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_encoding(path: Path, sample_size: int = 65536) -> str:
    """探测编码

    Args:
        path (Path): _description_
        sample_size (int, optional): _description_. Defaults to 65536.

    Raises:
        ValueError: _description_

    Returns:
        str: _description_
    """
    print(f"Detected file encoding: {path}")
    encodings = ["gbk", "gb2312", "utf-8-sig", "utf-8"]
    raw = path.open("rb").read(sample_size)
    for enc in encodings:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError as e:
            get_logger().error("尝试用 %s 解码失败: %s", enc, e)

            continue
    return "utf-8"
    # raise ValueError(f"Unable to recognize file encoding: {path}")


def path2book(src: str, cfg_dir: Path = PATH_CONFIG_BOOKS) -> Book:
    """根据路径初始化

    Args:
        src (str): _description_
        cfg_dir (Path, optional): _description_. Defaults to None.

    Returns:
        Book: _description_
    """
    src_path = Path(src)
    if not src_path.is_file():
        raise FileNotFoundError(f"File not found: {src}")
    if src_path.suffix.lower() not in [".txt"]:
        raise ValueError(_("Unsupported file type: {suffix}")
                         .format(suffix=src_path.suffix))
    enc = detect_encoding(src_path)

    with open(src, "r", encoding=enc, errors="ignore") as file:
        f_txt = file.read()

    chap_names, _chap_ps = parse_chap_names(f_txt, **get_txt_parse_rules()[0])
    chap_all = len(chap_names)

    dest = cfg_dir / src_path.name
    shutil.copy(src_path, dest)

    if chap_all == 0:
        raise ValueError(
            _("No chapters detected. Please check the parsing rules in Preferences."))

    return Book(str(dest), dest.stem, "", 0, chap_names[0],
                chap_all, 0, 0, len(f_txt), enc, cal_md5(dest))
