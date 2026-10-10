# -*- coding: utf-8 -*-
"""
Windows Auto-Start Manager (silent delayed mode, no admin needed).

Behavior (as requested):
- NOTHING pops up at login: no black window, no toast, no dead browser tab.
- 5 minutes after logon, a hidden starter launches the studio server
  (fully invisible). main.py itself waits until it is TRULY ready, then opens
  the FULL website UI once in the browser. Single-instance guard prevents
  any duplicate server or duplicate tab.

Why not a Scheduled Task? Creating one needs administrator rights
("Access is denied" on this machine). A Startup-folder script needs no
admin and achieves the exact same silent delayed result.

Legacy behavior (visible console + browser opened after 2 seconds onto a
dead page) is replaced: the old entry is removed and rewritten in the
new silent form on enable.
"""

import os
import sys

try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
STARTUP_DIR = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
STARTUP_VBS = STARTUP_DIR / "QuranStudio_AutoStart.vbs"
LAUNCHER_BAT = BASE_DIR / "launch_studio.bat"

TASK_NAME = "QuranStudio_DelayedStart"  # cleaned up if ever created
DELAY_MINUTES = 5


def create_launcher_bat():
    """Manual launcher: starts the server; main.py opens the browser itself
    exactly once when TRULY ready (no premature dead tab, no double tab)."""
    python_exe = sys.executable
    content = f"""@echo off
title Quran Studio Server
cd /d "%~dp0"
start "" "{python_exe}" main.py
"""
    with open(LAUNCHER_BAT, "w", encoding="utf-8") as f:
        f.write(content)
    return str(LAUNCHER_BAT)


def _write_delayed_silent_vbs():
    """Startup entry: sleeps 5 min invisibly, then starts main.py with zero UI.

    Written as UTF-16 so wscript reads the Arabic project path correctly.
    QURAN_BAT_OPEN is deliberately NOT set, so main.py opens the full UI
    itself exactly once when the server is truly ready.
    """
    python_exe = sys.executable
    main_py = str(BASE_DIR / "main.py")
    sleep_ms = DELAY_MINUTES * 60 * 1000
    vbs = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WScript.Sleep {sleep_ms}\n'
        f'WshShell.Run """{python_exe}"" ""{main_py}""", 0, False\n'
        'Set WshShell = Nothing\n'
    )
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(STARTUP_VBS, "w", encoding="utf-16") as f:
        f.write(vbs)
    return str(STARTUP_VBS)


def _remove_scheduled_task_quietly():
    """Best-effort cleanup of a task-based entry (usually needs admin)."""
    try:
        import subprocess
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                       capture_output=True, timeout=20, startupinfo=si)
    except Exception:
        pass


def is_autostart_enabled():
    """True if the silent delayed startup entry exists."""
    return STARTUP_VBS.exists()


def enable_autostart():
    """Enables silent delayed auto-start (5 min after logon, no popups)."""
    create_launcher_bat()
    _remove_scheduled_task_quietly()
    _write_delayed_silent_vbs()
    return True, (
        f"تم تفعيل التشغيل الصامت: بعد {DELAY_MINUTES} دقائق من فتح اللابتوب "
        "يعمل السيرفر في الخفاء وتُفتح واجهة الموقع كاملة تلقائياً (بدون أي نوافذ سوداء أو تنبيهات)"
    )


def disable_autostart():
    """Disables auto-start completely (nothing opens at boot)."""
    _remove_scheduled_task_quietly()
    if STARTUP_VBS.exists():
        try:
            STARTUP_VBS.unlink()
        except Exception as e:
            return False, f"تعذر الحذف: {e}"
        return True, "تم إلغاء التشغيل التلقائي نهائياً (لن يفتح شيء عند تشغيل اللابتوب)"
    return False, "التشغيل التلقائي غير مفعل بالفعل"


if __name__ == "__main__":
    if "--enable" in sys.argv:
        print(enable_autostart())
    elif "--disable" in sys.argv:
        print(disable_autostart())
    else:
        print("Auto-start status:", is_autostart_enabled())
