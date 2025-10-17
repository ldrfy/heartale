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

        self._ensure_columns_and_renames()  # <- 调用迁移函数

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
        if "chap_all" not in book_cols:
            stmts.append(
                "ALTER TABLE books ADD COLUMN chap_all INTEGER NOT NULL DEFAULT 0")
        if "author" not in book_cols:
            stmts.append(
                "ALTER TABLE books ADD COLUMN author TEXT NOT NULL DEFAULT ''")
        for s in stmts:
            cur.execute(s)

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
            chap_all INTEGER NOT NULL DEFAULT 0,
            chap_txt_pos INTEGER NOT NULL DEFAULT 0,
            txt_pos INTEGER NOT NULL DEFAULT 0,
            txt_all INTEGER NOT NULL DEFAULT 0,
            encoding TEXT,
            update_date INTEGER NOT NULL
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
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO books(md5, path, name, author, fmt, chap_n, chap_all, chap_txt_pos, txt_all, txt_pos, encoding, update_date)
        VALUES(:md5, :path, :name, :author, :fmt, :chap_n, :chap_all, :chap_txt_pos, :txt_all, :txt_pos, :encoding, :update_date)
        ON CONFLICT(md5) DO UPDATE SET
            path=excluded.path,
            name=excluded.name,
            author=excluded.author,
            chap_all=excluded.chap_all,
            txt_all=excluded.txt_all,
            encoding=excluded.encoding,
            fmt=excluded.fmt,
            update_date=excluded.update_date
        """, {
            "md5": book.md5,
            "path": book.path,
            "name": book.name,
            "author": book.author,
            "fmt": book.fmt,
            "chap_n": book.chap_n,
            "chap_all": book.chap_all,
            "chap_txt_pos": book.chap_txt_pos,
            "txt_all": book.txt_all,
            "txt_pos": book.txt_pos,
            "encoding": book.encoding,
            "update_date": int(book.update_date),
        })

    def update_book(self, book: Book) -> None:
        """
        保存 Book。若 md5 已存在则更新其字段（path/name/txt_all/encoding/update_date）。
        """
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO books(md5, path, name, author, fmt, chap_n, chap_all, chap_txt_pos, txt_all, txt_pos, encoding, update_date)
        VALUES(:md5, :path, :name, :author, :fmt, :chap_n, :chap_all, :chap_txt_pos, :txt_all, :txt_pos, :encoding, :update_date)
        ON CONFLICT(md5) DO UPDATE SET
            path=excluded.path,
            name=excluded.name,
            author=excluded.author,
            fmt=excluded.fmt,
            chap_n=excluded.chap_n,
            chap_all=excluded.chap_all,
            chap_txt_pos=excluded.chap_txt_pos,
            txt_all=excluded.txt_all,
            txt_pos=excluded.txt_pos,
            encoding=excluded.encoding,
            update_date=excluded.update_date
        """, {
            "md5": book.md5,
            "path": book.path,
            "name": book.name,
            "author": book.author,
            "fmt": book.fmt,
            "chap_n": book.chap_n,
            "chap_all": book.chap_all,
            "chap_txt_pos": book.chap_txt_pos,
            "txt_all": book.txt_all,
            "txt_pos": book.txt_pos,
            "encoding": book.encoding,
            "update_date": int(book.update_date),
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
        return Book(
            path=row["path"],
            name=row["name"],
            author=row["author"],
            fmt=row["fmt"],
            chap_n=row["chap_n"],
            chap_all=row["chap_all"],
            chap_txt_pos=row["chap_txt_pos"],
            txt_all=row["txt_all"],
            txt_pos=row["txt_pos"],
            encoding=row["encoding"],
            md5=row["md5"],
            update_date=row["update_date"]
        )

    def search_books_by_name(self, name_pattern: str, limit: int = 100) -> List[Book]:
        """
        模糊查询 name。name_pattern 支持 SQL 通配符，比如 '%关键字%'.
        如果用户传入原始关键字，下面的示例会自动包裹成 '%关键字%'.
        """
        if "%" not in name_pattern:
            name_pattern = f"%{name_pattern}%"
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM books WHERE name LIKE ? ORDER BY update_date DESC LIMIT ?",
                    (name_pattern, limit))
        rows = cur.fetchall()
        return [
            Book(
                path=r["path"],
                name=r["name"],
                author=r["author"],
                fmt=r["fmt"],
                chap_n=r["chap_n"],
                chap_all=r["chap_all"],
                chap_txt_pos=r["chap_txt_pos"],
                txt_all=r["txt_all"],
                txt_pos=r["txt_pos"],
                encoding=r["encoding"],
                md5=r["md5"],
                update_date=r["update_date"]
            ) for r in rows
        ]

    # -------------------------
    # TimeRead 操作
    # -------------------------
    def save_time_read(self, tr: TimeRead) -> None:
        """
        保存一个 TimeRead 条目。
        允许同一天多条记录。若需要按 (md5, day) 唯一，可改表结构和这里逻辑。
        """
        iso = tr.dt.isoformat(sep=" ")
        day = tr.dt.strftime("%Y-%m-%d")
        month = tr.dt.strftime("%Y-%m")
        year = tr.dt.strftime("%Y")
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO timereads(md5, way, dt, day, month, year, words, seconds)
        VALUES(:md5, :way, :dt, :day, :month, :year, :words, :seconds)
        """, {
            "md5": tr.md5,
            "way": tr.way,
            "dt": iso,
            "day": day,
            "month": month,
            "year": year,
            "words": tr.words,
            "seconds": tr.seconds,
        })

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
        return [self._row_to_timeread(r) for r in cur.fetchall()]

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
        return [self._row_to_timeread(r) for r in cur.fetchall()]

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
        return [self._row_to_timeread(r) for r in cur.fetchall()]

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
        return [self._row_to_timeread(r) for r in cur.fetchall()]

    def _row_to_timeread(self, row: sqlite3.Row) -> TimeRead:
        # dt 存为 ISO 格式 "YYYY-MM-DD HH:MM:SS[.ffffff]" 或类似
        dt_str = row["dt"]
        try:
            dt_obj = datetime.fromisoformat(dt_str)
        except Exception:  # pylint: disable=broad-except
            # 容错解析
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return TimeRead(
            md5=row["md5"],
            way=row["way"],
            words=row["words"],
            seconds=row["seconds"],
            dt=dt_obj,
        )

    # 用于迭代所有 books（可选）
    def iter_books(self) -> Iterator[Book]:
        """查找所有书

        Yields:
            Iterator[Book]: _description_
        """
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM books ORDER BY update_date DESC")
        for r in cur:
            yield Book(
                path=r["path"], name=r["name"], author=r["author"], fmt=r["fmt"],
                chap_n=r["chap_n"], chap_all=r["chap_all"], chap_txt_pos=r["chap_txt_pos"],
                txt_all=r["txt_all"], txt_pos=r["txt_pos"], encoding=r["encoding"],
                md5=r["md5"], update_date=r["update_date"]
            )
