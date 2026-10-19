"""Regressoes dos icones; APIs Windows simuladas nos testes portaveis."""
import ctypes
import pathlib
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Windows"))
import rotor_windows as icons


class IconTests(unittest.TestCase):
    def test_dpi_failure_does_not_skip_app_identity(self):
        win = MagicMock()
        win.shcore.SetProcessDpiAwareness.side_effect = OSError("DPI ja definido")
        win.shell32.SetCurrentProcessExplicitAppUserModelID.return_value = 0
        with patch.object(sys, "platform", "win32"), patch.object(sys, "executable", "pythonw.exe"), \
             patch.object(ctypes, "windll", win, create=True), self.assertLogs(icons.LOG):
            icons.configure_process()
        win.shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(icons.APP_ID)

    def test_native_host_uses_same_inferred_identity_as_shortcuts(self):
        win = MagicMock()
        with patch.object(sys, "platform", "win32"), patch.object(sys, "executable", "Rotor_PU2PTU.exe"), \
             patch.object(ctypes, "windll", win, create=True):
            icons.configure_process()
        win.shell32.SetCurrentProcessExplicitAppUserModelID.assert_not_called()

    def test_ico_is_applied_without_requiring_png_loader(self):
        with tempfile.TemporaryDirectory() as folder:
            ico = pathlib.Path(folder) / "rotor_icon.ico"
            ico.touch()
            root = MagicMock()
            root.winfo_id.return_value = 0x123456789
            with patch.object(sys, "platform", "win32"), patch.object(icons, "asset_path", return_value=ico), \
                 patch.object(icons, "NativeIcons") as native, patch.object(tk, "PhotoImage") as photo:
                icons.configure_window(root)
                photo.assert_not_called()
                root.iconbitmap.assert_any_call(bitmap=str(ico))
                root.iconbitmap.assert_any_call(default=str(ico))
                root.after_idle.call_args.args[0]()
                native.return_value.apply.assert_called_with(0x123456789)

    def test_tk_image_failure_does_not_skip_native_icons(self):
        with tempfile.TemporaryDirectory() as folder:
            ico = pathlib.Path(folder) / "rotor_icon.ico"
            ico.touch()
            root = MagicMock()
            root.iconbitmap.side_effect = tk.TclError("bitmap indisponivel")
            with patch.object(sys, "platform", "win32"), patch.object(icons, "asset_path", return_value=ico), \
                 patch.object(icons, "NativeIcons") as native, \
                 patch.object(tk, "PhotoImage", side_effect=tk.TclError("png indisponivel")), self.assertLogs(icons.LOG):
                icons.configure_window(root)
                root.after_idle.call_args.args[0]()
                native.return_value.apply.assert_called_once()

    def test_native_icons_target_external_frame_and_keep_64bit_handles(self):
        native = icons.NativeIcons.__new__(icons.NativeIcons)
        native.user = MagicMock()
        native.user.GetAncestor.return_value = 0x123456789
        native.handles = [0x198765432, 0x1ABCDEF12]
        native.apply(0x234567890)
        native.user.GetAncestor.assert_called_once_with(0x234567890, 2)
        self.assertEqual([c.args for c in native.user.SendMessageW.call_args_list], [
            (0x123456789, 0x80, 0, 0x198765432),
            (0x123456789, 0x80, 1, 0x1ABCDEF12),
        ])
        native.close()
        self.assertEqual(native.user.DestroyIcon.call_count, 2)
        self.assertEqual(native.handles, [])


if __name__ == "__main__":
    unittest.main()
