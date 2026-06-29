"""External dialog guard — a STANDALONE process that auto-dismisses blocking
modal dialogs which freeze Fusion's main thread.

Why a separate process (not a thread)?
--------------------------------------
Fusion's blocking calls (``ui.messageBox``, the unsaved-changes / document-
recovery / server-verification dialogs, ...) run a native modal loop on the main
thread and do NOT release the Python GIL. So *every* Python thread inside Fusion
— an in-process watchdog, even the HTTP server — is frozen for the whole time the
dialog is up. Only code in a different OS process can act. This script is that
process: launched by the add-in with Fusion's PID, it polls Fusion's top-level
windows via Win32 and dismisses a blocking modal with PostMessage (which works
cross-process and needs no foreground focus).

When does it act? (two independent, configurable triggers)
  * busy flag — the dispatcher writes ``--busy-file`` while an MCP op is running,
    so if a modal blocks mid-op we dismiss it after a short grace (the original
    "stuck for 270s" hang). This is the principled trigger: we only intervene
    when automation is actually wedged.
  * title allowlist — known nuisance dialogs (save / recover / server
    verification, ...) are dismissed after a longer grace even when idle, so
    Fusion's own spontaneous popups don't block future automation.

Dismissal is WM_CLOSE first (the [X]/Cancel path: no save, no Save-As loop, no
data loss), escalating to Esc then Enter. Windows only.

Usage (the add-in launches this; manual run is for debugging):
    python dialog_guard.py --pid 1234 --busy-file ~/.fusion-mcp/busy \
        --log ~/.fusion-mcp/addin.log --poll 1.0 --grace 1.5 --grace-allow 4.0 \
        --titles "self-test,recover,恢复,save,保存,server,验证,信任,offline,脱机"
"""

import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

_WM_KEYDOWN, _WM_KEYUP, _WM_CLOSE = 0x0100, 0x0101, 0x0010
_VK_RETURN, _VK_ESCAPE = 0x0D, 0x1B

_u = ctypes.windll.user32
_u.GetForegroundWindow.restype = wintypes.HWND
_u.IsWindowEnabled.argtypes = [wintypes.HWND]
_u.IsWindowVisible.argtypes = [wintypes.HWND]
_u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _title(hwnd):
    n = _u.GetWindowTextLengthW(hwnd)
    b = ctypes.create_unicode_buffer(n + 1)
    _u.GetWindowTextW(hwnd, b, n + 1)
    return b.value


def _area(hwnd):
    r = wintypes.RECT()
    _u.GetWindowRect(hwnd, ctypes.byref(r))
    return max(0, r.right - r.left) * max(0, r.bottom - r.top)


def _window_pid(hwnd):
    p = wintypes.DWORD()
    _u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return p.value


def _pid_windows(pid):
    out = []

    def cb(hwnd, _l):
        if _u.IsWindowVisible(hwnd) and _window_pid(hwnd) == pid:
            out.append(hwnd)
        return True

    _u.EnumWindows(_WNDENUMPROC(cb), 0)
    return out


def find_blocking_dialog(pid):
    """(hwnd, title) of a modal blocking the target process's main window, else
    (None, None). The main window is the largest top-level window; if it is
    *disabled* a modal is up, and we return the enabled popup (foreground first)."""
    wins = _pid_windows(pid)
    if not wins:
        return None, None
    main = max(wins, key=_area)
    if _u.IsWindowEnabled(main):
        return None, None
    fg = _u.GetForegroundWindow()
    if fg and fg != main and _window_pid(fg) == pid and _u.IsWindowEnabled(fg):
        return fg, _title(fg)
    for h in wins:
        if h != main and _u.IsWindowEnabled(h):
            return h, _title(h)
    return None, None


def dismiss(hwnd, attempt):
    """0 -> WM_CLOSE ([X]/Cancel: safe + reliable), 1 -> Esc, 2 -> Enter. All via
    PostMessage, so no foreground focus is required."""
    try:
        if attempt == 0:
            _u.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
            return "close"
        vk = _VK_ESCAPE if attempt == 1 else _VK_RETURN
        _u.PostMessageW(hwnd, _WM_KEYDOWN, vk, 0)
        _u.PostMessageW(hwnd, _WM_KEYUP, vk, 0)
        return "esc" if attempt == 1 else "enter"
    except Exception:
        return None


class _Log:
    def __init__(self, path):
        self._path = path

    def __call__(self, msg):
        line = "[{}] guard: {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg)
        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception:
            pass
        try:
            sys.stderr.write(line)
        except Exception:
            pass


def _busy(busy_file, max_age):
    """True if the dispatcher's busy flag exists and is fresh (an MCP op is in
    flight). The age cap prevents a stale flag — e.g. if Fusion crashed mid-op —
    from making us dismiss user dialogs forever."""
    try:
        st = os.stat(busy_file)
    except OSError:
        return False
    return (time.time() - st.st_mtime) <= max_age


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--busy-file", default="")
    ap.add_argument("--log", default="")
    ap.add_argument("--poll", type=float, default=1.0)
    ap.add_argument("--grace", type=float, default=1.5)        # when busy
    ap.add_argument("--grace-allow", type=float, default=4.0)  # idle + title match
    ap.add_argument("--busy-max-age", type=float, default=600.0)
    ap.add_argument("--titles", default="")  # comma-separated, case-insensitive substrings
    args = ap.parse_args(argv)

    log = _Log(args.log) if args.log else (lambda m: None)
    allow = [t.strip().lower() for t in args.titles.split(",") if t.strip()]
    log("started (pid={}, poll={}, grace={}, grace_allow={}, titles={})".format(
        args.pid, args.poll, args.grace, args.grace_allow, allow))

    blocked_since = None
    attempts = 0
    last_hwnd = None
    gone_ticks = 0  # consecutive ticks with zero target windows -> Fusion exited

    while True:
        time.sleep(args.poll)
        try:
            wins = _pid_windows(args.pid)
            if not wins:
                gone_ticks += 1
                if gone_ticks >= 10:
                    log("target process has no windows for 10 ticks; exiting.")
                    return 0
                continue
            gone_ticks = 0

            hwnd, title = find_blocking_dialog(args.pid)
            if not hwnd:
                blocked_since, attempts, last_hwnd = None, 0, None
                continue

            busy = _busy(args.busy_file, args.busy_max_age) if args.busy_file else False
            title_l = (title or "").lower()
            title_match = any(k in title_l for k in allow)
            if not (busy or title_match):
                continue  # a dialog the user opened themselves; leave it alone

            now = time.monotonic()
            if hwnd != last_hwnd:
                last_hwnd, attempts, blocked_since = hwnd, 0, now
            if blocked_since is None:
                blocked_since = now
            grace = args.grace if busy else args.grace_allow
            if now - blocked_since < grace:
                continue
            if attempts > 2:
                continue  # tried WM_CLOSE / Esc / Enter; give up quietly
            action = dismiss(hwnd, attempts)
            log("dismiss blocking dialog '{}' via {} (attempt {}, busy={}, title_match={})".format(
                title, action, attempts + 1, busy, title_match))
            attempts += 1
        except Exception as exc:  # noqa: BLE001
            log("error: {}".format(exc))


if __name__ == "__main__":
    sys.exit(main())
