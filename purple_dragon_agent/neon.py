"""Scalable angular chrome drawn by Tk; supplied artwork is kept separate."""
import tkinter as tk
from .theme import COLORS


class NeonPanel(tk.Frame):
    def __init__(self, master, accent=None, **kwargs):
        super().__init__(master, bg=COLORS['bg'], **kwargs)
        self.accent = accent or COLORS['accent_bright']
        self.chrome = tk.Canvas(self, bg=COLORS['bg'], highlightthickness=0, bd=0)
        self.chrome.place(relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=COLORS['panel'])
        self.body.pack(fill='both', expand=True, padx=9, pady=9)
        self.bind('<Configure>', self._draw)

    def _draw(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 24 or h < 24:
            return
        self.chrome.delete('all')
        cut = min(12, h // 4)
        for inset, color, width in ((2, '#241044', 5), (4, self.accent, 1), (7, '#44246B', 1)):
            x, y = inset, inset
            points = [x+cut,y,w-x-cut,y,w-x,y+cut,w-x,h-y-cut,w-x-cut,h-y,x+cut,h-y,x,h-y-cut,x,y+cut]
            self.chrome.create_polygon(points, fill='', outline=color, width=width)
        self.chrome.create_line(18, 4, min(w-18, 92), 4, fill=COLORS['text'], width=1)


class ValueLabel:
    """Adapter for the existing dashboard refresh callbacks."""
    def __init__(self, master, value, color=None):
        self.variable = tk.StringVar(master=master, value=value)
        self.label = tk.Label(master, textvariable=self.variable, bg=COLORS['panel'],
                              fg=color or COLORS['text'], font=('Segoe UI', 10, 'bold'),
                              anchor='w', justify='left', wraplength=210)
        self.label.pack(fill='x', padx=10, pady=(0, 7))

    def set(self, value):
        self.variable.set(value)
