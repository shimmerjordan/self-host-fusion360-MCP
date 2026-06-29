"""Diagnostic: enumerate the windows of the running Fusion process and show which
are enabled/visible/foreground — so we can design a reliable blocking-dialog
detector. Optionally dismiss the foreground dialog.

Usage:
    python scripts/win_dialogs.py            # list Fusion top-level windows
    python scripts/win_dialogs.py dismiss    # send Esc, then Enter, to the foreground popup
"""

import ctypes
import sys
from ctypes import wintypes

u = ctypes.windll.user32
k = ctypes.windll.kernel32

u.GetForegroundWindow.restype = wintypes.HWND
u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsWindowEnabled.argtypes = [wintypes.HWND]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
u.GetWindow.restype = wintypes.HWND

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
GW_OWNER = 4
WM_CLOSE = 0x0010


def text(hwnd):
    n = u.GetWindowTextLengthW(hwnd)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, b, n + 1)
    return b.value


def cls(hwnd):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(hwnd, b, 256)
    return b.value


def pid_of(hwnd):
    p = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return p.value


def fusion_pids():
    """Find PIDs whose main window title contains 'Fusion' (Autodesk Fusion)."""
    pids = set()

    def cb(hwnd, _l):
        if u.IsWindowVisible(hwnd):
            t = text(hwnd)
            if "Fusion" in t or "Autodesk" in t:
                pids.add(pid_of(hwnd))
        return True

    u.EnumWindows(WNDENUMPROC(cb), 0)
    return pids


def main():
    pids = fusion_pids()
    print("Fusion-like PIDs:", pids)
    fg = u.GetForegroundWindow()
    rows = []

    def cb(hwnd, _l):
        if pid_of(hwnd) in pids and u.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            u.GetWindowRect(hwnd, ctypes.byref(r))
            area = max(0, r.right - r.left) * max(0, r.bottom - r.top)
            rows.append((hwnd, area, u.IsWindowEnabled(hwnd), hwnd == fg,
                         u.GetWindow(hwnd, GW_OWNER), cls(hwnd), text(hwnd)[:60]))
        return True

    u.EnumWindows(WNDENUMPROC(cb), 0)
    rows.sort(key=lambda x: -x[1])
    print("hwnd        area      enabled fg  owner       class / title")
    for h, area, en, isfg, owner, c, t in rows:
        print("0x{:08X} {:>9} {!s:>5}  {!s:>3} 0x{:08X} {} | {}".format(
            h, area, en, isfg, owner or 0, c, t))

    if len(sys.argv) > 1 and sys.argv[1] == "dismiss":
        # Dismiss the foreground window if it's a Fusion popup (not the main window).
        if fg and pid_of(fg) in pids:
            main_hwnd = rows[0][0] if rows else 0
            if fg != main_hwnd:
                print("Dismissing foreground 0x{:08X} '{}' via WM_CLOSE".format(fg, text(fg)))
                u.PostMessageW(fg, WM_CLOSE, 0, 0)
            else:
                print("Foreground IS the main window; nothing to dismiss.")
        else:
            print("Foreground is not a Fusion window.")


if __name__ == "__main__":
    main()
