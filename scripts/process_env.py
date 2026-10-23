"""Restore the system DLL search for external programs in a frozen Windows app."""
from contextlib import contextmanager
import ctypes
import os
import sys
import threading

_lock = threading.RLock()


@contextmanager
def external_dll_search():
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        yield
        return
    # PyInstaller sets this process-wide path; external Python/native programs
    # must not accidentally load its bundled Python or runtime DLLs.
    with _lock:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            if not kernel.SetDllDirectoryW(str(sys._MEIPASS)):
                raise ctypes.WinError(ctypes.get_last_error())
