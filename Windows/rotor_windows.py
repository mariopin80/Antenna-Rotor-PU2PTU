"""Identidade visual do Rotor: Tk e icones nativos do Windows.

Os HICON usam tipos de ponteiro de 64 bits. Falhas sao registradas no log;
nao interferem no controle serial ou no movimento do rotor.
"""
from __future__ import annotations

import ctypes
import logging
from pathlib import Path
import sys
import tkinter as tk

APP_ID = "MarioPin.PU2PTU.Rotor"
LOG = logging.getLogger(__name__)


def asset_path(name: str) -> Path:
    candidates = [Path(__file__).resolve().parent / "assets" / name]
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "assets" / name)
    candidates.append(Path(sys.executable).resolve().parent.parent / "pkgs" / "assets" / name)
    return next((p for p in candidates if p.is_file()), candidates[0])


def configure_process() -> None:
    if sys.platform != "win32":
        return
    # A falha de DPI nao pode impedir a configuracao de identidade.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        LOG.exception("Nao foi possivel configurar o DPI")
    # No instalador, o processo possui EXE e icone proprios. Usar a identidade
    # inferida desse caminho permite ao Windows associar os atalhos ao processo.
    # Execucao direta dos fontes precisa de ID explicito para separar do Python.
    if Path(sys.executable).name.lower() != "rotor_pu2ptu.exe":
        try:
            shell = ctypes.windll.shell32
            shell.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
            shell.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
            result = shell.SetCurrentProcessExplicitAppUserModelID(APP_ID)
            if result < 0:
                raise OSError(f"SetCurrentProcessExplicitAppUserModelID: {result:#x}")
        except (AttributeError, OSError):
            LOG.exception("Nao foi possivel configurar o AppUserModelID")


class NativeIcons:
    """Mantem os icones vivos e aplica-os ao HWND externo criado pelo Tk."""
    def __init__(self, icon: Path):
        from ctypes import wintypes
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user.GetAncestor.restype = wintypes.HWND
        self.user.GetSystemMetrics.argtypes = [ctypes.c_int]
        self.user.GetSystemMetrics.restype = ctypes.c_int
        self.user.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                       wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user.LoadImageW.restype = wintypes.HANDLE
        self.user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                         ctypes.c_size_t, ctypes.c_ssize_t]
        self.user.SendMessageW.restype = ctypes.c_ssize_t
        self.user.DestroyIcon.argtypes = [wintypes.HANDLE]
        self.user.DestroyIcon.restype = wintypes.BOOL
        self.handles = []
        try:
            for cx, cy in ((49, 50), (11, 12)):  # SM_CXSMICON/SM_CXICON e alturas
                handle = self.user.LoadImageW(None, str(icon), 1,
                    self.user.GetSystemMetrics(cx), self.user.GetSystemMetrics(cy), 0x10)
                if not handle:
                    raise ctypes.WinError(ctypes.get_last_error())
                self.handles.append(handle)
        except OSError:
            self.close()
            raise

    def apply(self, client: int) -> None:
        # winfo_id() e o HWND do cliente; a legenda pertence ao wrapper externo.
        window = self.user.GetAncestor(client, 2) or client  # GA_ROOT
        for kind, handle in enumerate(self.handles):
            self.user.SendMessageW(window, 0x0080, kind, handle)  # WM_SETICON

    def close(self) -> None:
        for handle in self.handles:
            self.user.DestroyIcon(handle)
        self.handles.clear()


def configure_window(root: tk.Tk) -> None:
    ico, png = asset_path("rotor_icon.ico"), asset_path("rotor_icon.png")
    bitmap_set = False
    if sys.platform == "win32" and ico.is_file():
        try:
            # Aplicacao explicita a esta janela, alem do padrao de novas janelas.
            root.iconbitmap(bitmap=str(ico))
            root.iconbitmap(default=str(ico))
            bitmap_set = True
        except tk.TclError:
            LOG.exception("Falha do Tk ao aplicar ICO: %s", ico)
    if not bitmap_set and png.is_file():
        try:
            original = tk.PhotoImage(master=root, file=str(png))
            root._rotor_photo_icons = [original.subsample(4), original.subsample(8)]
            root.iconphoto(True, *root._rotor_photo_icons)
        except tk.TclError:
            LOG.exception("Falha ao aplicar PNG: %s", png)
    if sys.platform != "win32":
        return
    if not ico.is_file():
        LOG.error("Arquivo de icone ausente: %s", ico)
        return
    try:
        root._rotor_native_icons = native = NativeIcons(ico)
    except (AttributeError, OSError):
        LOG.exception("Falha ao carregar HICON: %s", ico)
        return

    def apply(event=None):
        if event is not None and event.widget is not root:
            return
        try:
            if root.winfo_exists():
                native.apply(root.winfo_id())
        except (OSError, tk.TclError):
            LOG.exception("Falha ao aplicar WM_SETICON")

    def destroy(event):
        if event.widget is root:
            native.close()

    root.bind("<Map>", apply, add="+")
    root.bind("<Destroy>", destroy, add="+")
    root.after_idle(apply)
    root.after(250, apply)
