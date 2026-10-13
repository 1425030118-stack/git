import csv
import importlib
import json
import os
import queue
import re
import requests
import tkinter as tk
import webbrowser
from datetime import date, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from threading import Thread
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parent
from source.common import get_proxy_config


DATA_DIR = ROOT / "Data"
CSV_PATTERN = re.compile(r"^github-ranking-(\d{4}-\d{2}-\d{2})\.csv$")
VIEW_TYPES = ("总榜", "日榜", "月榜", "年榜")
GITHUB_SEARCH_PAGE_SIZE = 100
GITHUB_SEARCH_MAX_RESULTS = 1000
TABLE_COLUMNS = (
    ("rank", "排名", 60, "center"),
    ("repo_name", "项目", 200, "w"),
    ("stars", "当前 Stars", 105, "e"),
    ("star_gain", "新增 Stars", 105, "e"),
    ("last_commit", "最近推送", 165, "w"),
    ("description", "项目简介", 440, "w"),
)
TRANSLATION_CACHE = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    / "GithubRankingViewer"
    / "translations-argos-zh-CN.json"
)


def search_github_repositories(query, page):
    token_path = ROOT / "access_token.txt"
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(f"无法读取 GitHub Token：{error}") from error
    if not token:
        raise RuntimeError(f"请先在项目根目录配置有效的 GitHub Token：\n{token_path}")

    response = requests.get(
        "https://api.github.com/search/repositories",
        params={
            "q": f"{query} in:name,description,readme",
            "sort": "stars",
            "order": "desc",
            "per_page": GITHUB_SEARCH_PAGE_SIZE,
            "page": page,
        },
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        proxies=get_proxy_config(),
        timeout=30,
    )
    if response.status_code != 200:
        try:
            detail = response.json().get("message", response.text[:500])
        except (ValueError, AttributeError):
            detail = response.text[:500]
        raise RuntimeError(f"GitHub 搜索失败（HTTP {response.status_code}）：{detail}")

    try:
        payload = response.json()
        items = payload["items"]
        total_count = int(payload["total_count"])
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError("GitHub 返回了无法识别的搜索结果。") from error

    rows = []
    for rank, repository in enumerate(items, start=(page - 1) * GITHUB_SEARCH_PAGE_SIZE + 1):
        rows.append({
            "rank": rank,
            "repo_name": repository["name"],
            "stars": repository["stargazers_count"],
            "star_gain": "",
            "last_commit": repository.get("pushed_at") or "",
            "description": repository.get("description") or "",
            "username": repository["owner"]["login"],
            "language": repository.get("language") or "",
            "repo_url": repository["html_url"],
        })
    return rows, total_count


def available_csv_files():
    files = []
    if DATA_DIR.is_dir():
        for path in DATA_DIR.iterdir():
            match = CSV_PATTERN.match(path.name)
            if match and path.is_file():
                files.append((match.group(1), path))
    return sorted(files, reverse=True)


def period_options(view_type, snapshot_dates):
    if view_type == "总榜":
        return ["最新快照"]
    if view_type == "日榜":
        return [
            current_date
            for previous_date, current_date in zip(snapshot_dates[1:], snapshot_dates)
            if date.fromisoformat(previous_date)
            == date.fromisoformat(current_date) - timedelta(days=1)
        ]
    if view_type == "月榜":
        periods = sorted(
            {snapshot_date[:7] for snapshot_date in snapshot_dates}, reverse=True,
        )
        return [
            period for period in periods
            if all(snapshot_pair(view_type, period, snapshot_dates))
        ]
    if view_type == "年榜":
        periods = sorted(
            {snapshot_date[:4] for snapshot_date in snapshot_dates}, reverse=True,
        )
        return [
            period for period in periods
            if all(snapshot_pair(view_type, period, snapshot_dates))
        ]
    return []


def snapshot_pair(view_type, selected_period, snapshot_dates):
    if not snapshot_dates:
        return None, None
    if view_type == "总榜":
        return snapshot_dates[0], None

    if view_type == "日榜":
        current_date = selected_period
        if current_date not in snapshot_dates:
            return None, None
        previous_dates = [snapshot_date for snapshot_date in snapshot_dates if snapshot_date < current_date]
        if not previous_dates:
            return current_date, None
        previous_date = previous_dates[0]
        if date.fromisoformat(previous_date) != date.fromisoformat(current_date) - timedelta(days=1):
            return current_date, None
        return current_date, previous_date

    if view_type == "月榜":
        year, month = (int(part) for part in selected_period.split("-"))
        period_start = date(year, month, 1)
        period_end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    elif view_type == "年榜":
        year = int(selected_period)
        period_start = date(year, 1, 1)
        period_end = date(year + 1, 1, 1)
    else:
        return None, None

    in_period = [
        snapshot_date for snapshot_date in snapshot_dates
        if period_start <= date.fromisoformat(snapshot_date) < period_end
    ]
    before_period = [
        snapshot_date for snapshot_date in snapshot_dates
        if date.fromisoformat(snapshot_date) < period_start
    ]
    return (
        max(in_period) if in_period else None,
        max(before_period) if before_period else None,
    )


def read_stars_snapshot(path):
    repositories = {}
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            if row.get("item") != "top-100-stars":
                continue
            repository_url = (row.get("repo_url") or "").strip().rstrip("/").casefold()
            if repository_url:
                repositories[repository_url] = row
    return repositories


def build_growth_rows(current_rows, previous_rows):
    growth_rows = []
    for repository_url, current_row in current_rows.items():
        previous_row = previous_rows.get(repository_url)
        if previous_row is None:
            continue
        try:
            stars_added = int(current_row["stars"]) - int(previous_row["stars"])
        except (KeyError, TypeError, ValueError):
            continue
        growth_row = dict(current_row)
        growth_row["star_gain"] = stars_added
        growth_rows.append(growth_row)
    growth_rows.sort(key=lambda row: (-row["star_gain"], row["repo_name"].casefold()))
    for rank, row in enumerate(growth_rows, start=1):
        row["rank"] = rank
    return growth_rows


class RankingViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub 排行榜")
        self.root.geometry("1280x780")
        self.root.minsize(900, 560)
        self.root.configure(bg="#f5f7fb")

        self.csv_files = available_csv_files()
        self.snapshot_dates = [snapshot_date for snapshot_date, _ in self.csv_files]
        self.snapshot_paths = dict(self.csv_files)
        self.rows = []
        self.urls = {}
        self.view_var = tk.StringVar(value="总榜")
        self.period_var = tk.StringVar()
        self.board_context = ""
        self.sort_column = "rank"
        self.sort_reverse = False
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.translation_cache = {}
        self.translation_queue = queue.Queue()
        self.translation_running = False
        self.github_search_queue = queue.Queue()
        self.github_search_running = False
        self.github_search_page = 0
        self.github_search_total = 0
        self.github_search_query = ""
        self._load_translation_cache()

        self._configure_style()
        self._build_ui()
        if not self.csv_files:
            messagebox.showerror(
                "没有找到排行榜数据",
                f"在以下目录中没有找到 github-ranking-YYYY-MM-DD.csv：\n{DATA_DIR}",
                parent=self.root,
            )
            self.root.after(0, self.root.destroy)
            return

        self.view_box["values"] = VIEW_TYPES
        self.view_box.current(0)
        self._refresh_period_options()
        self._load_board()

    def _configure_style(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=31, font=("Segoe UI", 10))
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI Semibold", 10),
            background="#edf1f7",
            foreground="#263247",
            padding=(8, 9),
        )
        style.map("Treeview", background=[("selected", "#dbeafe")],
                  foreground=[("selected", "#14213d")])
        style.configure("TCombobox", padding=6)

    def _build_ui(self):
        container = tk.Frame(self.root, bg="#f5f7fb", padx=24, pady=18)
        container.pack(fill="both", expand=True)

        tk.Label(
            container, text="GitHub 排行榜", bg="#f5f7fb", fg="#14213d",
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w")
        tk.Label(
            container, text="只看 Stars 榜；日、月、年榜按期间新增 Stars 排名。",
            bg="#f5f7fb", fg="#64748b", font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 17))

        controls = tk.Frame(container, bg="#ffffff", padx=14, pady=12,
                            highlightbackground="#e2e8f0", highlightthickness=1)
        controls.pack(fill="x", pady=(0, 12))

        tk.Label(controls, text="榜单类型", bg="#ffffff", fg="#475569",
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.view_box = ttk.Combobox(
            controls, textvariable=self.view_var, state="readonly", width=12,
        )
        self.view_box.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        self.view_box.bind("<<ComboboxSelected>>", lambda _event: self._change_view())

        tk.Label(controls, text="统计期间", bg="#ffffff", fg="#475569",
                 font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w")
        self.period_box = ttk.Combobox(
            controls, textvariable=self.period_var, state="readonly", width=16,
        )
        self.period_box.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(4, 0))
        self.period_box.bind("<<ComboboxSelected>>", lambda _event: self._load_board())

        tk.Label(controls, text="搜索项目", bg="#ffffff", fg="#475569",
                 font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w")
        search = ttk.Entry(controls, textvariable=self.search_var)
        search.grid(row=1, column=2, sticky="ew", padx=(0, 12), pady=(4, 0))
        search.bind("<KeyRelease>", lambda _event: self._render_rows())
        search.bind(
            "<Return>",
            lambda event: self._search_github() if event.keysym == "Return" else None,
        )

        self.search_button = ttk.Button(
            controls, text="联网搜索", command=self._search_github,
        )
        self.search_button.grid(row=1, column=3, sticky="ew", padx=(0, 10), pady=(4, 0))

        self.next_page_button = ttk.Button(
            controls, text="下一页", command=self._search_github_next_page,
            state="disabled",
        )
        self.next_page_button.grid(row=1, column=4, sticky="ew", padx=(0, 10), pady=(4, 0))

        self.retry_button = ttk.Button(
            controls, text="补全 / 重试翻译", command=self._request_translations,
        )
        self.retry_button.grid(row=1, column=5, sticky="ew", padx=(0, 10), pady=(4, 0))

        self.open_button = ttk.Button(
            controls, text="打开选中项目 ↗", command=self._open_selected,
        )
        self.open_button.grid(row=1, column=6, sticky="ew", pady=(4, 0))
        controls.columnconfigure(2, weight=1)

        table_frame = tk.Frame(container, bg="#ffffff",
                               highlightbackground="#e2e8f0", highlightthickness=1)
        table_frame.pack(fill="both", expand=True)
        column_ids = [column[0] for column in TABLE_COLUMNS]
        self.table = ttk.Treeview(
            table_frame, columns=column_ids, show="headings", selectmode="browse",
        )
        for column_id, title, width, anchor in TABLE_COLUMNS:
            self.table.heading(
                column_id, text=title,
                command=lambda key=column_id: self._sort_by(key),
            )
            self.table.column(column_id, width=width, minwidth=50,
                              anchor=anchor, stretch=column_id in ("repo_name", "description"))
        self.table.tag_configure("even", background="#ffffff")
        self.table.tag_configure("odd", background="#f8fafc")

        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table.bind("<Double-1>", lambda _event: self._open_selected())

        tk.Label(
            container, textvariable=self.status_var, bg="#f5f7fb", fg="#64748b",
            font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", pady=(10, 0))

    def _refresh_period_options(self):
        options = period_options(self.view_var.get(), self.snapshot_dates)
        self.period_box["values"] = options
        self.period_var.set(options[0] if options else "")
        self.period_box.configure(state="disabled" if self.view_var.get() == "总榜" else "readonly")

    def _change_view(self):
        self.sort_column = "rank" if self.view_var.get() == "总榜" else "star_gain"
        self.sort_reverse = self.view_var.get() != "总榜"
        self._refresh_period_options()
        self._load_board()

    def _load_board(self):
        if not self.snapshot_dates:
            return
        self.github_search_page = 0
        self.github_search_total = 0
        self.github_search_query = ""
        self.next_page_button.configure(state="disabled")
        view_type = self.view_var.get()
        current_date, baseline_date = snapshot_pair(
            view_type, self.period_var.get(), self.snapshot_dates,
        )
        self.rows = []
        if current_date is None:
            self.board_context = "该期间没有可用快照。"
            self._render_rows()
            return
        if baseline_date is None and view_type != "总榜":
            self.board_context = f"{current_date} 缺少可比较的上一份快照。"
            self._render_rows()
            return

        try:
            current_rows = read_stars_snapshot(self.snapshot_paths[current_date])
            if view_type == "总榜":
                self.rows = [
                    {**row, "star_gain": ""}
                    for row in sorted(
                        current_rows.values(),
                        key=lambda row: int(row.get("rank") or 0),
                    )
                ]
                self.board_context = f"总榜 · 快照 {current_date}"
            else:
                previous_rows = read_stars_snapshot(self.snapshot_paths[baseline_date])
                self.rows = build_growth_rows(current_rows, previous_rows)
                self.board_context = f"{view_type} · {baseline_date} 至 {current_date}"
        except (OSError, csv.Error, UnicodeError, ValueError) as error:
            messagebox.showerror(
                "读取榜单失败", f"无法读取 Stars 榜快照：\n{error}", parent=self.root,
            )
            self.rows = []
            self.board_context = "读取榜单失败。"
        self._render_rows()
        self._request_translations()

    def _search_github(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo("请输入搜索内容", "输入项目名称或关键词后再联网搜索。",
                                parent=self.root)
            return
        self._start_github_search(query, 1)

    def _search_github_next_page(self):
        next_page = self.github_search_page + 1
        if (
            self.github_search_query
            and not self.github_search_running
            and (next_page - 1) * GITHUB_SEARCH_PAGE_SIZE
            < min(self.github_search_total, GITHUB_SEARCH_MAX_RESULTS)
        ):
            self._start_github_search(self.github_search_query, next_page)

    def _start_github_search(self, query, page):
        if self.github_search_running:
            return
        self.github_search_running = True
        self.search_button.configure(state="disabled")
        self.next_page_button.configure(state="disabled")
        self.status_var.set(f"正在 GitHub 搜索“{query}”……")
        self.github_search_queue = queue.Queue()
        self.root.after(100, self._poll_github_search_queue)
        Thread(
            target=self._search_github_worker,
            args=(query, page, self.github_search_queue),
            daemon=True,
        ).start()

    @staticmethod
    def _search_github_worker(query, page, result_queue):
        try:
            rows, total_count = search_github_repositories(query, page)
            result_queue.put((query, page, rows, total_count, None))
        except (
            OSError, requests.RequestException, RuntimeError, ValueError, KeyError, TypeError,
        ) as error:
            result_queue.put((query, page, [], 0, str(error)))

    def _poll_github_search_queue(self):
        try:
            query, page, rows, total_count, error = self.github_search_queue.get_nowait()
        except queue.Empty:
            if self.github_search_running:
                self.root.after(100, self._poll_github_search_queue)
            return

        self.github_search_running = False
        self.search_button.configure(state="normal")
        if error:
            can_continue_previous_search = (
                self.github_search_query
                and self.github_search_page * GITHUB_SEARCH_PAGE_SIZE
                < min(self.github_search_total, GITHUB_SEARCH_MAX_RESULTS)
            )
            self.next_page_button.configure(
                state="normal" if can_continue_previous_search else "disabled",
                text=f"下一页 ({self.github_search_page + 1})",
            )
            self.status_var.set("GitHub 在线搜索失败。")
            messagebox.showerror("GitHub 搜索失败", error, parent=self.root)
            return

        self.search_var.set(query)
        self.github_search_query = query
        self.github_search_page = page
        self.github_search_total = total_count
        self.rows = rows
        self.sort_column = "stars"
        self.sort_reverse = True
        self.board_context = (
            f"GitHub 在线搜索 · 第 {page} 页 · 共 {total_count:,} 个匹配项目"
        )
        has_next_page = (
            page * GITHUB_SEARCH_PAGE_SIZE
            < min(total_count, GITHUB_SEARCH_MAX_RESULTS)
        )
        self.next_page_button.configure(
            state="normal" if has_next_page else "disabled",
            text=f"下一页 ({page + 1})",
        )
        if total_count > GITHUB_SEARCH_MAX_RESULTS:
            self.status_var.set(
                "GitHub 搜索最多返回 1,000 条匹配结果；当前显示星标最高的这一页。"
            )
        self._render_rows()
        self._request_translations()

    @staticmethod
    def _display_value(column, value):
        if column in ("rank", "stars", "star_gain"):
            try:
                return f"{int(value):,}"
            except (TypeError, ValueError):
                return value or ""
        return value or ""

    def _render_rows(self):
        if not hasattr(self, "table"):
            return
        self.table.delete(*self.table.get_children())
        self.urls.clear()
        eligible_translations = self._eligible_translations()

        query = self.search_var.get().strip().casefold()
        if query == self.github_search_query.casefold():
            query = ""
        visible_rows = [
            row for row in self.rows
            if not query or query in " ".join(
                row.get(key, "") or ""
                for key in ("repo_name", "username", "language", "description")
            ).casefold()
        ]
        visible_rows.sort(
            key=lambda row: self._sort_value(row.get(self.sort_column, "")),
            reverse=self.sort_reverse,
        )

        for index, row in enumerate(visible_rows):
            values = [self._display_value(
                column[0],
                self.translation_cache.get(
                    row.get("description", "").strip(), row.get("description", "")
                )
                if column[0] == "description"
                and row.get("description", "").strip() in eligible_translations
                else row.get(column[0], ""),
            )
                      for column in TABLE_COLUMNS]
            iid = self.table.insert(
                "", "end", values=values, tags=("even" if index % 2 == 0 else "odd",),
            )
            self.urls[iid] = row.get("repo_url", "")

        self.status_var.set(
            f"{self.board_context}  ·  显示 {len(visible_rows)} 个项目  ·  点击表头排序"
        )
        translated = sum(text in self.translation_cache for text in eligible_translations)
        self.status_var.set(
            self.status_var.get()
            + f"  ·  本地离线翻译 {translated}/{len(eligible_translations)}"
        )

    def _eligible_translations(self):
        descriptions = []
        seen = set()
        ranked_rows = sorted(self.rows, key=lambda row: self._sort_value(row.get("rank", "")))
        for row in ranked_rows:
            description = row.get("description", "").strip()
            if not description or self._contains_chinese(description) or description in seen:
                continue
            descriptions.append(description)
            seen.add(description)
        return descriptions

    @staticmethod
    def _contains_chinese(text):
        return any("\u4e00" <= character <= "\u9fff" for character in text)

    def _load_translation_cache(self):
        try:
            with TRANSLATION_CACHE.open("r", encoding="utf-8") as cache_file:
                cached = json.load(cache_file)
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showwarning(
                "翻译缓存不可用",
                f"无法读取本地翻译缓存，将重新翻译简介：\n{error}",
                parent=self.root,
            )
            return
        if isinstance(cached, dict):
            self.translation_cache = {
                source: translated
                for source, translated in cached.items()
                if isinstance(source, str) and isinstance(translated, str)
            }

    def _save_translation_cache(self):
        temporary_path = TRANSLATION_CACHE.with_suffix(".tmp")
        try:
            TRANSLATION_CACHE.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(self.translation_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(TRANSLATION_CACHE)
        except OSError as error:
            messagebox.showerror(
                "保存翻译缓存失败",
                f"无法保存本地翻译缓存：\n{error}",
                parent=self.root,
            )

    def _request_translations(self):
        if not self.rows or self.translation_running:
            return
        descriptions = self._eligible_translations()
        pending = [text for text in descriptions if text not in self.translation_cache]
        if not pending:
            self._render_rows()
            return

        self.translation_running = True
        self.retry_button.configure(state="disabled")
        self._render_rows()
        self.translation_queue = queue.Queue()
        self.root.after(100, self._poll_translation_queue)
        Thread(
            target=self._translate_descriptions,
            args=(pending, self.translation_queue),
            daemon=True,
        ).start()

    @staticmethod
    def _translate_descriptions(descriptions, result_queue):
        translated = {}
        failures = []
        try:
            argos_translate = importlib.import_module("argostranslate.translate")

            installed_languages = {
                language.code for language in argos_translate.get_installed_languages()
            }
            if "en" not in installed_languages or "zh" not in installed_languages:
                raise RuntimeError(
                    "未找到已安装的英中离线语言包。请先双击 "
                    "setup_local_translation.bat 完成安装。"
                )
            for description in descriptions:
                result = argos_translate.translate(description, "en", "zh").strip()
                if not result:
                    raise RuntimeError("离线翻译模型返回了空译文。")
                translated[description] = result
        except ImportError:
            failures.append(
                "未安装 Argos Translate。请先双击 "
                "setup_local_translation.bat 完成安装。"
            )
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            failures.append(str(error))
        result_queue.put((translated, failures))

    def _poll_translation_queue(self):
        try:
            translated, failures = self.translation_queue.get_nowait()
        except queue.Empty:
            if self.translation_running:
                self.root.after(100, self._poll_translation_queue)
            return

        self.translation_cache.update(translated)
        self.translation_running = False
        self.retry_button.configure(state="normal")
        if translated:
            self._save_translation_cache()
        self._render_rows()

        if failures:
            messagebox.showwarning(
                "部分简介未能翻译",
                f"本次成功翻译 {len(translated)} 条简介。未翻译部分会继续显示原文。\n\n"
                f"原因：{failures[0]}",
                parent=self.root,
            )
        if not failures:
            self._request_translations()

    @staticmethod
    def _sort_value(value):
        try:
            return (0, int(value))
        except (TypeError, ValueError):
            return (1, (value or "").casefold())

    def _sort_by(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = column in ("stars", "star_gain")
        self._render_rows()

    def _open_selected(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo("尚未选择项目", "请先在榜单中选择一个项目。",
                                parent=self.root)
            return
        url = self.urls.get(selection[0], "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "github.com":
            messagebox.showerror("项目链接无效", "选中项目没有有效的 GitHub HTTPS 链接。",
                                 parent=self.root)
            return
        webbrowser.open(url)


def main():
    root = tk.Tk()
    RankingViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
