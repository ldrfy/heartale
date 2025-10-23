"""数据"""
import sqlite3
from datetime import date, datetime
from pathlib import Path
from sqlite3 import OperationalError
from typing import Iterator, List, Optional

from .. import PATH_CONFIG
from .book import Book
from .time_read import TimeRead


class LibraryDB:
    """_summary_
    """

    def __init__(self, db_path: str | Path = PATH_CONFIG / "heartale.db"):

        self.db_path = str(db_path)
        self.conn = sqlite3.connect(
            self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

        # self._ensure_columns_and_renames()  # <- 调用迁移函数

    def _ensure_columns_and_renames(self):
        """
        检查并添加缺失列，同时尝试把旧列重命名为新列：
          books.type -> books.fmt
          timereads.type -> timereads.way
        兼容旧版 SQLite（退化为 ADD COLUMN + COPY）。
        可重复执行且安全。
        """
        cur = self.conn.cursor()

        # 常规列检查（你原先的需要列）
        cur.execute("PRAGMA table_info(books)")
        book_cols = {r["name"] for r in cur.fetchall()}

        # 保证存在 chap_all, author 等（同你之前的逻辑）
        stmts = []
        if "chap_name" not in book_cols:
            stmts.append(
                "ALTER TABLE books ADD COLUMN chap_name TEXT NOT NULL DEFAULT ''")
        if "create_date" not in book_cols:
            stmts.append(
                "ALTER TABLE books ADD COLUMN create_date INTEGER NOT NULL DEFAULT 0")
        if "sort" not in book_cols:
            stmts.append(
                "ALTER TABLE books ADD COLUMN sort REAL NOT NULL DEFAULT 0")
        if "chap_all" not in book_cols:
            stmts.append(
                "ALTER TABLE books ADD COLUMN chap_all INTEGER NOT NULL DEFAULT 0")
        if "author" not in book_cols:
            stmts.append(
                "ALTER TABLE books ADD COLUMN author TEXT NOT NULL DEFAULT ''")
        for s in stmts:
            cur.execute(s)

        # 常规列检查（你原先的需要列）
        cur.execute("PRAGMA table_info(timereads)")
        td_cols = {r["name"] for r in cur.fetchall()}
        if "chap_n" not in td_cols:
            cur.execute(
                "ALTER TABLE timereads ADD COLUMN chap_n INTEGER NOT NULL DEFAULT 0")

        # 尝试重命名列的通用函数

        def rename_column_if_needed(table: str, old: str, new: str):
            cur.execute(f"PRAGMA table_info({table})")
            cols = {r["name"] for r in cur.fetchall()}
            if new in cols:
                return  # 已存在目标列，跳过
            if old not in cols:
                return  # 旧列不存在，也跳过

            # 检查 sqlite 版本是否支持 RENAME COLUMN
            ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
            # SQLite >= 3.25.0 支持 RENAME COLUMN
            supports_rename = ver >= (3, 25, 0)

            if supports_rename:
                try:
                    cur.execute(
                        f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")
                    return
                except OperationalError:
                    # 回退到 add+copy
                    pass

            # 退化方案：新增目标列，然后把旧列的数据复制过去
            # 目标列以 TEXT 类型和默认值添加；你可按需改类型/默认值
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN {new} INTEGER NOT NULL DEFAULT 0")
            cur.execute(
                f"UPDATE {table} SET {new} = {old} WHERE {old} IS NOT NULL")
            # 此时旧列仍存在。完全移除旧列需要重建表，操作复杂，风险较高，
            # 因此仅在确实需要时再实现表重建逻辑。
            return

        # 执行重命名（或复制）
        rename_column_if_needed("books", "type", "fmt")
        rename_column_if_needed("timereads", "type", "way")

        # 提交事务
        self.conn.commit()

    def close(self):
        """关闭
        """
        self.conn.commit()
        self.conn.close()

    # 初始化表
    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY,             -- 自增 ID（rowid）
            md5 TEXT NOT NULL UNIQUE,           -- 仍保证唯一
            path TEXT NOT NULL,
            name TEXT NOT NULL,
            author TEXT NOT NULL,
            fmt INTEGER NOT NULL DEFAULT 0,
            chap_n INTEGER NOT NULL DEFAULT 0,
            chap_name INTEGER NOT NULL DEFAULT '',
            chap_all INTEGER NOT NULL DEFAULT 0,
            chap_txt_pos INTEGER NOT NULL DEFAULT 0,
            txt_pos INTEGER NOT NULL DEFAULT 0,
            txt_all INTEGER NOT NULL DEFAULT 0,
            sort REAL NOT NULL DEFAULT 0,
            encoding TEXT,
            update_date INTEGER NOT NULL,
            create_date INTEGER NOT NULL
        )
        """)
        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_books_name ON books(name);
        """)
        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_books_update_date ON books(update_date);
        """)
        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_books_path ON books(path);
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS timereads (
            id INTEGER PRIMARY KEY,
            md5 TEXT NOT NULL,
            name TEXT NOT NULL,
            chap_n TEXT NOT NULL,
            way INTEGER NOT NULL DEFAULT 0,
            dt TEXT NOT NULL,              -- ISO datetime string
            day TEXT NOT NULL,             -- YYYY-MM-DD
            month TEXT NOT NULL,           -- YYYY-MM
            year TEXT NOT NULL,            -- YYYY
            words INTEGER NOT NULL DEFAULT 0,
            seconds INTEGER NOT NULL DEFAULT 0
        )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_tr_md5_day ON timereads(md5, day)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tr_day ON timereads(day)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_tr_month ON timereads(month)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tr_year ON timereads(year)")
        self.conn.commit()

    # -------------------------
    # Book 操作
    # -------------------------
    def save_book(self, book: Book) -> None:
        """
        保存 Book。若 md5 已存在则更新其字段（path/name/txt_all/encoding/update_date）。
        """
        b_ = self.get_book_by_md5(book.md5)
        if b_:
            book.create_date = b_.create_date
            book.chap_name = b_.chap_name
            book.chap_n = b_.chap_n
            book.chap_txt_pos = b_.chap_txt_pos
            book.txt_pos = b_.txt_pos
            book.sort = b_.sort

        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO books(
            md5, path, name, author, fmt, chap_n, chap_name, chap_all, chap_txt_pos,
            txt_all, txt_pos, encoding, sort, update_date, create_date
        )
        VALUES(
            :md5, :path, :name, :author, :fmt, :chap_n, :chap_name, :chap_all, :chap_txt_pos,
            :txt_all, :txt_pos, :encoding, :sort, :update_date, :create_date
        )
        ON CONFLICT(md5) DO UPDATE SET
            path=excluded.path,
            name=excluded.name,
            author=excluded.author,
            chap_n=excluded.chap_n,
            chap_name=excluded.chap_name,
            chap_all=excluded.chap_all,
            txt_all=excluded.txt_all,
            encoding=excluded.encoding,
            sort=excluded.sort,
            fmt=excluded.fmt,
            update_date=excluded.update_date,
            create_date=excluded.create_date
        """, {
            "md5": book.md5,
            "path": book.path,
            "name": book.name,
            "author": book.author,
            "fmt": book.fmt,
            "chap_n": book.chap_n,
            "chap_name": book.chap_name,
            "chap_all": book.chap_all,
            "chap_txt_pos": book.chap_txt_pos,
            "txt_all": book.txt_all,
            "txt_pos": book.txt_pos,
            "encoding": book.encoding,
            "sort": book.sort,
            "update_date": book.update_date,
            "create_date": book.create_date,
        })

    def update_book(self, book: Book) -> None:
        """
        保存 Book。若 md5 已存在则更新其字段（path/name/txt_all/encoding/update_date）。
        """
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO books(
            md5, path, name, author, fmt, chap_n, chap_name, chap_all, chap_txt_pos,
            txt_all, txt_pos, encoding, sort, update_date, create_date
        )
        VALUES(
            :md5, :path, :name, :author, :fmt, :chap_n, :chap_name, :chap_all, :chap_txt_pos,
            :txt_all, :txt_pos, :encoding, :sort, :update_date, CURRENT_TIMESTAMP
        )
        ON CONFLICT(md5) DO UPDATE SET
            path=excluded.path,
            name=excluded.name,
            author=excluded.author,
            fmt=excluded.fmt,
            chap_n=excluded.chap_n,
            chap_name=excluded.chap_name,
            chap_all=excluded.chap_all,
            chap_txt_pos=excluded.chap_txt_pos,
            txt_all=excluded.txt_all,
            txt_pos=excluded.txt_pos,
            encoding=excluded.encoding,
            sort=excluded.sort,
            update_date=excluded.update_date
        """, {
            "md5": book.md5,
            "path": book.path,
            "name": book.name,
            "author": book.author,
            "fmt": book.fmt,
            "chap_n": book.chap_n,
            "chap_name": book.chap_name,
            "chap_all": book.chap_all,
            "chap_txt_pos": book.chap_txt_pos,
            "txt_all": book.txt_all,
            "txt_pos": book.txt_pos,
            "encoding": book.encoding,
            "sort": book.sort,
            "update_date": book.update_date,
        })

    def delete_book_by_md5(self, md5: str) -> None:
        """
        删除一本书。
        :param md5: 书的 md5
        """
        cur = self.conn.cursor()
        cur.execute("DELETE FROM books WHERE md5 = ?", (md5,))

    def get_book_by_md5(self, md5: str) -> Optional[Book]:
        """根据md5找某本书

        Args:
            md5 (str): _description_

        Returns:
            Optional[Book]: _description_
        """
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM books WHERE md5 = ?", (md5,))
        row = cur.fetchone()
        if not row:
            return None
        return self._r2book(row)

    def search_books_by_name(self, name_pattern: str, limit: int = 100) -> List[Book]:
        """
        模糊查询 name。name_pattern 支持 SQL 通配符，比如 '%关键字%'.
        如果用户传入原始关键字，下面的示例会自动包裹成 '%关键字%'.
        """
        if "%" not in name_pattern:
            name_pattern = f"%{name_pattern}%"
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM books WHERE name LIKE ? ORDER BY sort DESC, update_date DESC LIMIT ?",
                    (name_pattern, limit))
        rows = cur.fetchall()
        return [self._r2book(r) for r in rows]

    # 用于迭代所有 books（可选）
    def iter_books(self) -> Iterator[Book]:
        """查找所有书

        Yields:
            Iterator[Book]: _description_
        """
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM books ORDER BY sort DESC, update_date DESC")
        for r in cur:
            yield self._r2book(r)

    def _r2book(self, r: sqlite3.Row) -> Book:
        """_summary_

        Args:
            r (_type_): _description_

        Returns:
            _type_: _description_
        """
        return Book(
            id=r["id"], path=r["path"], name=r["name"], author=r["author"],
            chap_n=r["chap_n"], chap_name=r["chap_name"], chap_all=r["chap_all"],
            chap_txt_pos=r["chap_txt_pos"], txt_pos=r["txt_pos"], txt_all=r["txt_all"],
            encoding=r["encoding"], md5=r["md5"], sort=r["sort"], fmt=r["fmt"],
            create_date=r["create_date"], update_date=r["update_date"]
        )

    def get_max_sort(self) -> float:
        """目前最大的排序

        Returns:
            float: _description_
        """
        cur = self.conn.cursor()
        cur.execute("SELECT MAX(sort) as max_sort FROM books")
        row = cur.fetchone()
        return row["max_sort"] if row and row["max_sort"] is not None else 0.0

    # -------------------------
    # TimeRead 操作
    # -------------------------

    def get_trs_by_md5_way_and_day_chap_n(self, md5: str, way: int, chap_n: int, day: date) -> List[TimeRead]:
        """找到某本书的某节，在一天中的所有 TimeRead 记录

        Args:
            md5 (str): _description_
            way (int): _description_
            chap_n (int): _description_
            day (date): _description_

        Returns:
            List[TimeRead]: 旧的在前
        """
        day_s = day.strftime("%Y-%m-%d")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM timereads WHERE md5 = ? AND way = ? AND chap_n = ? AND day = ? ORDER BY dt ASC",
                    (md5, way, chap_n, day_s))
        return [self._r2td(r) for r in cur.fetchall()]

    def save_time_read(self, tr: TimeRead) -> None:
        """
        保存一个 TimeRead 条目。
        同一天，同一本书的同一个章节之保存一个。
        """
        trs_ = self.get_trs_by_md5_way_and_day_chap_n(
            tr.md5, tr.way, tr.chap_n, tr.dt.date())
        if len(trs_) > 0:
            tr.id = trs_[0].id
            tr.dt = trs_[0].dt
            for tr_ in trs_:
                tr.words += tr_.words
                tr.seconds += tr_.seconds

        self.update_time_read(tr)

        # 更新第一个，删除其余
        for existing_tr in trs_[1:]:
            self.delete_tr(existing_tr)

        return tr

    def update_time_read(self, tr: TimeRead) -> None:
        """更新或保存，如果id存在更新

        Args:
            tr (TimeRead): _description_
        """
        iso = tr.dt.isoformat(sep=" ")
        day = tr.dt.strftime("%Y-%m-%d")
        month = tr.dt.strftime("%Y-%m")
        year = tr.dt.strftime("%Y")

        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO timereads(
            id, md5, name, chap_n, way, dt, day, month, year, words, seconds
        )
        VALUES(
            :id, :md5, :name, :chap_n, :way, :dt, :day, :month, :year, :words, :seconds
        )
        ON CONFLICT(id) DO UPDATE SET
            md5=excluded.md5,
            name=excluded.name,
            chap_n=excluded.chap_n,
            way=excluded.way,
            dt=excluded.dt,
            day=excluded.day,
            month=excluded.month,
            year=excluded.year,
            words=excluded.words,
            seconds=excluded.seconds
        """, {
            "id": tr.id,
            "md5": tr.md5,
            "name": tr.name,
            "chap_n": tr.chap_n,
            "way": tr.way,
            "dt": iso,
            "day": day,
            "month": month,
            "year": year,
            "words": tr.words,
            "seconds": tr.seconds,
        })
        tr.id = cur.lastrowid
        return tr

    def get_time_reads_by_md5_and_day(self, md5: str, day: date) -> List[TimeRead]:
        """某本书按天

        Args:
            md5 (str): _description_
            day (date): _description_

        Returns:
            List[TimeRead]: _description_
        """
        day_s = day.strftime("%Y-%m-%d")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM timereads WHERE md5 = ? AND day = ? ORDER BY dt ASC",
                    (md5, day_s))
        return [self._r2td(r) for r in cur.fetchall()]

    def get_time_reads_by_day(self, day: date) -> List[TimeRead]:
        """按天

        Args:
            day (date): _description_

        Returns:
            List[TimeRead]: _description_
        """
        day_s = day.strftime("%Y-%m-%d")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM timereads WHERE day = ? ORDER BY dt ASC",
                    (day_s,))
        return [self._r2td(r) for r in cur.fetchall()]

    def get_time_reads_by_month(self, year: int, month: int) -> List[TimeRead]:
        """按月

        Args:
            year (int): _description_
            month (int): _description_

        Returns:
            List[TimeRead]: _description_
        """
        month_s = f"{year:04d}-{month:02d}"
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM timereads WHERE month = ? ORDER BY dt ASC",
                    (month_s,))
        return [self._r2td(r) for r in cur.fetchall()]

    def get_time_reads_by_year(self, year: int) -> List[TimeRead]:
        """按年

        Args:
            year (int): _description_

        Returns:
            List[TimeRead]: _description_
        """
        year_s = f"{year:04d}"
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM timereads WHERE year = ? ORDER BY dt ASC",
                    (year_s,))
        return [self._r2td(r) for r in cur.fetchall()]

    def delete_tr(self, tr: TimeRead) -> None:
        """
        删除某个。
        :param id: 书的 id
        """
        cur = self.conn.cursor()
        cur.execute("DELETE FROM timereads WHERE id = ?", (tr.id,))

    def _r2td(self, row: sqlite3.Row) -> TimeRead:
        """_summary_

        Args:
            row (_type_): _description_

        Returns:
            TimeRead: _description_
        """
        dt_str = row["dt"]
        try:
            dt_obj = datetime.fromisoformat(dt_str)
        except Exception:  # pylint: disable=broad-except
            # 容错解析
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return TimeRead(
            id=row["id"],
            md5=row["md5"],
            name=row["name"],
            chap_n=row["chap_n"],
            way=row["way"],
            words=row["words"],
            seconds=row["seconds"],
            dt=dt_obj,
        )
