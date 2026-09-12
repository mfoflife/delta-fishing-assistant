"""Ordinary Win32 capture coordinates, global hotkeys and mouse input."""
import ctypes as C
from ctypes import wintypes as W
import os
import threading
import time

if os.name != "nt":
    raise RuntimeError("实时操作仅支持 Windows")

user32 = C.WinDLL("user32", use_last_error=True)
kernel32 = C.WinDLL("kernel32", use_last_error=True)
advapi32 = C.WinDLL("advapi32", use_last_error=True)
PTR = C.c_size_t


class MOUSEINPUT(C.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", PTR)]


class KEYBDINPUT(C.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", PTR)]


class HARDWAREINPUT(C.Structure):
    _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]


class INPUTUNION(C.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", W.DWORD), ("u", INPUTUNION)]


user32.GetForegroundWindow.restype = W.HWND
user32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
user32.GetWindowThreadProcessId.restype = W.DWORD
user32.GetWindowTextLengthW.argtypes = [W.HWND]
user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
user32.IsWindowVisible.argtypes = user32.IsWindow.argtypes = user32.IsIconic.argtypes = [W.HWND]
user32.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
user32.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]
user32.SendInput.argtypes = [W.UINT, C.POINTER(INPUT), C.c_int]
user32.SendInput.restype = W.UINT
user32.RegisterHotKey.argtypes = [W.HWND, C.c_int, W.UINT, W.UINT]
user32.UnregisterHotKey.argtypes = [W.HWND, C.c_int]
user32.GetMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
user32.PostThreadMessageW.argtypes = [W.DWORD, W.UINT, W.WPARAM, W.LPARAM]
kernel32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
kernel32.OpenProcess.restype = W.HANDLE
kernel32.CloseHandle.argtypes = [W.HANDLE]
advapi32.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
advapi32.GetTokenInformation.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)]
advapi32.GetSidSubAuthorityCount.argtypes = [C.c_void_p]
advapi32.GetSidSubAuthorityCount.restype = C.POINTER(C.c_ubyte)
advapi32.GetSidSubAuthority.argtypes = [C.c_void_p, W.DWORD]
advapi32.GetSidSubAuthority.restype = C.POINTER(W.DWORD)


def process_integrity(pid):
    """Read OS token metadata only; no game memory access or privilege changes."""
    process, token = None, W.HANDLE()
    try:
        process = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not process or not advapi32.OpenProcessToken(process, 0x0008, C.byref(token)):
            raise C.WinError(C.get_last_error())
        size = W.DWORD()
        advapi32.GetTokenInformation(token, 25, None, 0, C.byref(size))
        if not size.value:
            raise C.WinError(C.get_last_error())
        buffer = C.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, 25, buffer, size.value, C.byref(size)):
            raise C.WinError(C.get_last_error())
        # TOKEN_MANDATORY_LABEL begins with SID_AND_ATTRIBUTES, whose first field is PSID.
        sid = C.cast(buffer, C.POINTER(C.c_void_p))[0]
        count = advapi32.GetSidSubAuthorityCount(sid)[0]
        rid = advapi32.GetSidSubAuthority(sid, count-1)[0]
        label = "系统" if rid >= 0x4000 else "管理员" if rid >= 0x3000 else "普通" if rid >= 0x2000 else "低"
        return {"pid": pid, "level": rid, "label": label}
    except OSError as exc:
        return {"pid": pid, "level": None, "label": "无法读取", "error": exc.winerror}
    finally:
        if token:
            kernel32.CloseHandle(token)
        if process:
            kernel32.CloseHandle(process)


def set_dpi_awareness():
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
        user32.SetProcessDpiAwarenessContext(C.c_void_p(-4))
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


def pid_of(hwnd):
    pid = W.DWORD()
    user32.GetWindowThreadProcessId(hwnd, C.byref(pid))
    return pid.value


def title_of(hwnd):
    buf = C.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd)+1)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


def list_windows():
    items = []
    callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    @callback_type
    def visit(hwnd, _):
        title = title_of(hwnd)
        if title and user32.IsWindowVisible(hwnd) and pid_of(hwnd) != os.getpid():
            items.append((int(hwnd), title, pid_of(hwnd)))
        return True
    user32.EnumWindows.argtypes = [callback_type, W.LPARAM]
    user32.EnumWindows(visit, 0)
    return items


def client_box(hwnd):
    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        raise RuntimeError("游戏窗口已关闭或最小化")
    rect, point = W.RECT(), W.POINT()
    if not user32.GetClientRect(hwnd, C.byref(rect)) or not user32.ClientToScreen(hwnd, C.byref(point)):
        raise C.WinError(C.get_last_error())
    width, height = rect.right-rect.left, rect.bottom-rect.top
    if width < 100 or height < 100:
        raise RuntimeError("游戏窗口尺寸异常")
    return {"left": point.x, "top": point.y, "width": width, "height": height}


class Mouse:
    def __init__(self, hwnd, pid, stop_event):
        self.hwnd, self.pid, self.stop_event = hwnd, pid, stop_event
        self.held = set()

    def focused(self):
        return (user32.GetForegroundWindow() == self.hwnd and
                pid_of(self.hwnd) == self.pid and not user32.IsIconic(self.hwnd))

    def focus_details(self):
        foreground = user32.GetForegroundWindow()
        return {"target_hwnd": self.hwnd, "target_pid": self.pid,
                "target_title": title_of(self.hwnd),
                "foreground_hwnd": int(foreground or 0),
                "foreground_pid": pid_of(foreground) if foreground else None,
                "foreground_title": title_of(foreground) if foreground else ""}

    def _event(self, flag):
        event = INPUT(type=0)
        event.mi = MOUSEINPUT(0, 0, 0, flag, 0, 0)
        C.set_last_error(0)
        if user32.SendInput(1, C.byref(event), C.sizeof(INPUT)) != 1:
            raise RuntimeError(f"Windows 未接受鼠标输入（错误码 {C.get_last_error()}），已暂停")

    def down(self, button):
        if self.stop_event.is_set() or not self.focused():
            raise RuntimeError("已停止或游戏失去焦点，取消点击")
        self._event(0x0002 if button == "left" else 0x0008)
        self.held.add(button)

    def up(self, button):
        if button in self.held:
            self._event(0x0004 if button == "left" else 0x0010)
            self.held.discard(button)

    def click(self, button):
        self.down(button)
        try:
            self.stop_event.wait(0.04)
        finally:
            self.up(button)

    def release(self):
        for button in tuple(self.held):
            self.up(button)


class Hotkeys:
    def __init__(self, callback):
        self.callback = callback
        self.thread_id = None
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        registered = []
        try:
            for identifier, vk in [(1, 0x77), (2, 0x78)]:
                label = f"F{8 if identifier == 1 else 9}"
                if user32.RegisterHotKey(None, identifier, 0x4000, vk):
                    registered.append(identifier)
                    self.callback("hotkey_bound", {"id": identifier, "label": label})
                elif user32.RegisterHotKey(None, identifier, 0x4003, vk):
                    registered.append(identifier)
                    self.callback("hotkey_bound", {"id": identifier, "label": "Ctrl+Alt+"+label})
                else:
                    self.callback("hotkey_error", f"{label} 与备用组合键均被占用，请使用界面按钮")
            self.ready.set()
            msg = W.MSG()
            while True:
                result = user32.GetMessageW(C.byref(msg), None, 0, 0)
                if result <= 0:
                    break
                if msg.message == 0x0312:
                    self.callback("toggle" if msg.wParam == 1 else "stop", None)
        finally:
            for identifier in registered:
                user32.UnregisterHotKey(None, identifier)

    def close(self):
        self.ready.wait(0.5)
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
