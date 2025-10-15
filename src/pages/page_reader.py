"""阅读"""

from gi.repository import Adw, GLib, Gtk  # type: ignore

from ..entity import Book, LibraryDB


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
    scroll_chap_name: Gtk.ScrolledWindow = Gtk.Template.Child()

    def __init__(self, nav: Adw.NavigationView, book: Book, chap_names, chaps_ps, ** kwargs):
        super().__init__(**kwargs)
        self._nav = nav
        self.book = book

        self._buffer = Gtk.TextBuffer()
        self.text_view.set_buffer(self._buffer)

        # 滚动触发控制
        self._auto_turning = False
        self._armed_bottom = True
        self._armed_top = True

        self.chap_names = chap_names
        self.chaps_ps = chaps_ps
        self._build_document()
        self._build_nav_buttons()

    # -------- 工具：夹取，并带安全边距 ----------

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return lo if v < lo else (hi if v > hi else v)

    def _safe_set_value(self, adj: Gtk.Adjustment, value: float, margin: float = 0.0):
        # 将 value 限制在 [lower, upper - page_size] 内，并留一点边距
        lo = adj.get_lower()
        hi = adj.get_upper() - adj.get_page_size()
        value = self._clamp(value, lo, hi)
        if margin > 0:
            # 若在底部区，往上抬一点；在顶部区，往下压一点
            if abs(value - hi) < 1e-3:
                value = self._clamp(value - margin, lo, hi)
            elif abs(value - lo) < 1e-3:
                value = self._clamp(value + margin, lo, hi)
        adj.set_value(value)

    # ---------- 小工具：按索引取章节 ----------
    def _get_chap_content_by_idx(self, n: int) -> str:
        with open(self.book.path, "r", encoding=self.book.encoding) as f:
            if n + 1 == len(self.chaps_ps):
                return f.read()[self.chaps_ps[n]:]

            return f.read()[self.chaps_ps[n]: self.chaps_ps[n + 1]]

    def _get_chap_content(self) -> str:
        return self._get_chap_content_by_idx(self.book.chap_n)

    # ---------- 构建：首次只放当前章 ----------
    def _build_document(self):
        self._buffer.set_text(self._get_chap_content())

        def _scroll_top():
            vadj = self.scroll_content.get_vadjustment()
            self._safe_set_value(vadj, vadj.get_lower(), margin=16.0)
            return False

        GLib.idle_add(_scroll_top)
        db = LibraryDB()
        db.save_book(self.book)
        db.close()

    def _build_nav_buttons(self):
        """_summary_
        """
        child = self.nav_list.get_first_child()
        while child:
            self.nav_list.remove(child)
            child = self.nav_list.get_first_child()
        # 填充
        for cn in self.chap_names:
            row = Gtk.ListBoxRow()
            btn = Gtk.Button(label=cn, halign=Gtk.Align.FILL)
            btn.set_halign(Gtk.Align.START)  # 靠左对齐
            btn.set_hexpand(True)
            # 点击按钮 -> 激活该行（触发 row-activated，统一走一套逻辑）
            btn.connect("clicked", lambda _b, r=row: r.activate())
            row.set_child(btn)
            self.nav_list.append(row)
        self.nav_list.show()
        row = self.nav_list.get_row_at_index(self.book.chap_n)
        if row:
            self.nav_list.select_row(row)

            def _focus_after_layout():
                row.grab_focus()          # 聚焦行 -> 父 scrolledwindow 自动滚动
                return False
            GLib.idle_add(_focus_after_layout)

    @Gtk.Template.Callback()
    def on_nav_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow):
        """_summary_

        Args:
            _listbox (Gtk.ListBox): _description_
            row (Gtk.ListBoxRow): _description_
        """
        idx = row.get_index()
        self.book.chap_n = idx
        self._build_document()

    @Gtk.Template.Callback()
    def on_reader_vadj_value_changed(self, adj: Gtk.Adjustment):
        """_summar监听滚动：底部追加下一章 / 顶部前插上一章y_

        Args:
            adj (Gtk.Adjustment): _description_
        """
        if self._auto_turning:
            return
        eps = 1.0
        value = adj.get_value()
        page = adj.get_page_size()
        lower = adj.get_lower()
        upper = adj.get_upper()

        at_bottom = value + page >= upper - eps
        at_top = value <= lower + eps

        # 只有“布防”为 True 时才触发；触发后立即“撤防”
        if at_bottom and self._armed_bottom:
            self._armed_bottom = False
            self._auto_turning = True
            GLib.idle_add(self._append_next_chapter)
        elif at_top and self._armed_top:
            self._armed_top = False
            self._auto_turning = True
            GLib.idle_add(self._prepend_prev_chapter)

        # 当离开触发区后再“布防”，避免惯性重复触发
        if not at_bottom:
            self._armed_bottom = True
        if not at_top:
            self._armed_top = True

    # ---------- 核心：在末尾“加载下一章”，保持贴底但留安全边距 ----------

    def _append_next_chapter(self):
        next_idx = self.book.chap_n + 1
        if next_idx >= len(self.chap_names):
            self._auto_turning = False
            return False

        vadj = self.scroll_content.get_vadjustment()
        prev_upper = vadj.get_upper()
        prev_value = vadj.get_value()
        prev_pagesize = vadj.get_page_size()
        at_bottom_before = prev_value + prev_pagesize >= prev_upper - 1.0

        # 可选分隔行
        end_iter = self._buffer.get_end_iter()
        self._buffer.insert(end_iter, "\n")

        # 追加正文
        text = self._get_chap_content_by_idx(next_idx)
        self._buffer.insert(self._buffer.get_end_iter(), text)

        # 更新章节与目录
        self.book.chap_n = next_idx
        row = self.nav_list.get_row_at_index(self.book.chap_n)
        if row:
            self.nav_list.select_row(row)

        # 关键：若追加前处在底部，把视图定位到“旧底部=衔接处”，而不是新底部
        def _stick_to_seam_or_keep():
            new_upper = vadj.get_upper()
            if at_bottom_before:
                # seam 就是追加前的底部行：prev_upper - prev_pagesize
                seam_offset = 16.0  # 让衔接处露出一点点，便于感知
                target = (prev_upper - prev_pagesize) + seam_offset
                # 夹取，避免再次落入底部触发区
                self._safe_set_value(vadj, target, margin=16.0)
            else:
                # 若不是贴底阅读，仍按相对位移补偿
                delta = new_upper - prev_upper
                self._safe_set_value(vadj, prev_value + delta, margin=0.0)
            return False

        GLib.idle_add(_stick_to_seam_or_keep)
        self._auto_turning = False
        return False

    # ---------- 核心：在开头“加载上一章”，保持可视位置并留安全边距 ----------

    def _prepend_prev_chapter(self):
        prev_idx = self.book.chap_n - 1
        if prev_idx < 0:
            self._auto_turning = False
            return False

        vadj = self.scroll_content.get_vadjustment()
        prev_upper = vadj.get_upper()
        prev_value = vadj.get_value()

        # 插入上一章正文（以及可选分隔）
        start_iter = self._buffer.get_start_iter()
        text = self._get_chap_content_by_idx(prev_idx)
        insert_text = text + "\n"
        self._buffer.insert(start_iter, insert_text)

        # 夹取 + 边距，防止再次进入顶部触发区
        def _keep_view():
            delta = vadj.get_upper() - prev_upper
            target = prev_value + delta
            self._safe_set_value(vadj, target, margin=24.0)  # 顶部留 24px
            return False

        GLib.idle_add(_keep_view)

        # 更新章节与目录
        self.book.chap_n = prev_idx
        row = self.nav_list.get_row_at_index(self.book.chap_n)
        if row:
            self.nav_list.select_row(row)

        self._auto_turning = False
        return False
