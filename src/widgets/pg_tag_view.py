"""段落控制器"""
import gi
from gi.repository import GLib, Gtk, Pango  # type: ignore

gi.require_version("Gtk", "4.0")


# =========================
# 段落控制器：段落索引/滚动/点击着色/可视段监听/样式可调
# =========================
class ParagraphTagController:
    """
    给现有 GtkTextView 附加“段落感知 + 点击命中 + 滚动定位 + 可视段监听 + 样式可调”能力。
    不改动 TextView/ScrolledWindow 结构，与你原来的滚动代码兼容。
    """

    def __init__(self, textview: Gtk.TextView, scroller: Gtk.ScrolledWindow):
        self.view = textview
        self.buf = textview.get_buffer()
        self.scroller = scroller

        # 段落 [start_off, end_off) 区间
        self._paragraph_ranges = []
        # 段落 tag 命名 para_{i}
        self._tag_prefix = "para_"

        # 点击着色 tag（仅前景色，可外部改样式）
        self._active_tag = self.buf.create_tag(
            "active_para",
            foreground="#d9480f",                  # 默认橙色前景
            weight=Pango.Weight.BOLD               # 默认加粗，可通过 set_active_style 调整
            # 也可用：foreground-rgba=Gdk.RGBA(0.85, 0.28, 0.06, 1.0)
        )
        self._active_idx = None

        # 全局布局 tag：行间距/段间距
        self._layout_tag = self.buf.create_tag("layout_tag")
        self._apply_layout_tag_full()

        # 点击后用插入光标位置命中段
        click = Gtk.GestureClick()
        click.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        click.connect("released", self._on_released)
        self.view.add_controller(click)

        # 外部回调
        self._on_click_cb = None
        self._on_visible_idx_changed = None

        # 滚动监听：上报“当前可视段”，不自动改着色
        self._last_visible_idx = None
        vadj = self.scroller.get_vadjustment()
        vadj.connect("value-changed", self._on_scroll_value_changed)

        # 首帧 idle 触发一次检测，等控件完成首次布局后再计算
        GLib.idle_add(self._emit_visible_idx_once, priority=GLib.PRIORITY_LOW)

        # 字体大小通过 CSS Provider 控制
        self._css_provider = Gtk.CssProvider()
        self._font_pt = 14
        self._apply_font_size(self._font_pt)

    # ---------- 公共 API ----------
    def set_on_paragraph_click(self, callback):
        """
        设置段落点击回调。
        签名：callback(idx:int, tag_name:str, start_off:int, end_off:int)。
        """
        self._on_click_cb = callback

    def set_on_visible_paragraph_changed(self, callback):
        """
        设置“当前可视段变化”回调。
        签名：callback(idx:int)。
        """
        self._on_visible_idx_changed = callback

    def clear(self):
        """
        清空内容与段落索引。
        不影响外部对 TextView 的既有用法。
        """
        self.buf.set_text("")
        self._paragraph_ranges.clear()
        self._active_idx = None
        self._apply_layout_tag_full()
        self._queue_emit_visible_idx()

    def set_paragraphs(self, paragraphs):
        """
        整体设置段落列表（list[str]）。
        自动创建 para_{i} 标签并记录范围。
        """
        self.clear()
        for i, text in enumerate(paragraphs):
            self._append_paragraph(i, text)
        self._queue_emit_visible_idx()

    def append_paragraph(self, text) -> int:
        """
        追加段落并返回其索引。
        """
        idx = len(self._paragraph_ranges)
        self._append_paragraph(idx, text)
        self._queue_emit_visible_idx()
        return idx

    def get_paragraph_count(self) -> int:
        """_summary_

        Returns:
            int: _description_
        """
        return len(self._paragraph_ranges)

    def get_paragraph_range(self, idx):
        """
        返回 (start_offset, end_offset)。
        越界返回 None。
        """
        if 0 <= idx < len(self._paragraph_ranges):
            return self._paragraph_ranges[idx]
        return None

    def get_paragraph_tag_name(self, idx) -> str:
        """
        返回 para_{idx}。
        """
        return f"{self._tag_prefix}{idx}"

    # ---- 滚动兼容接口：与你的旧逻辑一致 ----
    def scroll_to_paragraph(self, idx: int, center: bool = False):
        """
        滚到段首。
        内部用 TextView.scroll_to_iter，与旧代码一致。
        """
        rng = self.get_paragraph_range(idx)
        if not rng:
            return
        s_off, _ = rng
        it = self.buf.get_iter_at_offset(s_off)
        self._scroll_to_iter_safe(it, center=center)

    def scroll_to_offset(self, off: int, center: bool = False):
        """
        滚动到任意 offset。
        """
        off = max(0, min(off, self.buf.get_char_count()))
        it = self.buf.get_iter_at_offset(off)
        self._scroll_to_iter_safe(it, center=center)

    def scroll_to_tag_name(self, tag_name: str, center: bool = False):
        """
        滚到某个段落 tag 的起点。
        若 tag 覆盖多个区间，这里取首个。
        """
        tag = self.buf.get_tag_table().lookup(tag_name)
        if not tag:
            return
        start = self.buf.get_start_iter()
        while True:
            match = start.forward_to_tag_toggle(tag)
            if not match:
                break
            if match.begins_tag(tag):
                it = match.copy()
                self._scroll_to_iter_safe(it, center=center)
                return

    def highlight_paragraph(self, idx: int, ensure_visible: bool = False):
        """
        文字彩色着色某段（不再使用背景高亮）。
        着色仅在点击/调用时变化。
        滚动不会自动改变着色。
        """
        rng = self.get_paragraph_range(idx)
        if not rng:
            return
        self.buf.remove_tag(
            self._active_tag, self.buf.get_start_iter(), self.buf.get_end_iter()
        )
        s_off, e_off = rng
        self.buf.apply_tag(
            self._active_tag,
            self.buf.get_iter_at_offset(s_off),
            self.buf.get_iter_at_offset(e_off),
        )
        self._active_idx = idx
        if ensure_visible:
            self.scroll_to_paragraph(idx)

    # ---------- 样式相关（随时可调） ----------
    def set_font_size_pt(self, pt: int):
        """
        设置 TextView 字体大小（pt）。
        """
        pt = max(6, min(72, int(pt)))
        if pt == self._font_pt:
            return
        self._font_pt = pt
        self._apply_font_size(pt)
        self._queue_emit_visible_idx()

    def set_line_spacing(self, pixels_inside_wrap: int):
        """
        设置行间距（像素）。
        建议范围 0~30。
        """
        piw = max(0, min(60, int(pixels_inside_wrap)))
        self._layout_tag.props.pixels_inside_wrap = piw
        self._reapply_layout_tag()
        self._queue_emit_visible_idx()

    def set_paragraph_spacing(self, above_px: int, below_px: int):
        """
        设置段前/段后间距（像素）。
        建议范围 0~40。
        """
        a = max(0, min(80, int(above_px)))
        b = max(0, min(80, int(below_px)))
        self._layout_tag.props.pixels_above_lines = a
        self._layout_tag.props.pixels_below_lines = b
        self._reapply_layout_tag()
        self._queue_emit_visible_idx()

    def set_active_style(self, hex_color: str | None = None, bold: bool | None = None, underline: bool | None = None):
        """
        动态调整“活动段落”的文字样式（仅前景相关）。
        hex_color 例子: "#d9480f" 或 "#7c3aed"。
        """
        if hex_color:
            # 使用字符串前景色
            self._active_tag.set_property("foreground", hex_color)
            # 如需 RGBA，可改为：
            # rgba = Gdk.RGBA()
            # rgba.parse(hex_color)
            # self._active_tag.set_property("foreground-rgba", rgba)
        if bold is not None:
            self._active_tag.set_property(
                "weight", Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
        if underline is not None:
            self._active_tag.set_property(
                "underline",
                Pango.Underline.SINGLE if underline else Pango.Underline.NONE
            )

    # ---------- 内部实现 ----------
    def _append_paragraph(self, i, ptext):
        start_off = self.buf.get_end_iter().get_offset()
        # 使用空行作为段落分隔，便于视觉与逻辑划分
        self.buf.insert(self.buf.get_end_iter(), ptext)
        end_off = self.buf.get_end_iter().get_offset()

        tag = self.buf.get_tag_table().lookup(self.get_paragraph_tag_name(i)) \
            or self.buf.create_tag(self.get_paragraph_tag_name(i))
        self.buf.apply_tag(
            tag,
            self.buf.get_iter_at_offset(start_off),
            self.buf.get_iter_at_offset(end_off)
        )

        # 应用布局 tag（行/段间距）到新段
        self.buf.apply_tag(
            self._layout_tag,
            self.buf.get_iter_at_offset(start_off),
            self.buf.get_iter_at_offset(end_off)
        )

        self._paragraph_ranges.append((start_off, end_off))

    def _locate_paragraph(self, off: int):
        a = self._paragraph_ranges
        lo, hi = 0, len(a) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            s, e = a[mid]
            if off < s:
                hi = mid - 1
            elif off >= e:
                lo = mid + 1
            else:
                return mid
        return None

    def _on_released(self, _gesture, _n_press, _x, _y):
        # 使用插入光标位置判段（TextView 会在点击处设置插入光标）
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        off = it.get_offset()
        idx = self._locate_paragraph(off)
        if idx is None:
            return
        self.highlight_paragraph(idx, ensure_visible=False)
        if self._on_click_cb:
            s, e = self._paragraph_ranges[idx]
            self._on_click_cb(idx, self.get_paragraph_tag_name(idx), s, e)

    def _scroll_to_iter_safe(self, it: Gtk.TextIter, center: bool):
        """
        兼容 set_text/insert 后立即滚动可能无效的问题。
        用 idle 回调与 scroll_to_iter 组合保证可靠滚动。
        """
        def do_scroll():
            self.view.scroll_to_iter(
                it,
                0.1 if center else 0.0,
                True,
                0.0,
                0.5 if center else 0.1,
            )
            # 触发一次“可视段”刷新
            self._queue_emit_visible_idx()
            return False
        GLib.idle_add(do_scroll)

    def _apply_font_size(self, pt: int):
        css = f"""
        textview {{
            font-size: {pt}pt;
        }}
        """
        self._css_provider.load_from_data(css.encode("utf-8"))
        self.view.get_style_context().add_provider(
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )

    def _apply_layout_tag_full(self):
        self.buf.apply_tag(
            self._layout_tag,
            self.buf.get_start_iter(),
            self.buf.get_end_iter()
        )

    def _reapply_layout_tag(self):
        self.buf.remove_tag(
            self._layout_tag,
            self.buf.get_start_iter(),
            self.buf.get_end_iter()
        )
        self._apply_layout_tag_full()

    # ---- 可视段监听（滚动/布局变化时回调，不自动改变着色）----
    def _on_scroll_value_changed(self, _adj):
        self._queue_emit_visible_idx()

    def _queue_emit_visible_idx(self):
        # 去抖：同一帧只算一次
        GLib.idle_add(self._emit_visible_idx_once, priority=GLib.PRIORITY_LOW)

    def _emit_visible_idx_once(self):
        if not self._paragraph_ranges:
            return False

        # 取 TextView 的可视矩形（buffer 坐标）
        rect = self.view.get_visible_rect()

        # 在可视区域顶部向下偏移 2px，避开段间空白
        probe_x = rect.x + rect.width // 3
        probe_y = rect.y + 2

        # 兼容两种返回风格：有的绑定返回 (ok, iter)，有的直接抛异常
        it = None
        try:
            ok, iter_obj = self.view.get_iter_at_location(probe_x, probe_y)
            if ok:
                it = iter_obj
        except TypeError:
            it = self.view.get_iter_at_location(probe_x, probe_y)

        if it is None:
            return False

        off = it.get_offset()
        idx = self._locate_paragraph(off)
        if idx is None:
            return False

        if idx != self._last_visible_idx:
            self._last_visible_idx = idx
            if self._on_visible_idx_changed:
                self._on_visible_idx_changed(idx)
        return False
