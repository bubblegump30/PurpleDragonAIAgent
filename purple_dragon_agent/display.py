"""Enable native Windows text rendering before creating any Tk windows."""
import sys
import ctypes


def enable_high_dpi():
    if sys.platform != 'win32':
        return
    # System DPI awareness avoids Windows bitmap stretching and keeps Tk's
    # point-based fonts and pixel-based layout on the same scale at startup.
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(1) == 0:
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def scale_layout(root, factor):
    """Scale pixel distances once; retain native point fonts and text widths."""
    if abs(factor - 1) < .05:
        return
    def pixels(value):
        return max(0, round(root.winfo_pixels(value) * factor))
    def padding(value):
        return tuple(pixels(v) for v in (value if isinstance(value, (tuple, list)) else root.tk.splitlist(str(value))))
    def walk(widget):
        options = widget.keys()
        for name in ('padx', 'pady', 'borderwidth', 'highlightthickness', 'wraplength', 'sashwidth'):
            if name in options:
                widget.configure(**{name: pixels(widget.cget(name))})
        if widget.winfo_class() in {'Frame', 'Canvas'}:
            for name in ('width', 'height'):
                if name in options:
                    widget.configure(**{name: pixels(widget.cget(name))})
        if widget.winfo_class() == 'Canvas':
            widget.scale('all', 0, 0, factor, factor)
        manager = widget.winfo_manager()
        if manager in {'pack', 'grid'}:
            info = widget.pack_info() if manager == 'pack' else widget.grid_info()
            values = {name: padding(info[name]) for name in ('padx', 'pady') if name in info}
            values.update({name: pixels(info[name]) for name in ('ipadx', 'ipady') if name in info})
            if manager == 'pack': widget.pack_configure(**values)
            else: widget.grid_configure(**values)
        for child in widget.winfo_children():
            walk(child)
    for child in root.winfo_children():
        walk(child)
