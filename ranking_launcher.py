import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


ROOT = Path(__file__).resolve().parent


def show_error(title, message):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message, parent=root)
    root.destroy()


def main():
    pythonw = Path(sys.executable)
    python = pythonw.with_name("python.exe")
    if not python.is_file():
        show_error("无法启动排行榜", f"找不到 Python 解释器：\n{python}")
        return 1

    try:
        update = subprocess.run(
            [str(python), str(ROOT / "source" / "process.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        show_error("无法更新排行榜", str(error))
        return 1

    if update.returncode:
        details = "\n".join(
            output.strip() for output in (update.stdout, update.stderr) if output.strip()
        )
        show_error(
            "GitHub 数据抓取失败",
            details[-10000:] if details else f"抓取程序退出代码：{update.returncode}",
        )
        return update.returncode

    try:
        viewer = subprocess.run(
            [sys.executable, str(ROOT / "ranking_viewer.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        show_error("无法打开排行榜", str(error))
        return 1

    if viewer.returncode:
        details = "\n".join(
            output.strip() for output in (viewer.stdout, viewer.stderr) if output.strip()
        )
        show_error(
            "排行榜运行失败",
            details[-10000:] if details else f"查看器退出代码：{viewer.returncode}",
        )
    return viewer.returncode


if __name__ == "__main__":
    raise SystemExit(main())
