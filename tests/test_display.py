import unittest
from unittest.mock import Mock, patch
from purple_dragon_agent.display import enable_high_dpi

class DisplayTests(unittest.TestCase):
    def test_non_windows_does_not_call_windows_api(self):
        with patch('purple_dragon_agent.display.sys.platform', 'linux'), patch('purple_dragon_agent.display.ctypes') as api:
            enable_high_dpi()
            api.windll.shcore.SetProcessDpiAwareness.assert_not_called()
    def test_windows_enables_awareness(self):
        with patch('purple_dragon_agent.display.sys.platform', 'win32'), patch('purple_dragon_agent.display.ctypes') as api:
            api.windll.shcore.SetProcessDpiAwareness.return_value = 0
            enable_high_dpi()
            api.windll.shcore.SetProcessDpiAwareness.assert_called_once_with(1)
            api.windll.user32.SetProcessDPIAware.assert_not_called()
    def test_legacy_windows_fallback(self):
        with patch('purple_dragon_agent.display.sys.platform', 'win32'), patch('purple_dragon_agent.display.ctypes') as api:
            api.windll.shcore.SetProcessDpiAwareness.side_effect = OSError('unavailable')
            enable_high_dpi()
            api.windll.user32.SetProcessDPIAware.assert_called_once()

class LayoutTests(unittest.TestCase):
    def tearDown(self):
        # Mock cycles must release their Tcl interpreter on its owning thread.
        import gc
        gc.collect()

    def test_real_tcl_tuple_and_scalar_padding(self):
        import tkinter as tk
        from purple_dragon_agent.display import scale_layout
        # Tcl interpreter needs no display, and uses the same splitlist parser as Tk.
        root = Mock()
        root.tk = tk.Tcl()
        root.winfo_pixels.side_effect = lambda value: int(value)
        widget = Mock()
        widget.keys.return_value = []
        widget.winfo_class.return_value = 'Button'
        widget.winfo_manager.return_value = 'pack'
        widget.pack_info.return_value = {'padx': (3, 0), 'pady': 0, 'ipadx': 0, 'ipady': 0}
        widget.winfo_children.return_value = []
        root.winfo_children.return_value = [widget]
        scale_layout(root, 2)
        widget.pack_configure.assert_called_once_with(padx=(6, 0), pady=(0,), ipadx=0, ipady=0)

    def test_grid_tcl_string_padding(self):
        import tkinter as tk
        from purple_dragon_agent.display import scale_layout
        root = Mock(); root.tk = tk.Tcl()
        root.winfo_pixels.side_effect = lambda value: int(value)
        widget = Mock(); widget.keys.return_value = []
        widget.winfo_class.return_value = 'Label'
        widget.winfo_manager.return_value = 'grid'
        widget.grid_info.return_value = {'padx': '4 8', 'pady': '2', 'ipadx': 0, 'ipady': 0}
        widget.winfo_children.return_value = []
        root.winfo_children.return_value = [widget]
        scale_layout(root, 1.5)
        widget.grid_configure.assert_called_once_with(padx=(6, 12), pady=(3,), ipadx=0, ipady=0)
