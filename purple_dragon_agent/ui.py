from __future__ import annotations

from pathlib import Path
import json
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

from .config import APP_DIR, load_config, save_config
from .workspace import Workspace
from .audit import AuditLog
from .permissions import PermissionEngine
from .tools import ToolRegistry
from .agent import Agent
from .lm_studio import LMStudioClient
from .theme import COLORS, FONT, MONO
from .neon import NeonPanel, ValueLabel
from .research import normalize_options
from .display import enable_high_dpi, scale_layout


class GlowButton(tk.Frame):
    """Native keyboard-accessible button with a raised face and lower shadow."""
    def __init__(self, master, text, command=None, width=150, danger=False):
        super().__init__(master, bg=master.cget("bg"), bd=0)
        self.face = COLORS["danger"] if danger else COLORS["button_face"]
        self.hover = "#B52D48" if danger else COLORS["button_hover"]
        self.edge = tk.Frame(self, bg=COLORS["button_edge"], bd=1, relief="raised")
        self.edge.pack(fill="x")
        self.button = tk.Button(
            self.edge, text=text, command=command,
            width=max(10, int(width / 10)), bg=self.face, fg=COLORS["text"],
            activebackground=self.hover, activeforeground="white",
            disabledforeground=COLORS["muted"], relief="raised", overrelief="raised",
            bd=2, cursor="hand2", font=(FONT, 10, "bold"),
            padx=12, pady=10, highlightthickness=1,
            highlightbackground=COLORS["button_edge"], highlightcolor=COLORS["accent_bright"],
            takefocus=True,
        )
        tk.Frame(self.edge, bg=COLORS["button_edge"], height=2).pack(fill="x")
        self.button.pack(fill="x", padx=1)
        tk.Frame(self.edge, bg=COLORS["accent_dark"], height=3).pack(fill="x")
        self.shadow = tk.Frame(self, bg=COLORS["button_shadow"], height=4)
        self.shadow.pack(fill="x", padx=(3, 0))
        self.button.bind("<Enter>", self._hover)
        self.button.bind("<Leave>", self._leave)
        self.button.bind("<ButtonPress-1>", self._press, add="+")
        self.button.bind("<ButtonRelease-1>", self._release, add="+")

    def _hover(self, event=None):
        if self.button.cget("state") != "disabled":
            self.button.configure(bg=self.hover)
            self.edge.configure(bg=COLORS["accent_bright"])

    def _leave(self, event=None):
        self.button.configure(bg=COLORS["panel_3"] if self.button.cget("state") == "disabled" else self.face, relief="raised")
        self.edge.configure(bg=COLORS["button_edge"])

    def _press(self, event=None):
        if self.button.cget("state") != "disabled":
            self.button.configure(relief="sunken")

    def _release(self, event=None):
        self.button.configure(relief="raised")

    def config_state(self, state):
        self.button.configure(state=state, bg=COLORS["panel_3"] if state == "disabled" else self.face)


class ScrollPanel(tk.Frame):
    """Scrollable content with visible scrollbar and scoped mouse-wheel routing."""
    def __init__(self, master):
        super().__init__(master, bg=COLORS["panel"])
        self.canvas = tk.Canvas(self, bg=COLORS["panel"], bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body = tk.Frame(self.canvas, bg=COLORS["panel"])
        self.item = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.item, width=event.width))
        self.winfo_toplevel().bind("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event):
        widget = event.widget
        while widget is not None:
            if widget == self and self.winfo_ismapped():
                self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            widget = getattr(widget, "master", None)


class StatusCard(tk.Frame):
    def __init__(self, master, title, value, dot_color=None):
        super().__init__(
            master,
            bg=COLORS["panel_2"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        self.columnconfigure(1, weight=1)
        tk.Frame(self, bg=COLORS["highlight"], height=2).grid(row=0, column=0, columnspan=2, sticky="new")
        dot_color = dot_color or COLORS["accent"]

        self.dot = tk.Canvas(self, width=16, height=16, bg=COLORS["panel_2"], bd=0, highlightthickness=0)
        self.dot.create_oval(4, 4, 12, 12, fill=dot_color, outline="")
        self.dot.grid(row=0, column=0, rowspan=2, padx=(14, 9), pady=12)

        tk.Label(self, text=title.upper(), bg=COLORS["panel_2"], fg=COLORS["muted"],
                 font=(FONT, 8, "bold")).grid(row=0, column=1, sticky="sw", pady=(10, 0))
        self.value_var = tk.StringVar(value=value)
        self.value_label = tk.Label(self, textvariable=self.value_var, bg=COLORS["panel_2"], fg=COLORS["text"],
                 font=(FONT, 10, "bold"), justify="left", anchor="w")
        self.value_label.grid(row=1, column=1, sticky="ew", pady=(0, 10), padx=(0, 12))
        self.bind("<Configure>", lambda event: self.value_label.configure(wraplength=max(70, event.width - self.dot.winfo_reqwidth() - 45)))

    def set(self, value):
        self.value_var.set(value)


class PurpleDragonApp:
    def __init__(self):
        self.config = load_config()
        self.busy = False
        self.closing = threading.Event()
        self.ui_events = queue.Queue()
        enable_high_dpi()
        self.root = tk.Tk()
        self.display_scale = max(1.0, float(self.root.tk.call("tk", "scaling")) / (96 / 72))
        self.root.title(f"{self.config['app_name']} v{self.config['version']}")
        scale = self.display_scale
        width = min(round(1600 * scale), self.root.winfo_screenwidth() - round(40 * scale))
        height = min(round(940 * scale), self.root.winfo_screenheight() - round(90 * scale))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(width, round(1020 * scale)), min(height, round(680 * scale)))
        self.root.configure(bg=COLORS["bg"])

        self._set_window_icon()

        self.workspace = self._make_workspace(self.config.get("workspace", "workspace"))
        self.audit = AuditLog(APP_DIR / "logs" / "activity.jsonl")
        self.permissions = PermissionEngine(
            self.config.get("permissions", {}),
            approval_callback=self._approval_callback,
        )
        self.tools = ToolRegistry(self.workspace, self.permissions, self.audit)
        self.agent = self._make_agent()

        self.current_page = None
        self.page_frames = {}
        self.nav_buttons = {}

        self._configure_ttk()
        self._build_shell()
        scale_layout(self.root, self.display_scale)
        self._show_page("dashboard")

        self.audit.record("app_started", version=self.config["version"], workspace=str(self.workspace.root))
        self._refresh_activity()
        self._refresh_status_cards()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(50, self._drain_events)
        self.root.after(100, self._refresh_terminal)

    def _close(self):
        import time
        self.closing.set()
        self.tools.runner.cancel()
        deadline = time.monotonic() + 5
        def finish_close():
            state = self.tools.runner.snapshot()['state']
            if state in {'starting','running'} and time.monotonic() < deadline:
                self.root.after(50,finish_close)
                return
            if state in {'starting','running'}:
                self.tools.runner.abort()
            self.root.destroy()
        finish_close()

    def _drain_events(self):
        try:
            while True:
                callback = self.ui_events.get_nowait()
                callback()
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(50, self._drain_events)

    def _set_window_icon(self):
        try:
            ico = APP_DIR / "assets" / "purple_dragon_ai.ico"
            png = APP_DIR / "assets" / "purple_dragon_ai.png"
            if ico.exists():
                self.root.iconbitmap(default=str(ico))
            elif png.exists():
                self._icon_image = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._icon_image)
        except Exception:
            pass

    def _configure_ttk(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TScrollbar", background=COLORS["panel_3"], troughcolor=COLORS["sidebar"], bordercolor=COLORS["sidebar"], arrowcolor=COLORS["muted"], lightcolor=COLORS["panel_3"], darkcolor=COLORS["panel_3"])
        style.map("TScrollbar", background=[("active", COLORS["accent_dark"]), ("pressed", COLORS["accent"])])
        style.configure(
            "Purple.TCombobox",
            fieldbackground=COLORS["panel_3"],
            background=COLORS["panel_3"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=6,
        )
        style.configure("Treeview", background=COLORS["panel_2"], fieldbackground=COLORS["panel_2"], foreground=COLORS["text"], font=(FONT, 9), rowheight=round(25 * self.display_scale))
        style.configure("Treeview.Heading", background=COLORS["panel_3"], foreground=COLORS["text"], font=(FONT, 9, "bold"))
        style.map("Treeview", background=[("selected", COLORS["accent_dark"])], foreground=[("selected", "white")])
        style.configure("TNotebook", background=COLORS["panel"])
        style.configure("TNotebook.Tab", background=COLORS["panel_3"], foreground=COLORS["text"], padding=(10, 6))
        style.map("TNotebook.Tab", background=[("selected", COLORS["accent_dark"])])
        style.map(
            "Purple.TCombobox",
            fieldbackground=[("readonly", COLORS["panel_3"])],
            foreground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["panel_3"])],
            selectforeground=[("readonly", COLORS["text"])],
        )

    def _make_workspace(self, value: str) -> Workspace:
        p = Path(value)
        if not p.is_absolute():
            p = APP_DIR / p
        return Workspace(p)

    def _make_agent(self) -> Agent:
        self.tools.memory_options = dict(self.config.get('project_memory',{'use_context':False,'record_history':True}))
        self.tools.research_options = dict(self.config.get('research',{'enabled':False,'allowed_domains':[],'denied_domains':[]}))
        lm = self.config.get("lm_studio", {})
        if not lm.get("enabled", False):
            self.tools.model = None
            return Agent(self.tools)
        client = LMStudioClient(
            endpoint=lm.get("endpoint", "http://127.0.0.1:1234/v1/chat/completions"),
            model=lm.get("model", "local-model"),
            temperature=float(lm.get("temperature", 0.2)),
            timeout_seconds=int(lm.get("timeout_seconds", 60)),
        )
        self.tools.model = client
        return Agent(self.tools, client)

    # ---------------- shell ----------------

    def _build_shell(self):
        self._build_masthead()
        self.sidebar = tk.Frame(self.root, bg=COLORS["sidebar"], width=180)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Frame(self.root, bg=COLORS["border"], width=1).pack(side="left", fill="y")

        self.main = tk.Frame(self.root, bg=COLORS["bg"])
        self.main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_topbar()

        self.content_host = tk.Frame(self.main, bg=COLORS["bg"])
        self.content_host.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self._build_dashboard_page()
        self._build_workspace_page()
        self._build_coding_page()
        self._build_terminal_page()
        self._build_memory_page()
        self._build_research_page()
        self._build_permissions_page()
        self._build_activity_page()
        self._build_settings_page()
        self._build_about_page()

    def _build_sidebar(self):
        tk.Label(self.sidebar, text='AGENT WORKSPACE', bg=COLORS['sidebar'], fg=COLORS['cyan'], font=(FONT,9,'bold')).pack(fill='x',pady=(14,12))

        nav_items = [
            ("dashboard", "Chat", "◇"),
            ("workspace", "Workspace", "▣"),
            ("coding", "Coding", "⌘"),
            ("terminal", "Terminal & Tests", "▸"),
            ("memory", "Project Memory", "◇"),
            ("research", "Research", "◎"),
            ("permissions", "Permissions", "◆"),
            ("activity", "Activity", "≋"),
            ("settings", "Settings", "⚙"),
            ("about", "About", "i"),
        ]

        nav_scroll = ScrollPanel(self.sidebar)
        nav_scroll.configure(bg=COLORS['sidebar'])
        nav_scroll.canvas.configure(bg=COLORS['sidebar'])
        nav_scroll.body.configure(bg=COLORS['sidebar'])
        nav_scroll.pack(fill='both',expand=True)
        for key, label, symbol in nav_items:
            btn = tk.Button(
                nav_scroll.body,
                text=f"  {symbol}    {label}",
                anchor="w",
                command=lambda k=key: self._show_page(k),
                bg=COLORS["sidebar"],
                fg=COLORS["muted"],
                activebackground=COLORS["panel_3"],
                activeforeground=COLORS["text"],
                relief="flat",
                bd=0,
                cursor="hand2",
                padx=8,
                pady=10,
                highlightthickness=1,
                highlightbackground=COLORS["sidebar"],
                highlightcolor=COLORS["accent_bright"],
                font=(FONT, 10, "bold"),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn


        safe = tk.Frame(
            self.sidebar,
            bg=COLORS["panel"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        safe.pack(fill="x", padx=14, pady=14)
        tk.Label(safe, text="●  SAFE MODE", bg=COLORS["panel"], fg=COLORS["success"],
                 font=(FONT, 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(
            safe,
            text="Sensitive actions require\npermission or remain blocked.",
            justify="left",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(FONT, 8),
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _build_masthead(self):
        header = NeonPanel(self.root)
        header.pack(fill='x', padx=8, pady=(6, 2))
        body = header.body
        self._brand_art = tk.PhotoImage(file=str(APP_DIR / 'assets/reference_dragon_logo.png')).zoom(max(4, round(4*self.display_scale))).subsample(4)
        tk.Label(body, image=self._brand_art, bg=COLORS['panel']).pack(side='left', padx=(6, 16))
        brand = tk.Frame(body, bg=COLORS['panel'])
        brand.pack(side='left', fill='both', expand=True, pady=8)
        tk.Label(brand, text='PURPLE DRAGON AI AGENT', bg=COLORS['panel'], fg=COLORS['text'], font=(FONT, 22, 'bold'), anchor='w').pack(fill='x')
        tk.Label(brand, text='A S S I S T   / /   A U T O M A T E   / /   R E S E A R C H   / /   C O N T R O L', bg=COLORS['panel'], fg=COLORS['cyan'], font=(FONT, 8), anchor='w').pack(fill='x')
        tk.Button(body, text='⚙  SETTINGS', command=lambda:self._show_page('settings'), bg=COLORS['panel_2'], fg=COLORS['text'], activebackground=COLORS['accent_dark'], activeforeground='white', relief='flat', padx=12, pady=10, font=(FONT,9,'bold')).pack(side='right', padx=12)

    def _build_topbar(self):
        top = tk.Frame(self.main, bg=COLORS['bg'])
        top.pack(fill='x', padx=14, pady=(8, 4))
        self.page_title_var = tk.StringVar(value='AI CONVERSATION')
        self.page_subtitle_var = tk.StringVar(value='Chat with your local agent and run controlled tasks')
        self.status_var = tk.StringVar(value='SAFE MODE • READY')
        tk.Label(top, textvariable=self.status_var, bg=COLORS['panel_2'], fg=COLORS['success'], font=(FONT,9,'bold'), padx=12, pady=8).pack(side='right')
        tk.Label(top, textvariable=self.page_title_var, bg=COLORS['bg'], fg=COLORS['text'], font=(FONT,15,'bold'), anchor='w').pack(fill='x')
        tk.Label(top, textvariable=self.page_subtitle_var, bg=COLORS['bg'], fg=COLORS['muted'], font=(FONT,9), anchor='w').pack(fill='x')

    def _page(self):
        frame = tk.Frame(self.content_host, bg=COLORS["bg"])
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        return frame

    def _show_page(self, key):
        titles = {
            "dashboard": ("AI CONVERSATION", "Chat with your local agent and run controlled tasks"),
            "research": ("Research", "Retrieve approved public sources and review cited research drafts"),
            "memory": ("Project Memory", "Review local notes, decisions, history and optional model context"),
            "terminal": ("Terminal & Tests", "Preview fixed test commands, review output, and control execution"),
            "coding": ("Coding", "Analyze selected sources and stage code changes for review"),
            "workspace": ("Workspace", "Browse files, review edits, and restore tracked snapshots"),
            "permissions": ("Permissions", "Decide exactly what the agent can do"),
            "activity": ("Activity", "Review the auditable action history"),
            "settings": ("Settings", "Configure local model and workspace behavior"),
            "about": ("About", "Purple Dragon AI Agent information"),
        }
        self.page_title_var.set(titles[key][0])
        self.page_subtitle_var.set(titles[key][1])

        for k, btn in self.nav_buttons.items():
            selected = (k == key)
            btn.configure(
                bg=COLORS["panel_3"] if selected else COLORS["sidebar"],
                fg=COLORS["text"] if selected else COLORS["muted"],
                highlightbackground=COLORS["accent"] if selected else COLORS["sidebar"],
            )

        for frame in self.page_frames.values():
            frame.lower()
        self.page_frames[key].lift()
        self.current_page = key

        if key == "activity":
            self._refresh_activity()
        if key == "dashboard":
            self._refresh_status_cards()

    # ---------------- dashboard ----------------

    def _build_dashboard_page(self):
        page = self._page()
        self.page_frames['dashboard'] = page
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        center = tk.Frame(page, bg=COLORS['bg'])
        center.grid(row=0, column=0, sticky='nsew')
        self.dashboard_rail = tk.Frame(page, bg=COLORS['bg'], width=300)
        self.dashboard_rail.grid(row=0, column=1, sticky='nsew', padx=(8,0))
        self.dashboard_rail.grid_propagate(False)
        self.dashboard_rail.pack_propagate(False)
        hero = NeonPanel(center, accent=COLORS['cyan'])
        hero.pack(fill='x', pady=(0,6))
        hero.body.columnconfigure(0, weight=1)
        hero.body.columnconfigure(1, weight=2)
        hero.body.columnconfigure(2, weight=1)
        self._core_art = tk.PhotoImage(file=str(APP_DIR/'assets/reference_dragon_core.png')).zoom(max(4, round(4*self.display_scale))).subsample(8)
        emblem = tk.Label(hero.body, image=self._core_art, bg=COLORS['panel'])
        emblem.grid(row=0, column=1, rowspan=2, padx=3, pady=5)
        for index, title, attribute, value, color in (
            (0,'LOCAL MODEL','card_model','Fallback Planner',COLORS['accent_bright']),
            (1,'WORKSPACE','card_workspace','Ready',COLORS['cyan']),
            (2,'PERMISSIONS','card_permissions','Controlled',COLORS['warning']),
            (3,'AGENT STATUS','card_agent','Idle',COLORS['success'])):
            frame = tk.Frame(hero.body,bg=COLORS['panel'],highlightbackground=COLORS['border'],highlightthickness=1)
            frame.grid(row=index%2,column=0 if index<2 else 2,sticky='nsew',padx=5,pady=5)
            tk.Label(frame,text=title,bg=COLORS['panel'],fg=COLORS['muted'],font=(FONT,8,'bold'),anchor='w').pack(fill='x',padx=10,pady=(7,3))
            setattr(self,attribute,ValueLabel(frame,value,color))
        conversation = NeonPanel(center)
        conversation.pack(fill='both',expand=True,pady=(0,6))
        row = tk.Frame(conversation.body,bg=COLORS['panel']);row.pack(fill='x',padx=10,pady=(6,4))
        tk.Label(row,text='◈  PURPLE DRAGON AI',bg=COLORS['panel'],fg=COLORS['accent_bright'],font=(FONT,10,'bold')).pack(side='left')
        tk.Button(row,text='Clear',command=lambda:self.output.delete('1.0','end'),bg=COLORS['panel_2'],fg=COLORS['muted'],activebackground=COLORS['accent_dark'],relief='flat',font=(FONT,8)).pack(side='right')
        self.output = tk.Text(conversation.body,height=8,wrap='word',bg=COLORS['console'],fg=COLORS['console_text'],insertbackground=COLORS['cyan'],selectbackground=COLORS['accent_dark'],relief='flat',bd=0,padx=12,pady=12,font=(FONT,10),highlightthickness=1,highlightbackground=COLORS['border'])
        scrollbar=ttk.Scrollbar(conversation.body,command=self.output.yview)
        scrollbar.pack(side='right',fill='y')
        self.output.configure(yscrollcommand=scrollbar.set)
        self.output.pack(fill='both',expand=True,padx=(8,0),pady=(0,8))
        self.output.insert('end',f"Purple Dragon AI Agent v{self.config['version']}\n\nDescribe a goal below to begin.\nFiles, coding, terminal tests, memory and approved research are available from the navigation.\n\nSAFE MODE is active. Sensitive actions require approval.\n")
        composer=NeonPanel(center);composer.pack(fill='x')
        self.task=tk.Text(composer.body,height=2,wrap='word',bg=COLORS['recessed'],fg=COLORS['text'],insertbackground=COLORS['cyan'],selectbackground=COLORS['accent_dark'],relief='flat',padx=12,pady=9,font=(FONT,10),highlightthickness=1,highlightbackground=COLORS['border'],highlightcolor=COLORS['accent_bright'])
        self.task.pack(fill='x',padx=4,pady=(4,6));self.task.insert('1.0','scan workspace')
        actions=tk.Frame(composer.body,bg=COLORS['panel']);actions.pack(fill='x',padx=4,pady=(0,4))
        self.run_button=GlowButton(actions,'SEND  ➤',self._run_task,width=115);self.run_button.pack(side='right')
        GlowButton(actions,'WORKSPACE',self._choose_workspace,width=110).pack(side='left')
        self.workspace_var=tk.StringVar(value=str(self.workspace.root))
        label=tk.Label(actions,textvariable=self.workspace_var,bg=COLORS['panel'],fg=COLORS['muted'],font=(MONO,8),anchor='w',justify='left',wraplength=240)
        label.pack(side='left',fill='x',expand=True,padx=8)
        label.bind('<Configure>',lambda event:label.configure(wraplength=max(60,event.width)))
        modes=NeonPanel(self.dashboard_rail);modes.pack(fill='x',pady=(0,6))
        tk.Label(modes.body,text='✧  AGENT MODES',bg=COLORS['panel'],fg=COLORS['text'],font=(FONT,11,'bold'),anchor='w').pack(fill='x',padx=8,pady=6)
        for title,subtitle,key,color in (
            ('General Assist','Controlled task planner','dashboard',COLORS['accent_bright']),
            ('Code Assistant','Analyze sources and stage edits','coding',COLORS['cyan']),
            ('System Control','Workspace and guarded test runner','terminal',COLORS['success']),
            ('Research Agent','Approved sources and cited briefs','research',COLORS['warning']),
            ('Project Memory','Local notes, decisions and history','memory',COLORS['magenta'])):
            tk.Button(modes.body,text=f'{title}   ›\n{subtitle}',command=lambda k=key:self._show_page(k),bg=COLORS['panel_2'],fg=color,activebackground=COLORS['panel_3'],activeforeground=color,relief='flat',highlightbackground=color,highlightcolor='white',highlightthickness=1,anchor='w',justify='left',padx=12,pady=7,font=(FONT,9,'bold'),cursor='hand2').pack(fill='x',padx=5,pady=3)
        local=NeonPanel(self.dashboard_rail,accent=COLORS['cyan']);local.pack(fill='x',pady=(0,6))
        tk.Label(local.body,text='LOCAL MODEL STATUS',bg=COLORS['panel'],fg=COLORS['cyan'],font=(FONT,10,'bold'),anchor='w').pack(fill='x',padx=8,pady=6)
        self.local_model_status=tk.StringVar(value='')
        tk.Label(local.body,textvariable=self.local_model_status,bg=COLORS['panel'],fg=COLORS['text'],font=(FONT,9),justify='left',anchor='w',wraplength=250).pack(fill='x',padx=8,pady=(0,8))
        task=NeonPanel(self.dashboard_rail);task.pack(fill='x',pady=(0,6))
        tk.Label(task.body,text='TASK STATUS',bg=COLORS['panel'],fg=COLORS['text'],font=(FONT,10,'bold'),anchor='w').pack(fill='x',padx=8,pady=6)
        tk.Label(task.body,textvariable=self.status_var,bg=COLORS['panel'],fg=COLORS['success'],font=(FONT,9,'bold'),anchor='w').pack(fill='x',padx=8,pady=(0,8))
        recent=NeonPanel(self.dashboard_rail);recent.pack(fill='both',expand=True)
        tk.Button(recent.body,text='RECENT ACTIONS   ›',command=lambda:self._show_page('activity'),bg=COLORS['panel'],fg=COLORS['accent_bright'],relief='flat',font=(FONT,10,'bold'),anchor='w').pack(fill='x',padx=8,pady=6)
        self.recent_summary=tk.StringVar(value='No actions yet')
        tk.Label(recent.body,textvariable=self.recent_summary,bg=COLORS['panel'],fg=COLORS['muted'],font=(FONT,8),anchor='nw',justify='left',wraplength=245).pack(fill='both',expand=True,padx=8,pady=(0,8))
        def adapt(event):
            if event.width < round(1000*self.display_scale):
                self.dashboard_rail.grid_remove()
            else:
                self.dashboard_rail.grid()
        page.bind('<Configure>',adapt)

    # ---------------- research ----------------

    def _build_research_page(self):
        page=self._page();self.page_frames['research']=page
        self.research_status=tk.StringVar(value='Research is off by default. Add allowed domains and set Network Access to Ask before fetching.')
        tk.Label(page,textvariable=self.research_status,bg=COLORS['bg'],fg=COLORS['muted'],wraplength=700,justify='left',font=(FONT,9)).pack(fill='x',pady=(0,8))
        notebook=ttk.Notebook(page);notebook.pack(fill='both',expand=True)
        policy=tk.Frame(notebook,bg=COLORS['panel']);browse=tk.Frame(notebook,bg=COLORS['panel']);brief=tk.Frame(notebook,bg=COLORS['panel'])
        notebook.add(browse,text='Sources');notebook.add(brief,text='Research brief');notebook.add(policy,text='Domain policy')
        self.research_notebook=notebook
        opts=self.config.get('research',{})
        self.research_enabled=tk.BooleanVar(value=opts.get('enabled',False))
        tk.Checkbutton(policy,text='Enable controlled public HTTPS research',variable=self.research_enabled,bg=COLORS['panel'],fg=COLORS['text'],activebackground=COLORS['panel'],activeforeground=COLORS['text'],selectcolor=COLORS['panel_3'],font=(FONT,10)).pack(anchor='w',padx=12,pady=12)
        tk.Label(policy,text='One domain per line. Exact example.com; *.example.com matches subdomains only. Deny rules take priority. No IP literals, schemes or ports.',bg=COLORS['panel'],fg=COLORS['muted'],wraplength=650,justify='left',font=(FONT,9)).pack(anchor='w',padx=12)
        for label,key in (('Allowed domains','allowed_domains'),('Denied domains','denied_domains')):
            tk.Label(policy,text=label,bg=COLORS['panel'],fg=COLORS['text'],font=(FONT,10,'bold')).pack(anchor='w',padx=12,pady=(8,2))
            text=tk.Text(policy,height=4,wrap='word',bg=COLORS['panel_2'],fg=COLORS['text'],font=(MONO,10))
            text.pack(fill='x',padx=12);text.insert('1.0','\n'.join(opts.get(key,[])))
            setattr(self,'research_'+key,text)
        GlowButton(policy,'SAVE DOMAIN POLICY',self._save_research_options,width=190).pack(anchor='w',padx=12,pady=12)
        row=tk.Frame(browse,bg=COLORS['panel']);row.pack(fill='x',padx=10,pady=10)
        self.research_url=tk.StringVar()
        tk.Entry(row,textvariable=self.research_url,bg=COLORS['panel_2'],fg=COLORS['text'],insertbackground=COLORS['text'],font=(MONO,10)).pack(side='left',fill='x',expand=True)
        GlowButton(row,'PREVIEW URL',lambda:self._workspace_action('preview_web',{'url':self.research_url.get().strip()}),width=130).pack(side='left',padx=5)
        GlowButton(row,'FETCH SOURCE',lambda:self._workspace_action('fetch_web',{'url':self.research_url.get().strip()}),width=145).pack(side='left')
        controls=tk.Frame(browse,bg=COLORS['panel']);controls.pack(fill='x',padx=10,pady=(0,8))
        GlowButton(controls,'LOAD SOURCES',lambda:self._workspace_action('list_web_sources',{}),width=150).pack(side='left')
        GlowButton(controls,'CLEAR SOURCES',self._clear_research_sources,width=155,danger=True).pack(side='left',padx=8)
        self.web_sources=ttk.Treeview(browse,columns=('title','url'),show='headings',selectmode='extended',height=5)
        self.web_sources.heading('title',text='Title');self.web_sources.heading('url',text='Source URL')
        self.web_sources.column('title',width=200);self.web_sources.column('url',width=380)
        self.web_sources.pack(fill='x',padx=10)
        self.web_sources.bind('<<TreeviewSelect>>',self._select_web_source)
        self.web_text=tk.Text(browse,wrap='word',bg=COLORS['console'],fg=COLORS['console_text'],font=(FONT,10),state='disabled',height=5)
        self.web_text.pack(fill='both',expand=True,padx=10,pady=10)
        self.research_question=tk.StringVar();self.research_output_path=tk.StringVar(value='research-brief.md')
        tk.Label(brief,text='Question (uses selected cached sources, one to five)',bg=COLORS['panel'],fg=COLORS['text'],font=(FONT,10,'bold')).pack(anchor='w',padx=10,pady=(10,4))
        tk.Entry(brief,textvariable=self.research_question,bg=COLORS['panel_2'],fg=COLORS['text'],font=(FONT,10)).pack(fill='x',padx=10)
        row=tk.Frame(brief,bg=COLORS['panel']);row.pack(fill='x',padx=10,pady=8)
        GlowButton(row,'CREATE DRAFT',self._create_research_brief,width=150).pack(side='left')
        tk.Entry(row,textvariable=self.research_output_path,bg=COLORS['panel_2'],fg=COLORS['text'],font=(MONO,9),width=20).pack(side='left',fill='x',expand=True,padx=8)
        GlowButton(row,'STAGE BRIEF',self._stage_research_brief,width=150).pack(side='left')
        self.research_brief_text=tk.Text(brief,wrap='word',bg=COLORS['console'],fg=COLORS['console_text'],font=(FONT,10),state='disabled')
        self.research_brief_text.pack(fill='both',expand=True,padx=10,pady=(0,10))
        self.source_rows={};self.source_cache_ids=None;self.research_draft=None

    def _save_research_options(self):
        if self.busy:
            self.research_status.set('Wait for the current task before changing domain policy.')
            return
        try:
            opts=normalize_options({'enabled':self.research_enabled.get(),'allowed_domains':[line for line in self.research_allowed_domains.get('1.0','end').splitlines() if line.strip()],'denied_domains':[line for line in self.research_denied_domains.get('1.0','end').splitlines() if line.strip()]})
            updated=dict(self.config,research=opts);save_config(updated)
        except (ValueError,OSError) as exc:
            self.research_status.set(f'Domain policy not saved: {exc}')
            return
        self.config=updated;self.tools.research_options=dict(opts)
        self.audit.record('research_policy_changed',**opts)
        self.research_status.set('Domain policy saved. Network Access must allow an approved request; Deny still blocks it.')

    def _select_web_source(self,event=None):
        selected=self.web_sources.selection()
        if len(selected)==1:self._workspace_action('read_web_source',{'source_id':selected[0]})

    def _clear_research_sources(self):
        if self.source_cache_ids is None:
            self.research_status.set('Load the current source cache before clearing.')
            return
        self._workspace_action('clear_web_sources',{'expected_ids':self.source_cache_ids})

    def _create_research_brief(self):
        selected=list(self.web_sources.selection());question=self.research_question.get().strip()
        if not 1<=len(selected)<=5 or not question or len(question)>4000:
            self.research_status.set('Select one to five cached sources and enter a question up to 4000 characters.')
            return
        self._workspace_action('create_research_brief',{'source_ids':selected,'question':question})

    def _stage_research_brief(self):
        if not self.research_draft:
            self.research_status.set('Create and review a research draft before staging it.')
            return
        self._workspace_action('stage_changes',{'changes':{self.research_output_path.get().strip():self.research_draft['markdown']}})

    # ---------------- memory ----------------

    def _build_memory_page(self):
        page=self._page();self.page_frames['memory']=page
        options=tk.Frame(page,bg=COLORS['panel']);options.pack(fill='x',pady=(0,8))
        preferences=self.config.get('project_memory',{})
        self.use_memory_context=tk.BooleanVar(value=preferences.get('use_context',False))
        self.save_task_history=tk.BooleanVar(value=preferences.get('record_history',True))
        for label,var in (('Use relevant notes/decisions as local model context',self.use_memory_context),('Record bounded task labels and outcomes',self.save_task_history)):
            tk.Checkbutton(options,text=label,variable=var,bg=COLORS['panel'],fg=COLORS['text'],activebackground=COLORS['panel'],activeforeground=COLORS['text'],selectcolor=COLORS['panel_3'],font=(FONT,9)).pack(anchor='w',padx=12,pady=3)
        GlowButton(options,'SAVE CONTEXT OPTIONS',self._save_memory_options,width=200).pack(anchor='w',padx=12,pady=(3,8))
        query=tk.Frame(page,bg=COLORS['bg']);query.pack(fill='x',pady=(0,8))
        self.memory_query=tk.StringVar()
        tk.Entry(query,textvariable=self.memory_query,bg=COLORS['panel_2'],fg=COLORS['text'],insertbackground=COLORS['text'],font=(FONT,10)).pack(side='left',fill='x',expand=True,padx=(0,8))
        GlowButton(query,'SEARCH / REFRESH',lambda:self._workspace_action('list_memory',{'query':self.memory_query.get()}),width=160).pack(side='left')
        GlowButton(query,'PREVIEW CONTEXT',lambda:self._workspace_action('retrieve_memory',{'query':self.memory_query.get()}),width=165).pack(side='left',padx=(8,0))
        self.memory_status=tk.StringVar(value='Model context is off by default. Saved memory is reference data, never permission or approval.')
        tk.Label(page,textvariable=self.memory_status,bg=COLORS['bg'],fg=COLORS['muted'],wraplength=700,justify='left',font=(FONT,9)).pack(fill='x',pady=(0,8))
        pane=tk.PanedWindow(page,orient='horizontal',bg=COLORS['border'],sashwidth=5,bd=0);pane.pack(fill='both',expand=True)
        left=tk.Frame(pane,bg=COLORS['panel']);right=tk.Frame(pane,bg=COLORS['panel'])
        pane.add(left,minsize=round(200*self.display_scale),width=round(250*self.display_scale))
        pane.add(right,minsize=round(350*self.display_scale))
        scroll=ttk.Scrollbar(left,orient='vertical');scroll.pack(side='right',fill='y')
        self.memory_tree=ttk.Treeview(left,columns=('kind','title'),show='headings',height=8,yscrollcommand=scroll.set)
        self.memory_tree.heading('kind',text='Type');self.memory_tree.heading('title',text='Title / task')
        self.memory_tree.column('kind',width=round(75*self.display_scale),stretch=False)
        self.memory_tree.column('title',width=round(170*self.display_scale))
        self.memory_tree.pack(fill='both',expand=True);scroll.configure(command=self.memory_tree.yview)
        self.memory_tree.bind('<<TreeviewSelect>>',self._select_memory)
        self.memory_rows={};self.memory_generation=None;self.selected_memory=None
        row=tk.Frame(right,bg=COLORS['panel']);row.pack(fill='x',padx=10,pady=8)
        self.memory_kind=tk.StringVar(value='note');self.memory_title=tk.StringVar()
        ttk.Combobox(row,textvariable=self.memory_kind,values=('note','decision'),state='readonly',width=10,style='Purple.TCombobox').pack(side='left')
        tk.Entry(row,textvariable=self.memory_title,bg=COLORS['panel_2'],fg=COLORS['text'],insertbackground=COLORS['text'],font=(FONT,10)).pack(side='left',fill='x',expand=True,padx=8)
        self.memory_body=tk.Text(right,wrap='word',undo=True,bg=COLORS['console'],fg=COLORS['console_text'],insertbackground=COLORS['text'],font=(FONT,10),height=5)
        self.memory_body.pack(fill='both',expand=True,padx=10)
        buttons=tk.Frame(right,bg=COLORS['panel']);buttons.pack(fill='x',padx=10,pady=8)
        for column,(label,command) in enumerate((('NEW ENTRY',self._new_memory),('SAVE ENTRY',self._save_memory_entry),('DELETE ENTRY',self._delete_memory_entry))):
            GlowButton(buttons,label,command,width=115).grid(row=0,column=column,sticky='ew',padx=2)
            buttons.columnconfigure(column,weight=1)
        clear=tk.Frame(page,bg=COLORS['bg']);clear.pack(fill='x',pady=(8,0))
        for column,(label,scope) in enumerate((('CLEAR NOTES / DECISIONS','saved'),('CLEAR HISTORY','history'),('CLEAR ALL MEMORY','all'))):
            GlowButton(clear,label,lambda scope=scope:self._clear_project_memory(scope),width=180,danger=True).grid(row=0,column=column,sticky='ew',padx=3)
            clear.columnconfigure(column,weight=1)

    def _save_memory_options(self):
        if self.busy:
            self.memory_status.set('Wait for the current task before changing context options.')
            return
        options={'use_context':self.use_memory_context.get(),'record_history':self.save_task_history.get()}
        updated=dict(self.config,project_memory=options)
        try:save_config(updated)
        except OSError as exc:
            self.memory_status.set(f'Could not save context options: {exc}')
            return
        self.config=updated;self.tools.memory_options=dict(options)
        self.audit.record('project_memory_options_changed',**options)
        self.memory_status.set('Context/history options saved. The agent cannot change these switches.')

    def _new_memory(self):
        self.selected_memory=None;self.memory_kind.set('note');self.memory_title.set('')
        self.memory_body.configure(state='normal');self.memory_body.delete('1.0','end');self.memory_body.edit_reset()

    def _select_memory(self,event=None):
        selected=self.memory_tree.selection()
        if not selected:return
        row=self.memory_rows.get(selected[0])
        if row is None:return
        self.selected_memory=row
        self.memory_kind.set(row['kind'] if row['kind']!='history' else 'note')
        self.memory_title.set(row['title'])
        self.memory_body.configure(state='normal');self.memory_body.delete('1.0','end')
        self.memory_body.insert('1.0',row['body']);self.memory_body.edit_reset()
        if row['kind']=='history':self.memory_body.configure(state='disabled')

    def _save_memory_entry(self):
        row=self.selected_memory
        if row and row['kind']=='history':
            self.memory_status.set('History is read-only. Choose New Entry to create a note or decision.')
            return
        args={'kind':self.memory_kind.get(),'title':self.memory_title.get(),'body':self.memory_body.get('1.0','end-1c')}
        if row:args.update(entry_id=row['id'],expected_revision=row['revision'])
        self._workspace_action('save_memory',args)

    def _delete_memory_entry(self):
        row=self.selected_memory
        if not row:
            self.memory_status.set('Select an entry before deleting.')
            return
        self._workspace_action('delete_memory',{'entry_id':row['id'],'expected_revision':row['revision']})

    def _clear_project_memory(self,scope):
        if self.memory_generation is None:
            self.memory_status.set('Refresh project memory before clearing.')
            return
        self._workspace_action('clear_memory',{'scope':scope,'expected_generation':self.memory_generation})

    # ---------------- terminal and tests ----------------

    def _build_terminal_page(self):
        page = self._page()
        self.page_frames['terminal'] = page
        panel = tk.Frame(page,bg=COLORS['panel'])
        panel.pack(fill='x',pady=(0,10))
        tk.Label(panel,text='FIXED PYTHON TEST COMMANDS',bg=COLORS['panel'],fg=COLORS['text'],font=(FONT,11,'bold')).pack(anchor='w',padx=14,pady=(12,4))
        tk.Label(panel,text='Host runs use your account access. Approve trusted projects only. Arbitrary commands stay blocked.',bg=COLORS['panel'],fg=COLORS['warning'],wraplength=680,justify='left',font=(FONT,9)).pack(anchor='w',padx=14,pady=(0,8))
        row=tk.Frame(panel,bg=COLORS['panel']);row.pack(fill='x',padx=14,pady=(0,10))
        self.test_framework=tk.StringVar(value='auto')
        ttk.Combobox(row,textvariable=self.test_framework,values=('auto','unittest','pytest'),state='readonly',width=12,style='Purple.TCombobox').pack(side='left')
        tk.Label(row,text='Timeout (seconds)',bg=COLORS['panel'],fg=COLORS['muted'],font=(FONT,9)).pack(side='left',padx=10)
        self.test_timeout=tk.StringVar(value='120')
        tk.Spinbox(row,from_=1,to=600,textvariable=self.test_timeout,width=6,bg=COLORS['panel_2'],fg=COLORS['text'],insertbackground=COLORS['text'],font=(FONT,10)).pack(side='left')
        buttons=tk.Frame(panel,bg=COLORS['panel']);buttons.pack(fill='x',padx=14,pady=(0,12))
        controls=(('DETECT',lambda:self._terminal_action('detect_test_framework')),('PREVIEW',lambda:self._terminal_action('preview_tests')),('RUN TRUSTED TESTS',lambda:self._terminal_action('run_tests')),('EXPORT SANDBOX',lambda:self._terminal_action('export_sandbox_tests')),('CANCEL HOST RUN',self._cancel_tests),('FAILURE TO CODING',self._failure_to_coding))
        for index,(label,command) in enumerate(controls):
            GlowButton(buttons,label,command,width=150).grid(row=index//3,column=index%3,sticky='ew',padx=3,pady=3)
        for column in range(3):buttons.columnconfigure(column,weight=1)
        self.terminal_status=tk.StringVar(value='Idle. Preview does not execute code. Sandbox export requires Windows Sandbox enabled.')
        tk.Label(page,textvariable=self.terminal_status,bg=COLORS['bg'],fg=COLORS['muted'],wraplength=700,justify='left',font=(FONT,9)).pack(fill='x',pady=(0,8))
        self.terminal_preview=tk.Text(page,height=4,wrap='word',bg=COLORS['panel_2'],fg=COLORS['text'],font=(MONO,9),state='disabled')
        self.terminal_preview.pack(fill='x',pady=(0,10))
        host=tk.Frame(page,bg=COLORS['panel']);host.pack(fill='both',expand=True)
        scrollbar=ttk.Scrollbar(host,orient='vertical');scrollbar.pack(side='right',fill='y')
        self.terminal_output=tk.Text(host,wrap='word',bg=COLORS['console'],fg=COLORS['console_text'],font=(MONO,9),state='disabled',yscrollcommand=scrollbar.set)
        self.terminal_output.pack(fill='both',expand=True);scrollbar.configure(command=self.terminal_output.yview)
        self.last_test_result=None
        self._terminal_last=None

    def _terminal_action(self, tool):
        try:
            timeout=int(self.test_timeout.get())
        except ValueError:
            self.terminal_status.set('Timeout must be an integer between 1 and 600.')
            return
        args={} if tool=='detect_test_framework' else {'framework':self.test_framework.get(),'timeout_seconds':timeout}
        if tool=='export_sandbox_tests':args.pop('framework',None)
        self._workspace_action(tool,args)

    def _cancel_tests(self):
        cancelled=self.tools.runner.cancel()
        self.terminal_status.set('Cancellation requested.' if cancelled else 'No active host test process to cancel.')

    def _refresh_terminal(self):
        if self.closing.is_set():return
        snapshot=self.tools.runner.snapshot()
        marker=(snapshot['state'],snapshot['bytes_seen'],snapshot['exit_code'])
        if marker != self._terminal_last and snapshot['state'] != 'idle':
            self._terminal_last=marker
            self.terminal_output.configure(state='normal')
            self.terminal_output.delete('1.0','end')
            self.terminal_output.insert('1.0',('[Earlier output truncated; showing last 100 KB]\n' if snapshot['truncated'] else '')+snapshot['output'])
            self.terminal_output.configure(state='disabled')
            self.terminal_output.see('end')
            if snapshot['state'] in {'starting','running'}:
                self.terminal_status.set(f"Host tests {snapshot['state']}; {snapshot['bytes_seen']} output bytes.")
        self.root.after(100,self._refresh_terminal)

    def _failure_to_coding(self):
        if not self.last_test_result:
            self.terminal_status.set('Run tests first to collect output.')
            return
        import re
        result=self.last_test_result
        paths=[]
        for name in re.findall(r'File "([^"\n]+)", line',result['output']):
            try:
                relative=Path(name).resolve().relative_to(self.workspace.root).as_posix()
                self.tools.files._path(relative)
                if relative not in paths:paths.append(relative)
            except (ValueError,OSError):pass
        self.coding_paths.set(','.join(paths[:8]))
        self.coding_instruction.delete('1.0','end')
        self.coding_instruction.insert('1.0','Investigate these test failures and propose a minimal repair. Do not execute tests or install packages.\n'+result['output'][-6000:])
        self.coding_status.set('Failure context prepared. Select source files, then explicitly Propose Code; nothing was sent to a model.')
        self._show_page('coding')

    # ---------------- coding ----------------

    def _build_coding_page(self):
        page = self._page()
        self.page_frames["coding"] = page
        settings = tk.Frame(page, bg=COLORS["panel"])
        settings.pack(fill="x", pady=(0, 10))
        tk.Label(settings, text="SELECTED SOURCE FILES (comma separated)", bg=COLORS["panel"], fg=COLORS["text"], font=(FONT, 10, "bold")).pack(anchor="w", padx=14, pady=(12, 5))
        self.coding_paths = tk.StringVar()
        tk.Entry(settings, textvariable=self.coding_paths, bg=COLORS["panel_2"], fg=COLORS["text"], insertbackground=COLORS["text"], font=(MONO, 10)).pack(fill="x", padx=14, ipady=5)
        tk.Label(settings, text="Select up to eight UTF-8 files, 80 KB total. Existing proposals must be applied or discarded first.", bg=COLORS["panel"], fg=COLORS["muted"], wraplength=650, justify="left", font=(FONT, 9)).pack(anchor="w", padx=14, pady=(5, 8))
        tk.Label(settings, text="CODING INSTRUCTION", bg=COLORS["panel"], fg=COLORS["text"], font=(FONT, 10, "bold")).pack(anchor="w", padx=14)
        self.coding_instruction = tk.Text(settings, height=3, wrap="word", bg=COLORS["panel_2"], fg=COLORS["text"], insertbackground=COLORS["text"], font=(FONT, 10))
        self.coding_instruction.pack(fill="x", padx=14, pady=(5, 8))
        actions = tk.Frame(settings, bg=COLORS["panel"])
        actions.pack(fill="x", padx=14, pady=(0, 10))
        GlowButton(actions, "ANALYZE SOURCE", lambda: self._coding_action("analyze_code"), width=165).pack(side="left")
        GlowButton(actions, "PROPOSE CODE", lambda: self._coding_action("propose_code_changes"), width=165).pack(side="left", padx=8)
        rename = tk.Frame(page, bg=COLORS["panel"])
        rename.pack(fill="x", pady=(0, 10))
        tk.Label(rename, text="OFFLINE PYTHON RENAME", bg=COLORS["panel"], fg=COLORS["text"], font=(FONT, 10, "bold")).pack(anchor="w", padx=14, pady=(10, 4))
        fields = tk.Frame(rename, bg=COLORS["panel"])
        fields.pack(fill="x", padx=14, pady=(0, 10))
        self.rename_old = tk.StringVar(); self.rename_new = tk.StringVar()
        for column,(label,var) in enumerate((("Old name",self.rename_old),("New name",self.rename_new))):
            tk.Label(fields,text=label,bg=COLORS["panel"],fg=COLORS["muted"],font=(FONT,9)).grid(row=0,column=column,sticky="w")
            tk.Entry(fields,textvariable=var,bg=COLORS["panel_2"],fg=COLORS["text"],insertbackground=COLORS["text"],font=(MONO,9),width=18).grid(row=1,column=column,sticky="ew",padx=(0,8),ipady=5)
            fields.columnconfigure(column,weight=1)
        GlowButton(fields,"STAGE RENAME",lambda:self._coding_action("rename_python_function"),width=150).grid(row=1,column=2)
        self.coding_status = tk.StringVar(value="Analysis works offline. Code generation requires your local LM Studio model.")
        tk.Label(page,textvariable=self.coding_status,bg=COLORS["bg"],fg=COLORS["muted"],wraplength=700,justify="left",font=(FONT,9)).pack(fill="x",pady=(0,8))
        host = tk.Frame(page,bg=COLORS["panel"])
        host.pack(fill="both",expand=True)
        scrollbar = ttk.Scrollbar(host,orient="vertical")
        scrollbar.pack(side="right",fill="y")
        self.coding_output = tk.Text(host,wrap="word",bg=COLORS["console"],fg=COLORS["console_text"],font=(MONO,9),state="disabled",yscrollcommand=scrollbar.set)
        self.coding_output.pack(fill="both",expand=True)
        scrollbar.configure(command=self.coding_output.yview)

    def _coding_action(self, tool):
        paths = [path.strip() for path in self.coding_paths.get().split(",") if path.strip()]
        args = {"paths":paths}
        if tool == "propose_code_changes":
            args['instruction'] = self.coding_instruction.get("1.0","end-1c").strip()
        elif tool == "rename_python_function":
            if len(paths) != 1:
                self.coding_status.set("Offline rename requires exactly one Python file.")
                return
            args = {"path":paths[0],"old":self.rename_old.get().strip(),"new":self.rename_new.get().strip()}
        self._workspace_action(tool,args)

    # ---------------- workspace ----------------

    def _build_workspace_page(self):
        page = self._page()
        self.page_frames["workspace"] = page
        bar = tk.Frame(page, bg=COLORS["bg"])
        bar.pack(fill="x", pady=(0, 8))
        for column, (label, tool) in enumerate((("INDEX FILES", "index_workspace"), ("SAVE SNAPSHOT", "snapshot_workspace"), ("LOAD SNAPSHOTS", "list_snapshots"))):
            GlowButton(bar, label, lambda tool=tool: self._workspace_action(tool, {}), width=155).grid(row=0, column=column, padx=(0, 8))
        self.file_status = tk.StringVar(value="Index a workspace to browse files. Snapshots cover supported UTF-8 files only.")
        tk.Label(page, textvariable=self.file_status, bg=COLORS["bg"], fg=COLORS["muted"], anchor="w", justify="left", wraplength=650, font=(FONT, 9)).pack(fill="x", pady=(0, 8))
        pane = tk.PanedWindow(page, orient="horizontal", bg=COLORS["border"], sashwidth=5, bd=0)
        pane.pack(fill="both", expand=True)
        left = tk.Frame(pane, bg=COLORS["panel"])
        right = tk.Frame(pane, bg=COLORS["panel"])
        pane.add(left, minsize=round(210*self.display_scale), width=round(250*self.display_scale))
        pane.add(right, minsize=round(350*self.display_scale))
        tk.Label(left, text="PROJECT FILES", bg=COLORS["panel"], fg=COLORS["text"], font=(FONT, 10, "bold")).pack(pady=8)
        file_host = tk.Frame(left, bg=COLORS["panel"])
        file_host.pack(fill="both", expand=True)
        self.file_tree = ttk.Treeview(file_host, columns=("path", "bytes"), show="headings", height=8)
        self.file_tree.heading("path", text="File")
        self.file_tree.heading("bytes", text="Bytes")
        self.file_tree.column("path", width=round(180*self.display_scale))
        self.file_tree.column("bytes", width=round(70*self.display_scale), stretch=False)
        scroll = ttk.Scrollbar(file_host, orient="vertical", command=self.file_tree.yview)
        scroll.pack(side="right", fill="y")
        self.file_tree.configure(yscrollcommand=scroll.set)
        self.file_tree.pack(fill="both", expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self._open_selected_file)
        tk.Label(left, text="SNAPSHOTS", bg=COLORS["panel"], fg=COLORS["text"], font=(FONT, 10, "bold")).pack(pady=8)
        snapshot_host = tk.Frame(left, bg=COLORS["panel"])
        snapshot_host.pack(fill="x")
        self.snapshot_tree = ttk.Treeview(snapshot_host, columns=("id", "kind"), show="headings", height=4)
        snapshot_scroll = ttk.Scrollbar(snapshot_host, orient="vertical", command=self.snapshot_tree.yview)
        snapshot_scroll.pack(side="right", fill="y")
        self.snapshot_tree.configure(yscrollcommand=snapshot_scroll.set)
        self.snapshot_tree.heading("id", text="Snapshot ID")
        self.snapshot_tree.heading("kind", text="State")
        self.snapshot_tree.column("id", width=130)
        self.snapshot_tree.column("kind", width=100)
        self.snapshot_tree.pack(fill="x")
        GlowButton(left, "REVIEW RESTORE", self._review_restore, width=160).pack(pady=8)
        row = tk.Frame(right, bg=COLORS["panel"])
        row.pack(fill="x", padx=10, pady=10)
        tk.Label(row, text="File path", bg=COLORS["panel"], fg=COLORS["muted"], font=(FONT, 9)).pack(side="left")
        self.editor_path = tk.StringVar()
        tk.Entry(row, textvariable=self.editor_path, bg=COLORS["panel_2"], fg=COLORS["text"], insertbackground=COLORS["text"], font=(MONO, 9)).pack(side="left", fill="x", expand=True, padx=8)
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True, padx=10)
        self.file_notebook = notebook
        editor_host = tk.Frame(notebook, bg=COLORS["panel"])
        review_host = tk.Frame(notebook, bg=COLORS["panel"])
        notebook.add(editor_host, text="File preview / edit")
        notebook.add(review_host, text="Change review")
        def text_area(host):
            text = tk.Text(host, wrap="none", undo=True, bg=COLORS["console"], fg=COLORS["console_text"], insertbackground=COLORS["text"], font=(MONO, 10), bd=1, relief="sunken")
            vertical = ttk.Scrollbar(host, orient="vertical", command=text.yview)
            horizontal = ttk.Scrollbar(host, orient="horizontal", command=text.xview)
            host.rowconfigure(0, weight=1); host.columnconfigure(0, weight=1)
            text.grid(row=0, column=0, sticky="nsew")
            vertical.grid(row=0, column=1, sticky="ns"); horizontal.grid(row=1, column=0, sticky="ew")
            text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            return text
        self.file_editor = text_area(editor_host)
        self.change_review = text_area(review_host)
        self.change_review.configure(state="disabled")
        self.pending_review = None
        buttons = tk.Frame(right, bg=COLORS["panel"])
        buttons.pack(fill="x", padx=10, pady=10)
        actions = (("STAGE EDIT", self._stage_editor), ("REVIEW CHANGES", lambda: self._workspace_action("review_changes", {})),
                   ("APPLY REVIEWED", self._apply_reviewed), ("DISCARD PROPOSAL", lambda: self._workspace_action("discard_changes", {})))
        for index, (label, callback) in enumerate(actions):
            GlowButton(buttons, label, callback, width=150).grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
        buttons.columnconfigure(0, weight=1); buttons.columnconfigure(1, weight=1)

    def _workspace_action(self, tool, args):
        if self.busy:
            return
        self.busy = True
        self.run_button.config_state("disabled")
        self.status_var.set("SAFE MODE • RUNNING")
        self.card_agent.set("Working")
        registry = self.tools
        def worker():
            try:
                result = registry.execute(tool, args)
                if tool not in {'list_memory','retrieve_memory','save_memory','delete_memory','clear_memory'}:
                    registry.record_history(tool,[({'tool':tool},result)])
                self.ui_events.put(lambda: self._workspace_finished(tool, args, result))
            except Exception as exc:
                from .tools import ToolResult
                result = ToolResult(False, f"{type(exc).__name__}: {exc}")
                self.ui_events.put(lambda result=result: self._workspace_finished(tool, args, result))
        threading.Thread(target=worker, daemon=True).start()

    def _workspace_finished(self, tool, args, result):
        self.busy = False
        self.run_button.config_state("normal")
        self.status_var.set("SAFE MODE • READY")
        self.card_agent.set("Idle")
        self.file_status.set(result.message)
        if tool in {'preview_web','fetch_web','list_web_sources','read_web_source','create_research_brief','clear_web_sources'}:
            self.research_status.set(result.message)
            if result.ok and tool in {'fetch_web','read_web_source','preview_web'}:
                self.web_text.configure(state='normal');self.web_text.delete('1.0','end')
                self.web_text.insert('1.0',json.dumps(result.data,indent=2,ensure_ascii=False));self.web_text.configure(state='disabled')
                if tool=='fetch_web':
                    self.source_cache_ids=None
                    source=result.data;self.source_rows[source['id']]=source
                    self.web_sources.insert('','end',iid=source['id'],values=(source['title'],source['url']))
            elif result.ok and tool=='list_web_sources':
                self.source_rows={row['id']:row for row in result.data};self.source_cache_ids=list(self.source_rows)
                self.web_sources.delete(*self.web_sources.get_children())
                for row in result.data:self.web_sources.insert('','end',iid=row['id'],values=(row['title'],row['url']))
            elif result.ok and tool=='create_research_brief':
                self.research_draft=result.data
                self.research_brief_text.configure(state='normal');self.research_brief_text.delete('1.0','end')
                self.research_brief_text.insert('1.0',result.data['markdown']);self.research_brief_text.configure(state='disabled')
                self.research_notebook.select(1)
            elif result.ok and tool=='clear_web_sources':
                self.source_rows={};self.source_cache_ids=None;self.research_draft=None;self.web_sources.delete(*self.web_sources.get_children())
                self.research_brief_text.configure(state='normal');self.research_brief_text.delete('1.0','end');self.research_brief_text.configure(state='disabled')
                self.web_text.configure(state='normal');self.web_text.delete('1.0','end');self.web_text.configure(state='disabled')
        elif tool in {'list_memory','retrieve_memory','save_memory','delete_memory','clear_memory'}:
            self.memory_status.set(result.message)
            if result.ok and tool=='list_memory':
                self.memory_rows={row['id']:row for row in result.data['entries']}
                self.memory_generation=result.data['generation']
                self.memory_tree.delete(*self.memory_tree.get_children())
                for row in result.data['entries']:
                    self.memory_tree.insert('', 'end',iid=row['id'],values=(row['kind'],row['title']))
                self._new_memory()
            elif result.ok and tool=='retrieve_memory':
                self._new_memory()
                self.memory_title.set('Context preview (not saved)')
                self.memory_body.insert('1.0',json.dumps(result.data,indent=2,ensure_ascii=False))
                self.memory_body.configure(state='disabled')
            elif result.ok:
                self.memory_generation=None
                self.memory_rows={};self.memory_tree.delete(*self.memory_tree.get_children())
                self._new_memory()
                self.memory_status.set(result.message+' Refresh to load current entries.')
        elif tool in {'detect_test_framework','preview_tests','run_tests','export_sandbox_tests'}:
            self.terminal_status.set(result.message)
            self.terminal_preview.configure(state='normal')
            self.terminal_preview.delete('1.0','end')
            if tool=='run_tests' and isinstance(result.data,dict):
                self.last_test_result=result.data
                display={key:value for key,value in result.data.items() if key != 'output'}
            else:
                display=result.data if result.ok else {'error':result.message}
            self.terminal_preview.insert('1.0',json.dumps(display,indent=2,ensure_ascii=False))
            self.terminal_preview.configure(state='disabled')
        elif tool in {"analyze_code","propose_code_changes","rename_python_function"}:
            self.coding_status.set(result.message)
            self.coding_output.configure(state="normal")
            self.coding_output.delete("1.0","end")
            display = result.data if result.ok else {"error":result.message}
            if isinstance(display,dict) and 'review' in display:
                self.pending_review = display['review']
                self.change_review.configure(state="normal")
                self.change_review.delete("1.0","end")
                self.change_review.insert("1.0",display['review']['diff'])
                self.change_review.configure(state="disabled")
                display = {key:value for key,value in display.items() if key != 'review'}
                display['next_step'] = 'Open Workspace, read the Change Review tab, then Apply Reviewed.'
                self.file_notebook.select(1)
            self.coding_output.insert("1.0",json.dumps(display,indent=2,ensure_ascii=False))
            self.coding_output.configure(state="disabled")
        elif result.ok and tool == "index_workspace":
            self.file_tree.delete(*self.file_tree.get_children())
            for row in result.data['files']:
                self.file_tree.insert("", "end", values=(row['path'], row['bytes']))
            projects = result.data['project_types']
            self.file_status.set(result.message + (" Detected: " + ", ".join(projects) if projects else ""))
        elif result.ok and tool == "preview_file":
            self.editor_path.set(args['path'])
            self.file_editor.delete("1.0", "end")
            self.file_editor.insert("1.0", result.data)
            self.file_editor.edit_reset()
            self.file_notebook.select(0)
        elif result.ok and tool in {"stage_changes", "review_changes", "prepare_restore"}:
            self.pending_review = result.data
            self.change_review.configure(state="normal")
            self.change_review.delete("1.0", "end")
            self.change_review.insert("1.0", result.data['diff'])
            self.change_review.configure(state="disabled")
            self.file_notebook.select(1)
        elif result.ok and tool == "list_snapshots":
            self.snapshot_tree.delete(*self.snapshot_tree.get_children())
            for row in result.data:
                self.snapshot_tree.insert("", "end", values=(row['id'], row['kind'] + " / " + row['status']))
        elif result.ok and tool in {"apply_changes", "restore_snapshot", "discard_changes"}:
            self.pending_review = None
            self.change_review.configure(state="normal")
            self.change_review.delete("1.0", "end")
            self.change_review.configure(state="disabled")
        if result.ok and tool == "snapshot_workspace":
            self.file_status.set(result.message + " ID: " + result.data['snapshot'])
        self._refresh_activity()
        self._refresh_status_cards()

    def _open_selected_file(self, event=None):
        selected = self.file_tree.selection()
        if selected:
            path = self.file_tree.item(selected[0], "values")[0]
            self._workspace_action("preview_file", {"path":path})

    def _stage_editor(self):
        path = self.editor_path.get().strip()
        if not path:
            self.file_status.set("Enter a relative file path first.")
            return
        self._workspace_action("stage_changes", {"changes":{path:self.file_editor.get("1.0", "end-1c")}})

    def _review_restore(self):
        selected = self.snapshot_tree.selection()
        if selected:
            snapshot = self.snapshot_tree.item(selected[0], "values")[0]
            self._workspace_action("prepare_restore", {"snapshot_id":snapshot})
        else:
            self.file_status.set("Load snapshots and select one first.")

    def _apply_reviewed(self):
        if self.pending_review is None:
            self.file_status.set("Review the pending changes before applying.")
            return
        tool = "restore_snapshot" if self.pending_review['kind'] == "restore" else "apply_changes"
        self._workspace_action(tool, {"proposal_id":self.pending_review['id']})

    # ---------------- permissions ----------------

    def _build_permissions_page(self):
        page = self._page()
        self.page_frames["permissions"] = page

        intro = tk.Frame(page, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        intro.pack(fill="x", pady=(0, 12))
        tk.Label(intro, text="Permission Center", bg=COLORS["panel"], fg=COLORS["text"],
                 font=(FONT, 13, "bold")).pack(anchor="w", padx=16, pady=(14, 3))
        tk.Label(
            intro,
            text="ALLOW runs automatically • ASK requires your approval • DENY blocks the action. "
                 "The agent cannot modify these policies itself.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(FONT, 9),
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 14))

        bottom = tk.Frame(page, bg=COLORS["bg"])
        bottom.pack(side="bottom", fill="x", pady=12)
        GlowButton(bottom, "SAVE PERMISSIONS", self._save_permissions, width=200).pack(side="left")
        permission_scroll = ScrollPanel(page)
        permission_scroll.pack(fill="both", expand=True)
        list_card = permission_scroll.body

        self.permission_vars = {}
        descriptions = {
            "list_files": "View file names inside the selected workspace.",
            "read_file": "Read file contents inside the workspace.",
            "write_file": "Stage writes; applying always requires review and approval.",
            "analyze_code": "Parse selected source files without running project code.",
            "propose_code_changes": "Send selected source context to your local model; stage validated edits.",
            "rename_python_function": "Stage a conservative single-file Python function rename.",
            "index_workspace": "Index project files; skip linked paths and dependency/cache folders.",
            "preview_file": "Preview UTF-8 workspace files up to 1 MB.",
            "stage_changes": "Prepare text changes without changing workspace files.",
            "review_changes": "Read the current proposed change diff.",
            "discard_changes": "Discard the pending proposal without changing files.",
            "snapshot_workspace": "Save a local snapshot of supported UTF-8 workspace files.",
            "list_snapshots": "List this workspace's recovery snapshots.",
            "prepare_restore": "Prepare a rollback diff without changing files.",
            "restore_snapshot": "Approval-gated restore; may remove files created by a change set.",
            "run_tests": "Trusted host tests always require approval; timeout/output limits apply.",
            "list_memory": "Review local notes, decisions and outcome history.",
            "retrieve_memory": "Retrieve relevant saved notes/decisions as reference context.",
            "record_task_history": "Store bounded task labels and outcomes, not file contents/output.",
            "save_memory": "Save/edit always requires approval of local reference notes or decisions.",
            "delete_memory": "Approval-gated deletion of one project-memory entry.",
            "clear_memory": "Approval-gated clearing of saved notes, history, or both.",
            "detect_test_framework": "Detect supported Python unittest/pytest configuration.",
            "preview_tests": "Preview the exact fixed test command without execution.",
            "export_sandbox_tests": "Export a fixed unittest session for Windows Sandbox; does not launch.",
            "run_command": "Unavailable until an isolated command runner exists.",
            "delete_file": "Delete files. Disabled in v0.1.x tool registry.",
            "install_package": "Install packages or applications.",
            "network_access": "Web fetches always require approval; private-network access stays blocked.",
            "preview_web": "Check URL/domain policy without DNS or network traffic.",
            "fetch_web": "Retrieve bounded public HTTPS text after Network Access approval.",
            "list_web_sources": "List retained source metadata for this project.",
            "read_web_source": "Read cached source text without making a network request.",
            "create_research_brief": "Approval-gated draft using cached sources and optional local model.",
            "clear_web_sources": "Approval-gated clearing of reviewed source records.",
            "git_push": "Push local Git changes to a remote repository.",
            "publish_release": "Publish external software releases.",
        }

        for idx, (action, policy) in enumerate(sorted(self.permissions.snapshot().items())):
            row = tk.Frame(list_card, bg=COLORS["panel_2"] if idx % 2 == 0 else COLORS["panel"])
            row.pack(fill="x", padx=12, pady=(8 if idx == 0 else 0, 0))
            row.columnconfigure(1, weight=1)

            tk.Label(row, text=action.replace("_", " ").title(), bg=row["bg"], fg=COLORS["text"],
                     font=(FONT, 9, "bold"), width=22, anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=10)
            description = tk.Label(row, text=descriptions.get(action, ""), bg=row["bg"], fg=COLORS["muted"],
                     font=(FONT, 8), anchor="w", justify="left", wraplength=230)
            description.grid(row=0, column=1, sticky="ew", padx=8)
            description.bind("<Configure>", lambda event, label=description: label.configure(wraplength=max(80, event.width)))

            var = tk.StringVar(value=policy)
            self.permission_vars[action] = var
            box = ttk.Combobox(row, textvariable=var, values=["allow", "ask", "deny"],
                               state="readonly", width=10, style="Purple.TCombobox")
            box.grid(row=0, column=2, sticky="e", padx=12, pady=7)


    # ---------------- activity ----------------

    def _build_activity_page(self):
        page = self._page()
        self.page_frames["activity"] = page

        panel = tk.Frame(page, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        panel.pack(fill="both", expand=True)

        bar = tk.Frame(panel, bg=COLORS["panel"])
        bar.pack(fill="x", padx=14, pady=12)
        tk.Label(bar, text="AUDIT / ACTIVITY LOG", bg=COLORS["panel"], fg=COLORS["text"],
                 font=(FONT, 11, "bold")).pack(side="left")
        tk.Button(
            bar, text="Refresh", command=self._refresh_activity,
            bg=COLORS["panel_3"], fg=COLORS["text"], activebackground=COLORS["accent_dark"],
            activeforeground="white", relief="flat", bd=0, cursor="hand2", padx=12, pady=5
        ).pack(side="right")

        self.activity = tk.Text(
            panel,
            wrap="none",
            bg=COLORS["console"],
            fg=COLORS["console_text"],
            insertbackground=COLORS["accent_bright"],
            relief="sunken",
            bd=1,
            padx=12,
            pady=10,
            font=(MONO, 8),
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        self.activity.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ---------------- settings ----------------

    def _build_settings_page(self):
        page = self._page()
        self.page_frames["settings"] = page
        settings_scroll = ScrollPanel(page)
        settings_scroll.pack(fill="both", expand=True)
        page = settings_scroll.body

        panel = tk.Frame(page, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        panel.pack(fill="x")

        tk.Label(panel, text="LOCAL MODEL", bg=COLORS["panel"], fg=COLORS["text"],
                 font=(FONT, 12, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 3), columnspan=2)
        tk.Label(panel, text="Connect Purple Dragon AI Agent to an OpenAI-compatible LM Studio local server.",
                 bg=COLORS["panel"], fg=COLORS["muted"], font=(FONT, 8)).grid(
                    row=1, column=0, sticky="w", padx=16, pady=(0, 14), columnspan=2
                 )

        lm = self.config.get("lm_studio", {})
        self.lm_enabled = tk.BooleanVar(value=bool(lm.get("enabled", False)))
        self.lm_endpoint = tk.StringVar(value=lm.get("endpoint", "http://127.0.0.1:1234/v1/chat/completions"))
        self.lm_model = tk.StringVar(value=lm.get("model", "local-model"))

        cb = tk.Checkbutton(
            panel,
            text="Enable LM Studio connector",
            variable=self.lm_enabled,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            activebackground=COLORS["panel"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel_3"],
            font=(FONT, 9, "bold"),
        )
        cb.grid(row=2, column=0, sticky="w", padx=16, pady=8, columnspan=2)

        tk.Label(panel, text="Endpoint", bg=COLORS["panel"], fg=COLORS["muted"],
                 font=(FONT, 9)).grid(row=3, column=0, sticky="w", padx=16, pady=8)
        endpoint = tk.Entry(
            panel, textvariable=self.lm_endpoint, bg=COLORS["panel_2"], fg=COLORS["text"],
            insertbackground=COLORS["accent_bright"], relief="flat", bd=0,
            highlightbackground=COLORS["border"], highlightthickness=1,
            font=(MONO, 9)
        )
        endpoint.grid(row=3, column=1, sticky="ew", padx=(0,16), pady=8, ipady=8)

        tk.Label(panel, text="Model", bg=COLORS["panel"], fg=COLORS["muted"],
                 font=(FONT, 9)).grid(row=4, column=0, sticky="w", padx=16, pady=8)
        model = tk.Entry(
            panel, textvariable=self.lm_model, bg=COLORS["panel_2"], fg=COLORS["text"],
            insertbackground=COLORS["accent_bright"], relief="flat", bd=0,
            highlightbackground=COLORS["border"], highlightthickness=1,
            font=(MONO, 9)
        )
        model.grid(row=4, column=1, sticky="ew", padx=(0,16), pady=8, ipady=8)

        panel.columnconfigure(1, weight=1)

        btns = tk.Frame(panel, bg=COLORS["panel"])
        btns.grid(row=5, column=0, columnspan=2, sticky="w", padx=16, pady=(12,16))
        GlowButton(btns, "SAVE SETTINGS", self._save_settings, width=180).pack(side="left")

        workspace_panel = tk.Frame(page, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        workspace_panel.pack(fill="x", pady=14)
        tk.Label(workspace_panel, text="WORKSPACE", bg=COLORS["panel"], fg=COLORS["text"],
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=16, pady=(16,3))
        settings_path = tk.Label(workspace_panel, textvariable=self.workspace_var, bg=COLORS["panel"], fg=COLORS["muted"],
                 font=(MONO, 8), anchor="w", justify="left", wraplength=400)
        settings_path.pack(fill="x", padx=16, pady=(0,10))
        settings_path.bind("<Configure>", lambda event: settings_path.configure(wraplength=max(100, event.width)))
        GlowButton(workspace_panel, "CHANGE WORKSPACE", self._choose_workspace, width=190).pack(anchor="w", padx=16, pady=(0,16))

    # ---------------- about ----------------

    def _build_about_page(self):
        page = self._page()
        self.page_frames["about"] = page

        panel = tk.Frame(page, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=1)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text="PD", bg=COLORS["accent_dark"], fg="white",
                 font=(FONT, 28, "bold"), padx=18, pady=10).pack(pady=(45, 16))

        tk.Label(panel, text="PURPLE DRAGON AI AGENT", bg=COLORS["panel"], fg=COLORS["text"],
                 font=(FONT, 20, "bold")).pack()
        tk.Label(panel, text=f"Version {self.config['version']} • Research/Web Agent",
                 bg=COLORS["panel"], fg=COLORS["accent_bright"],
                 font=(FONT, 10, "bold")).pack(pady=(5, 18))

        text = (
            "A local-first, permission-controlled autonomous AI agent foundation.\n"
            "Designed so the agent can perform useful work while sensitive actions remain\n"
            "approval-gated or blocked by policy."
        )
        tk.Label(panel, text=text, justify="center", bg=COLORS["panel"], fg=COLORS["muted"],
                 font=(FONT, 10)).pack()

        tk.Frame(panel, bg=COLORS["border"], height=1, width=420).pack(pady=26)
        tk.Label(panel, text="Created by Kyle Austin Hillier", bg=COLORS["panel"], fg=COLORS["text"],
                 font=(FONT, 10, "bold")).pack()
        tk.Label(panel, text="SAFE MODE remains the default operating boundary.",
                 bg=COLORS["panel"], fg=COLORS["success"], font=(FONT, 9, "bold")).pack(pady=8)

    # ---------------- actions ----------------

    def _refresh_status_cards(self):
        lm = self.config.get("lm_studio", {})
        if lm.get("enabled", False):
            model = lm.get("model", "local-model") or "Local Model"
            self.card_model.set(model)
        else:
            self.card_model.set("Fallback Planner")

        try:
            count = len(self.workspace.list_files(limit=999))
            self.card_workspace.set(f"Ready • {count} file(s)")
        except Exception:
            self.card_workspace.set("Unavailable")

        if hasattr(self, 'local_model_status'):
            enabled = lm.get('enabled', False)
            self.local_model_status.set((f"{lm.get('model', 'Local Model')}\nConnector enabled · connection unverified" if enabled else 'Fallback Planner\nLM Studio connector disabled') + '\nGPU / VRAM / context: not reported')
            events = self.audit.tail(5)
            self.recent_summary.set('\n\n'.join(entry.get('event','Action').replace('_',' ').title() for entry in reversed(events)) or 'No actions yet')

        snapshot = self.permissions.snapshot()
        asks = sum(1 for v in snapshot.values() if v == "ask")
        denies = sum(1 for v in snapshot.values() if v == "deny")
        self.card_permissions.set(f"{asks} Ask • {denies} Deny")
        if self.status_var.get().endswith("READY"):
            self.card_agent.set("Idle")

    def _approval_callback(self, action: str, context: dict) -> bool:
        if threading.current_thread() is threading.main_thread():
            return self._approval_dialog(action, context)

        result = {"value": False}
        event = threading.Event()

        def ask():
            try:
                if not self.closing.is_set():
                    result["value"] = self._approval_dialog(action, context)
            finally:
                event.set()

        self.ui_events.put(ask)
        while not event.wait(0.1):
            if self.closing.is_set():
                return False
        return result["value"]

    def _approval_dialog(self, action: str, context: dict) -> bool:
        pretty = json.dumps(context.get("args", {}), indent=2)
        return messagebox.askyesno(
            "Purple Dragon AI • Approval Required",
            f"SAFE MODE blocked automatic execution.\n\n"
            f"Requested action:\n{action}\n\n"
            f"Arguments:\n{pretty}\n\n"
            f"{context.get('warning', '')}\n\n"
            f"Approve this action?",
            parent=self.root,
        )

    def _run_task(self):
        if self.busy:
            return
        task = self.task.get("1.0", "end").strip()
        if not task:
            return

        self.busy = True
        agent = self.agent
        self.run_button.config_state("disabled")
        self.status_var.set("SAFE MODE • RUNNING")
        self.card_agent.set("Working")
        self.output.delete("1.0", "end")
        self.output.insert("end", f"> Task\n{task}\n\n")

        def execute_task():
            self.audit.record("task_started", task=task)
            run = agent.run(task)
            lines = [f"> Plan\n{run.summary}", ""]
            for index, (step, result) in enumerate(run.results, start=1):
                state = "OK" if result.ok else "BLOCKED / FAILED"
                lines.append(f"[{index}] {step.get('tool')}  [{state}]")
                lines.append(result.message)
                if result.data is not None:
                    data = result.data
                    if isinstance(data, list):
                        data = "\n".join(map(str, data))
                    lines.append(str(data))
                lines.append("")
            if not run.results:
                lines.append("No executable steps were produced.")
            for step,result in run.results:
                if step.get('tool')=='run_tests' and isinstance(result.data,dict):
                    self.ui_events.put(lambda data=result.data:setattr(self,'last_test_result',data))
            self.audit.record("task_finished", task=task, steps=len(run.results))
            self.ui_events.put(lambda: self._task_finished("\n".join(lines)))

        def worker():
            try:
                execute_task()
            except Exception as exc:
                text = f"Task failed: {type(exc).__name__}: {exc}"
                self.ui_events.put(lambda text=text: self._task_finished(text))

        threading.Thread(target=worker, daemon=True).start()

    def _task_finished(self, text: str):
        self.busy = False
        self.output.insert("end", text)
        self.output.see("end")
        self.run_button.config_state("normal")
        self.status_var.set("SAFE MODE • READY")
        self.card_agent.set("Idle")
        self._refresh_activity()
        self._refresh_status_cards()

    def _save_permissions(self):
        if self.busy:
            messagebox.showinfo("Task running", "Wait for the current task to finish before changing configuration.", parent=self.root)
            return
        for action, var in self.permission_vars.items():
            self.permissions.set_policy(action, var.get())
        self.config["permissions"] = self.permissions.snapshot()
        save_config(self.config)
        self.audit.record("permissions_changed", policies=self.config["permissions"])
        self._refresh_status_cards()
        messagebox.showinfo("Purple Dragon AI", "Permission policies saved.", parent=self.root)

    def _save_settings(self):
        if self.busy:
            messagebox.showinfo("Task running", "Wait for the current task to finish before changing configuration.", parent=self.root)
            return
        try:
            LMStudioClient(self.lm_endpoint.get().strip(), self.lm_model.get().strip())
        except ValueError as exc:
            messagebox.showerror("Invalid local endpoint", str(exc), parent=self.root)
            return
        self.config["lm_studio"]["enabled"] = self.lm_enabled.get()
        self.config["lm_studio"]["endpoint"] = self.lm_endpoint.get().strip()
        self.config["lm_studio"]["model"] = self.lm_model.get().strip()
        save_config(self.config)
        self.agent = self._make_agent()
        self.audit.record("settings_changed", lm_enabled=self.lm_enabled.get())
        self._refresh_status_cards()
        messagebox.showinfo("Purple Dragon AI", "Settings saved and model connector reloaded.", parent=self.root)

    def _choose_workspace(self):
        if self.busy:
            messagebox.showinfo("Task running", "Wait for the current task to finish before changing configuration.", parent=self.root)
            return
        path = filedialog.askdirectory(parent=self.root, title="Select Project Workspace")
        if not path:
            return
        self.workspace = Workspace(Path(path))
        self.config["workspace"] = str(self.workspace.root)
        save_config(self.config)
        self.tools = ToolRegistry(self.workspace, self.permissions, self.audit)
        self.agent = self._make_agent()
        self.workspace_var.set(str(self.workspace.root))
        self.pending_review = None
        self.source_rows={};self.source_cache_ids=None;self.research_draft=None
        self.web_sources.delete(*self.web_sources.get_children())
        self.web_text.configure(state='normal');self.web_text.delete('1.0','end');self.web_text.configure(state='disabled')
        self.research_brief_text.configure(state='normal');self.research_brief_text.delete('1.0','end');self.research_brief_text.configure(state='disabled')
        self.research_status.set('Workspace changed. Load this project’s retained sources.')
        self.memory_rows={};self.memory_generation=None;self.memory_tree.delete(*self.memory_tree.get_children())
        self._new_memory();self.memory_query.set('');self.memory_status.set('Workspace changed. Refresh to load this project’s local memory.')
        self.last_test_result = None
        self._terminal_last = None
        self.terminal_output.configure(state='normal')
        self.terminal_output.delete('1.0','end')
        self.terminal_output.configure(state='disabled')
        self.terminal_preview.configure(state='normal')
        self.terminal_preview.delete('1.0','end')
        self.terminal_preview.configure(state='disabled')
        self.terminal_status.set('Workspace changed. Detect or preview tests for this project.')
        self.file_tree.delete(*self.file_tree.get_children())
        self.snapshot_tree.delete(*self.snapshot_tree.get_children())
        self.editor_path.set("")
        self.coding_paths.set("")
        self.coding_status.set("Workspace changed. Select source files from the new project.")
        self.coding_output.configure(state="normal")
        self.coding_output.delete("1.0","end")
        self.coding_output.configure(state="disabled")
        self.file_editor.delete("1.0", "end")
        self.change_review.configure(state="normal")
        self.change_review.delete("1.0", "end")
        self.change_review.configure(state="disabled")
        self.file_status.set("Workspace changed. Index files and load snapshots for this project.")
        self.audit.record("workspace_changed", workspace=str(self.workspace.root))
        self._refresh_status_cards()

    def _refresh_activity(self):
        if not hasattr(self, "activity"):
            return
        self.activity.delete("1.0", "end")
        for item in self.audit.tail(300):
            self.activity.insert(
                "end",
                f"{item.get('timestamp')}  {item.get('event')}  "
                f"{json.dumps(item.get('details', {}), ensure_ascii=False)}\n",
            )
        self.activity.see("end")

    def run(self):
        self.root.mainloop()
