"""阅读界面"""
import json
from pathlib import Path

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity import Book, LibraryDB

PROGRESS_FILE = Path.home() / ".config" / "heartale" / "progress.json"


@Gtk.Template(resource_path="/cool/ldr/heartale/page_reader.ui")
class ReaderPage(Adw.NavigationPage):
    """_summary_

    Args:
        Adw (_type_): _description_

    Returns:
        _type_: _description_
    """
    __gtype_name__ = "ReaderPage"

    nav_list: Gtk.ListBox = Gtk.Template.Child("nav_list")
    text_view: Gtk.TextView = Gtk.Template.Child("text_view")
    scroll_content: Gtk.ScrolledWindow = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, book: Book, **kwargs):
        super().__init__(**kwargs)
        self._nav = nav
        self._book = book
        self._buffer = Gtk.TextBuffer()
        self.text_view.set_buffer(self._buffer)
        self._chapter_marks: list[Gtk.TextMark] = []
        self._in_scroll_sync = False  # 防抖标记，避免循环触发
        self._load_or_init_progress_store()
        self._build_document()  # 构造章节与 mark
        self._build_nav_buttons()  # 左侧按钮
        self._connect_scroll_sync()  # 滚动同步
        self._restore_progress_async()  # 恢复上次进度（滚到哪就到哪）

    # ---------- 文档/章节构建（示例：按简单章节数组；实际可由解析器生成） ----------
    def _build_document(self):
        buf = self._buffer
        buf.set_text("")  # 清空
        # 示例章节：可替换为实际解析结果（比如从 EPUB 目录、PDF 目录、或自建章节列表）
        chapters = self._fake_chapters_from_book(self._book)
        self._chapters = chapters
        iter_ = buf.get_end_iter()
        self._chapter_marks.clear()

        for idx, ch in enumerate(chapters):
            # 标题（加粗/更大字号可用 TextTag，这里用简单文本）
            buf.insert(iter_, f"{ch['title']}\n", -1)
            # 在标题位置放一个 Mark
            mark = buf.create_mark(f"ch{idx}", iter_, left_gravity=True)
            self._chapter_marks.append(mark)
            # 正文
            buf.insert(iter_, ch["body"] + "\n\n", -1)

    def _fake_chapters_from_book(self, book: Book):
        # 仅示例：实际应替换为真实内容（读取文件/解析）
        chapters = []
        for i in range(1, 11):
            chapters.append({
                "title": f"{book.name} - 第 {i} 章",
                "body": "这里是正文示例。" * 80  # 占位长文本
            })
        return chapters

    def _build_nav_buttons(self):
        """_summary_
        """
        child = self.nav_list.get_first_child()
        while child:
            self.nav_list.remove(child)
            child = self.nav_list.get_first_child()
        # 填充
        for ch in self._chapters:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=ch["title"], halign=Gtk.Align.FILL)
            btn.set_hexpand(True)
            # 点击按钮 -> 激活该行（触发 row-activated，统一走一套逻辑）
            btn.connect("clicked", lambda _b, r=row: r.activate())
            row.set_child(btn)
            self.nav_list.append(row)
        self.nav_list.show()

    @Gtk.Template.Callback()
    def on_nav_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow):
        """_summary_

        Args:
            _listbox (Gtk.ListBox): _description_
            row (Gtk.ListBoxRow): _description_
        """
        idx = row.get_index()
        if 0 <= idx < len(self._chapter_marks):
            mark = self._chapter_marks[idx]
            # 滚动到目标章节（居上）
            self._in_scroll_sync = True
            self.text_view.scroll_to_mark(
                mark, 0.0, use_align=True, xalign=0.0, yalign=0.0)
            # 稍后清除防抖标记
            GLib.idle_add(self._clear_sync_flag)
            # 同步选择高亮
            self._select_nav_row(idx)
            # 保存进度（以章节索引为主）
            self._save_progress(
                {"chapter": idx, "offset": self._get_buffer_offset_at_visible_top()})

    def _clear_sync_flag(self):
        self._in_scroll_sync = False
        return False

    def _select_nav_row(self, idx: int):
        row = self.nav_list.get_row_at_index(idx)
        if row:
            self.nav_list.select_row(row)
            # 让选中行可见
            adj = self.nav_list.get_adjustment()
            if adj:
                # 简单确保选中行滚入视口
                row_y = row.get_allocation().y
                if row_y < adj.get_value() or row_y > adj.get_value() + adj.get_page_size() - row.get_allocation().height:
                    adj.set_value(max(0, row_y))

    # ---------- 滚动同步：正文滚动 -> 高亮对应按钮 ----------
    def _connect_scroll_sync(self):
        vadj = self.scroll_content.get_vadjustment()
        if vadj:
            vadj.connect("value-changed", self._on_scroll_value_changed)

    def _on_scroll_value_changed(self, _adj: Gtk.Adjustment):
        if self._in_scroll_sync:
            return
        # 当前可视顶部对应的 buffer 偏移
        offset = self._get_buffer_offset_at_visible_top()
        # 找到不大于该 offset 的最后一个章节 mark
        idx = self._chapter_index_for_offset(offset)
        if idx is not None:
            self._select_nav_row(idx)
            self._save_progress({"chapter": idx, "offset": offset})

    def _get_buffer_offset_at_visible_top(self) -> int:
        # 从 TextView 的可视矩形左上角，取对应 TextIter 的偏移
        rect = self.text_view.get_visible_rect()
        # 将视口坐标转为文本坐标
        # 这里用 (rect.x, rect.y) 近似“顶部行”
        it = self.text_view.get_iter_at_location(rect.x + 1, rect.y + 1)[1]
        return it.get_offset()

    def _chapter_index_for_offset(self, offset: int) -> int | None:
        buf = self._buffer
        # 预先把每个 Mark 的 offset 算出来
        mark_offsets = []
        for mk in self._chapter_marks:
            it = buf.get_iter_at_mark(mk)
            mark_offsets.append(it.get_offset())
        # 线性扫描足够快（章节数通常不大），可改成二分
        idx = 0
        for i, mo in enumerate(mark_offsets):
            if mo <= offset:
                idx = i
            else:
                break
        return idx

    # ---------- 进度持久化（每本书独立 key） ----------
    def _load_or_init_progress_store(self):
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._progress = json.loads(PROGRESS_FILE.read_text("utf-8"))
        except Exception:
            self._progress = {}

    def _save_progress(self, data: dict):
        key = self._progress_key()
        self._progress[key] = data
        tmp = PROGRESS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(
            self._progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(PROGRESS_FILE)

    def _restore_progress_async(self):
        # 等 UI 完成布局后再滚动
        def _do():
            key = self._progress_key()
            prog = self._progress.get(key)
            if not prog:
                # 默认滚到顶部并高亮第 0 章
                self._select_nav_row(0)
                return False
            ch = int(prog.get("chapter", 0))
            ch = max(0, min(ch, len(self._chapter_marks) - 1))
            self._select_nav_row(ch)
            # 优先章节 mark，其次 offset
            mark = self._chapter_marks[ch]
            self._in_scroll_sync = True
            self.text_view.scroll_to_mark(mark, 0.0, True, 0.0, 0.0)
            GLib.idle_add(self._clear_sync_flag)
            return False

        GLib.idle_add(_do)

    def _progress_key(self) -> str:
        # 以路径为主键；也可改为 (路径+文件指纹)
        return self._book.md5
