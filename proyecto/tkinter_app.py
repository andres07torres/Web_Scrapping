import os
import sys
import json
import csv
import threading
import asyncio
from tkinter import ttk, messagebox, filedialog
import tkinter as tk
from dotenv import load_dotenv
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.scraper import run_scrape, validate_url, cleanup_scraper, clean_session_file

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def get_session_path(url_or_domain):
    if not url_or_domain:
        return os.path.join(DATA_DIR, 'session_state_aulagradob.json') # Default fallback
    
    if "://" in url_or_domain:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url_or_domain)
            domain = parsed.netloc.lower()
        except Exception:
            domain = "aulagradob.unemi.edu.ec"
    else:
        domain = url_or_domain.lower()
        
    if "aulagrado.unemi.edu.ec" in domain:
        return os.path.join(DATA_DIR, 'session_state_aulagrado.json')
    else:
        return os.path.join(DATA_DIR, 'session_state_aulagradob.json')

# Migrate old session file if exists to the new domain-specific format
old_session_path = os.path.join(DATA_DIR, 'session_state.json')
new_session_path = os.path.join(DATA_DIR, 'session_state_aulagradob.json')
if os.path.exists(old_session_path) and not os.path.exists(new_session_path):
    try:
        import shutil
        shutil.copy(old_session_path, new_session_path)
    except Exception:
        pass

# Clean both session files on startup
clean_session_file(os.path.join(DATA_DIR, 'session_state_aulagrado.json'))
clean_session_file(os.path.join(DATA_DIR, 'session_state_aulagradob.json'))

COLORS = {
    "bg": "#f0f2f5",
    "header_bg": "#2c3e50",
    "header_fg": "#ffffff",
    "card": "#ffffff",
    "accent": "#3498db",
    "accent_hover": "#2980b9",
    "success": "#27ae60",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "border": "#dcdde1",
    "text": "#2c3e50",
    "text_secondary": "#7f8c8d",
    "row_even": "#f8f9fa",
    "row_odd": "#ffffff",
}

_MAX_ERROR_LEN = 80


class ScrapingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Scrapper")
        self.root.geometry("900x580")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        self.tasks = []
        self.scraping = False
        self._style = ttk.Style()
        self._setup_styles()
        self._validate_env()
        self._build_ui()
        self._load_saved()
        self._update_counter()
        self._update_session_indicator()

    def _validate_env(self):
        missing = []
        for var in ("MOODLE_USERNAME", "MOODLE_PASSWORD"):
            if not os.getenv(var):
                missing.append(var)
        if missing:
            msg = "Faltan variables de entorno:\n" + "\n".join(f"  \u2022 {v}" for v in missing)
            msg += "\n\nVerifica tu archivo .env en la raiz del proyecto."
            messagebox.showwarning("Configuracion incompleta", msg)

    def _setup_styles(self):
        self._style.theme_use("clam")
        self._style.configure("Header.TFrame", background=COLORS["header_bg"])
        self._style.configure("Card.TFrame", background=COLORS["card"],
                              relief="solid", borderwidth=1)
        self._style.configure("Accent.TButton", background=COLORS["accent"],
                              foreground="#ffffff", borderwidth=0,
                              focusthickness=3, focuscolor=COLORS["accent"])
        self._style.map("Accent.TButton",
                        background=[("active", COLORS["accent_hover"]),
                                    ("disabled", "#bdc3c7")])
        self._style.configure("Toolbar.TFrame", background=COLORS["card"])
        self._style.configure("StatusBar.TLabel", background=COLORS["bg"],
                              foreground=COLORS["text_secondary"],
                              font=("Segoe UI", 9))
        self._style.configure("Counter.TLabel", background=COLORS["card"],
                              foreground=COLORS["text_secondary"],
                              font=("Segoe UI", 9))
        self._style.configure("Treeview", rowheight=30,
                              font=("Segoe UI", 10),
                              background=COLORS["row_odd"],
                              fieldbackground=COLORS["row_odd"],
                              foreground=COLORS["text"])
        self._style.map("Treeview",
                        background=[("selected", COLORS["accent"])],
                        foreground=[("selected", "#ffffff")])
        self._style.configure("Treeview.Heading",
                              font=("Segoe UI", 10, "bold"),
                              background=COLORS["bg"],
                              foreground=COLORS["text"],
                              relief="flat")
        self._style.map("Treeview.Heading",
                        background=[("active", COLORS["border"])])

    def _build_ui(self):
        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_progress()
        self._build_statusbar()

    def _build_header(self):
        h = ttk.Frame(self.root, style="Header.TFrame")
        h.pack(fill=tk.X)
        inner = tk.Frame(h, bg=COLORS["header_bg"], padx=20, pady=14)
        inner.pack(fill=tk.X)
        tk.Label(inner, text="\ud83d\udccb", font=("Segoe UI", 20),
                 bg=COLORS["header_bg"], fg=COLORS["header_fg"]).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(inner, text="Scrapper",
                 font=("Segoe UI", 16, "bold"),
                 bg=COLORS["header_bg"], fg=COLORS["header_fg"]).pack(side=tk.LEFT)
        tk.Label(inner, text="Desarrollado por Dev Andr\u00e9s Torres",
                 font=("Segoe UI", 8),
                 bg=COLORS["header_bg"], fg="#95a5a6").pack(side=tk.RIGHT)

    def _build_toolbar(self):
        card = ttk.Frame(self.root, style="Card.TFrame", padding=12)
        card.pack(fill=tk.X, padx=12, pady=(10, 0))

        url_frame = tk.Frame(card, bg=COLORS["card"])
        url_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(url_frame, text="URL de la tarea:", font=("Segoe UI", 10),
                 bg=COLORS["card"], fg=COLORS["text"]).pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_frame, font=("Segoe UI", 10))
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.url_entry.bind("<Return>", lambda e: self._scrape())
        self.url_entry.bind("<KeyRelease>", lambda e: self._update_session_indicator())
        clear_btn = tk.Button(url_frame, text="✕",
                              font=("Segoe UI", 9),
                              bg=COLORS["card"], fg=COLORS["text_secondary"],
                              relief="flat", bd=0, padx=4, pady=0,
                              activebackground=COLORS["bg"],
                              cursor="hand2",
                              command=lambda: [self.url_entry.delete(0, tk.END), self._update_session_indicator()])
        clear_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.scrape_btn = ttk.Button(url_frame, text="\u25b6 Scrapear",
                                     style="Accent.TButton",
                                     command=self._scrape)
        self.scrape_btn.pack(side=tk.LEFT)

        btn_frame = tk.Frame(card, bg=COLORS["card"])
        btn_frame.pack(fill=tk.X)

        left = tk.Frame(btn_frame, bg=COLORS["card"])
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        right = tk.Frame(btn_frame, bg=COLORS["card"])
        right.pack(side=tk.RIGHT)

        def _toolbar_btn(text, cmd, parent):
            btn = tk.Button(parent, text=text, command=cmd,
                            font=("Segoe UI", 9),
                            bg=COLORS["card"], fg=COLORS["text"],
                            relief="solid", bd=1,
                            padx=10, pady=3,
                            activebackground=COLORS["bg"],
                            cursor="hand2")
            btn.pack(side=tk.LEFT, padx=2)
            return btn

        _toolbar_btn("+ Manual", self._add_manual, left)
        _toolbar_btn("\u2b07 CSV", self._export_csv, left)
        self.actualizar_btn = _toolbar_btn("\u21bb Actualizar", self._actualizar, left)
        _toolbar_btn("\u2753", self._show_help, left)

        sep = ttk.Separator(right, orient=tk.VERTICAL)
        sep.pack(side=tk.RIGHT, padx=4, fill=tk.Y)
        _toolbar_btn("\u274c Limpiar Todo", self._clear_all, right)
        _toolbar_btn("\u23f9 Salir", self._quit, right)
        self._session_indicator = tk.Canvas(right, width=12, height=12,
                                             bg=COLORS["card"],
                                             highlightthickness=0)
        self._session_indicator.pack(side=tk.RIGHT, padx=(0, 2))
        self._session_dot = self._session_indicator.create_oval(
            2, 2, 10, 10, fill=COLORS["danger"], outline="")
        btn_renew = tk.Button(right, text="Sesi\u00f3n",
                              font=("Segoe UI", 8),
                              bg=COLORS["card"], fg=COLORS["text"],
                              relief="solid", bd=1,
                              padx=6, pady=2,
                              activebackground=COLORS["bg"],
                              cursor="hand2",
                              command=self._renovar_sesion)
        btn_renew.pack(side=tk.RIGHT, padx=2)
        self.counter_label = ttk.Label(right, style="Counter.TLabel")
        self.counter_label.pack(side=tk.RIGHT, padx=(0, 4))

    def _build_table(self):
        self._col_props = [
            ("titulo", "T\u00edtulo", 3, "w"),
            ("materia", "Materia", 2, "w"),
            ("tipo", "Tipo", 1, "center"),
            ("apertura", "Apertura", 1, "center"),
            ("entrega", "Entrega", 1, "center"),
            ("estado", "Estado", 1, "center"),
        ]
        cols = tuple(c[0] for c in self._col_props)
        total_weight = sum(c[2] for c in self._col_props)

        container = ttk.Frame(self.root, style="Card.TFrame", padding=0)
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 0))

        self.tree = ttk.Treeview(container, columns=cols, show="headings",
                                 selectmode="extended")
        for key, text, weight, anchor in self._col_props:
            self.tree.heading(key, text=text)
            self.tree.column(key, minwidth=60, anchor=anchor)

        self._vsb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self._vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Delete>", lambda e: self._delete_selected())
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Configure>", self._on_tree_resize)
        self._tree_initial_width = 0
        self._setup_tags()

    def _setup_tags(self):
        self.tree.tag_configure("even", background=COLORS["row_even"])
        self.tree.tag_configure("odd", background=COLORS["row_odd"])
        self.tree.tag_configure("estado_pendiente",
                                foreground=COLORS["warning"])
        self.tree.tag_configure("estado_completado",
                                foreground=COLORS["success"])
        self.tree.tag_configure("estado_vencido",
                                foreground=COLORS["danger"])

    def _on_tree_resize(self, event):
        if event.width == self._tree_initial_width:
            return
        self._tree_initial_width = event.width
        total_weight = sum(c[2] for c in self._col_props)
        try:
            vsb_w = self._vsb.winfo_width()
        except Exception:
            vsb_w = 20
        avail = event.width - vsb_w - 4
        for key, text, weight, anchor in self._col_props:
            w = max(60, int(avail * weight / total_weight))
            self.tree.column(key, width=w)

    def _build_progress(self):
        pass

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Listo")
        self._status_frame = tk.Frame(self.root, bg=COLORS["bg"])
        self._status_frame.pack(fill=tk.X, pady=(4, 0))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self._status_frame, variable=self.progress_var,
            mode="indeterminate")

        self._status_bar = ttk.Label(self._status_frame, textvariable=self.status_var,
                                     style="StatusBar.TLabel", padding=(14, 2))
        self._status_bar.pack(fill=tk.X, expand=True)
        self._progress_visible = False

    def _show_progress(self):
        if not self._progress_visible:
            self.progress_bar.config(length=100)
            self.progress_bar.pack(side=tk.LEFT, padx=(14, 6), pady=2,
                                   before=self._status_bar)
            self._progress_visible = True
        self.progress_bar.start(10)

    def _hide_progress(self):
        if self._progress_visible:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self._progress_visible = False

    # ---------- data ----------

    def _load_saved(self):
        path = os.path.join(DATA_DIR, "tareas_export.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
                self._refresh_table()
                self.status_var.set(f"Cargadas {len(self.tasks)} tarea(s) guardadas")
            except Exception:
                pass

    def _save(self):
        path = os.path.join(DATA_DIR, "tareas_export.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _update_counter(self):
        total = len(self.tasks)
        self.counter_label.config(text=f"Total: {total} tarea{'s' if total != 1 else ''}")

    def _get_estado_tag(self, estado):
        e = estado.lower().strip() if estado else ""
        if e in ("pendiente", "abierto", "abierta"):
            return "estado_pendiente"
        if e in ("completado", "completada", "entregado", "entregada",
                 "realizado", "realizada"):
            return "estado_completado"
        if e in ("vencido", "vencida", "atrasado", "atrasada"):
            return "estado_vencido"
        return ""

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, t in enumerate(self.tasks):
            estado = t.get("estado", "pendiente")
            tag = "even" if i % 2 == 0 else "odd"
            estado_tag = self._get_estado_tag(estado)
            self.tree.insert("", tk.END, values=(
                t.get("titulo", "?"),
                t.get("materia", "?"),
                t.get("tipo", "?"),
                t.get("fecha_apertura", "?"),
                t.get("fecha_entrega", "?"),
                estado,
            ), tags=(tag, estado_tag) if estado_tag else (tag,))

    # ---------- scrape ----------

    def _scrape(self):
        if self.scraping:
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL vac\u00eda",
                                   "Ingresa una URL de Moodle")
            return
        if not validate_url(url):
            messagebox.showwarning("URL inválida",
                                   "Debe ser una URL de aulagradob.unemi.edu.ec o aulagrado.unemi.edu.ec valida")
            return
        self.scraping = True
        self.scrape_btn.config(state=tk.DISABLED, text="\u23f3 Scrapeando...")
        self.status_var.set("Scrapeando...")
        self._show_progress()
        threading.Thread(target=self._do_scrape, args=(url,), daemon=True).start()

    def _do_scrape(self, url):
        try:
            task = run_scrape(
                url,
                username=os.getenv("MOODLE_USERNAME"),
                password=os.getenv("MOODLE_PASSWORD"),
                headless=True,
                storage_path=get_session_path(url),
            )
            self.root.after(0, self._on_scrape_done, task, url)
        except Exception as e:
            import traceback, time
            tb = traceback.format_exc()
            print("--- SCRAPING ERROR ---")
            print(tb)
            try:
                with open(os.path.join(DATA_DIR, "app_error.log"), "a", encoding="utf-8") as f:
                    f.write(f"\n[{time.ctime()}] URL: {url}\n{tb}\n")
            except Exception:
                pass
            self.root.after(0, self._on_scrape_error, str(e), url)

    def _on_scrape_done(self, task, url):
        self._stop_progress()
        self.scraping = False
        self.scrape_btn.config(state=tk.NORMAL, text="\u25b6 Scrapear")
        if task:
            task["url_original"] = url
            self.tasks.append(task)
            self._refresh_table()
            self._save()
            self._update_counter()
            self.status_var.set(f"\u2705 {task.get('titulo', 'Tarea')[:60]}")
        else:
            self.status_var.set("\u274c No se obtuvo resultado")

    def _on_scrape_error(self, error_msg, url=None):
        self._stop_progress()
        self.scraping = False
        self.scrape_btn.config(state=tk.NORMAL, text="▶ Scrapear")
        safe_msg = error_msg[:_MAX_ERROR_LEN] if error_msg else "Error desconocido"
        self.status_var.set(f"❌ {safe_msg}")
        is_login_error = any(kw in error_msg.lower() for kw in [
            "captcha", "expired", "inicio de sesión", 
            "sesión", "sesion", "login", "contraseña", "credenciales"
        ])
        
        if is_login_error:
            retry = messagebox.askyesno(
                "Sesión requerida o expirada",
                "Se detectó que la sesión ha expirado o es necesario iniciar sesión.\n\n"
                "¿Quieres abrir el navegador para iniciar sesión manualmente y actualizar tu sesión?")
            if retry and url:
                self._capture_session_and_retry(url)
        else:
            messagebox.showerror("Error", safe_msg)

    def _capture_session_and_retry(self, url):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        self._capture_session_flow(base_url, target_url_to_retry=url)

    def _capture_session_flow(self, base_url, target_url_to_retry=None):
        self.status_var.set("Abriendo navegador para login manual...")
        self.scrape_btn.config(state=tk.DISABLED, text="⏳ Login...")
        
        is_cancelled = False
        
        def cancel_action():
            nonlocal is_cancelled
            is_cancelled = True
            self.status_var.set("❌ Login cancelado")
            self.scrape_btn.config(state=tk.NORMAL, text="▶ Scrapear")

        waiting_win = self._show_waiting_window(cancel_action)
        
        def run_thread():
            async def run():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=False,
                        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                    )
                    context = await browser.new_context(
                        no_viewport=True,
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/125.0.0.0 Safari/537.36"
                        ),
                    )
                    page = await context.new_page()
                    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    login_url = f"{base_url}/login/index.php"
                    await page.goto(login_url, wait_until="domcontentloaded")
                    
                    success = False
                    for _ in range(360):  # Max 3 minutes
                        if is_cancelled or not browser.is_connected():
                            break
                        try:
                            is_login_page = "login/index.php" in page.url
                            is_logged = (not is_login_page) and (await page.locator("a[href*='login/logout.php'], img.userpicture").count() > 0)
                            if is_logged:
                                await page.wait_for_timeout(2000)  # Wait for cookies to settle
                                await context.storage_state(path=get_session_path(base_url))
                                success = True
                                break
                        except Exception:
                            pass
                        await asyncio.sleep(0.5)
                        
                    await browser.close()
                    return success

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(run())
                loop.close()
                
                self.root.after(0, lambda: self._on_capture_flow_done(success, target_url_to_retry, waiting_win))
            except Exception as e:
                self.root.after(0, lambda: self._on_capture_flow_error(str(e), waiting_win))

        threading.Thread(target=run_thread, daemon=True).start()

    def _show_waiting_window(self, cancel_callback):
        win = tk.Toplevel(self.root)
        win.title("Esperando inicio de sesión")
        win.geometry("400x180")
        win.configure(bg=COLORS["card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        win.geometry(f"+{rx + (rw - 400)//2}+{ry + (rh - 180)//2}")
        
        tk.Label(win, text="Inicio de sesión requerido", font=("Segoe UI", 12, "bold"),
                 bg=COLORS["card"], fg=COLORS["text"]).pack(pady=(15, 10))
        
        lbl = tk.Label(win, text="Inicia sesión en la ventana del navegador que se abrió.\nEsta ventana se cerrará sola cuando tengas éxito.",
                       font=("Segoe UI", 9), bg=COLORS["card"], fg=COLORS["text_secondary"], justify="center")
        lbl.pack(pady=(0, 10))
        
        pb = ttk.Progressbar(win, mode="indeterminate", length=250)
        pb.pack(pady=5)
        pb.start(10)
        
        btn = tk.Button(win, text="Cancelar", command=lambda: [cancel_callback(), win.destroy()],
                        font=("Segoe UI", 9), bg=COLORS["danger"], fg="#ffffff", relief="flat", padx=15, pady=3, cursor="hand2")
        btn.pack(pady=10)
        
        win.protocol("WM_DELETE_WINDOW", lambda: [cancel_callback(), win.destroy()])
        return win

    def _on_capture_flow_done(self, success, target_url_to_retry, waiting_win):
        try:
            waiting_win.destroy()
        except Exception:
            pass
            
        self.scrape_btn.config(state=tk.NORMAL, text="▶ Scrapear")
        self._update_session_indicator()
        
        if success:
            if target_url_to_retry:
                self.status_var.set("✅ Sesión guardada. Reintentando scrape...")
                self._do_scrape(target_url_to_retry)
            else:
                self.status_var.set("✅ Sesión renovada exitosamente")
                messagebox.showinfo("Sesión guardada", "¡Sesión guardada correctamente! Ya puedes scrapear tus tareas.")
        else:
            self.status_var.set("❌ No se pudo guardar la sesión o se canceló")

    def _on_capture_flow_error(self, error_msg, waiting_win):
        try:
            waiting_win.destroy()
        except Exception:
            pass
        self.scrape_btn.config(state=tk.NORMAL, text="▶ Scrapear")
        self._on_capture_failed(error_msg)

    def _on_capture_failed(self, error_msg):
        self.scraping = False
        self.scrape_btn.config(state=tk.NORMAL, text="▶ Scrapear")
        safe_msg = error_msg[:_MAX_ERROR_LEN] if error_msg else "Error desconocido"
        self.status_var.set(f"❌ {safe_msg}")
        messagebox.showerror("Error", f"No se pudo capturar la sesión:\n{safe_msg}")

    def _update_session_indicator(self):
        url = self.url_entry.get().strip()
        session_path = get_session_path(url)
        color = COLORS["success"] if os.path.exists(session_path) else COLORS["danger"]
        self._session_indicator.itemconfig(self._session_dot, fill=color)

    def _clear_session(self):
        try:
            url = self.url_entry.get().strip()
            session_path = get_session_path(url)
            if os.path.exists(session_path):
                os.remove(session_path)
            self._update_session_indicator()
            self.status_var.set("Sesión anterior eliminada")
        except Exception:
            pass

    def _renovar_sesion(self):
        if self.scraping:
            return
        
        # Check current URL in the input field to choose the correct domain
        url = self.url_entry.get().strip()
        if url and validate_url(url):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        else:
            base_url = "https://aulagradob.unemi.edu.ec"  # Default fallback
            
        self._clear_session()
        self._capture_session_flow(base_url)

    def _stop_progress(self):
        self._hide_progress()

    # ---------- actualizar ----------

    def _actualizar(self):
        urls = [
            (i, t["url_original"])
            for i, t in enumerate(self.tasks)
            if t.get("url_original")
        ]
        if not urls:
            messagebox.showinfo("Actualizar",
                                "No hay tareas con URL guardada para actualizar.")
            return
        if self.scraping:
            return
        self.scraping = True
        self._spinner_idx = 0
        self._spinner_chars = ["\u25f4", "\u25f7", "\u25f6", "\u25f5"]
        self._actualizar_queue = urls.copy()
        self._actualizar_total = len(urls)
        self._actualizar_ok = 0
        self._show_progress()
        self._spinner_active()
        threading.Thread(target=self._do_actualizar, daemon=True).start()

    def _spinner_active(self):
        if not self.scraping:
            self.actualizar_btn.config(text="\u21bb Actualizar")
            return
        c = self._spinner_chars[self._spinner_idx % len(self._spinner_chars)]
        self.actualizar_btn.config(text=f"{c} Actualizar")
        self._spinner_idx += 1
        self.root.after(150, self._spinner_active)

    def _do_actualizar(self):
        for pos, (idx, url) in enumerate(self._actualizar_queue):
            if not self.scraping:
                break
            self.root.after(0, lambda p=pos, t=self._actualizar_total:
                self.status_var.set(f"Actualizando {p+1}/{t}..."))
            try:
                task = run_scrape(
                    url,
                    username=os.getenv("MOODLE_USERNAME"),
                    password=os.getenv("MOODLE_PASSWORD"),
                    headless=True,
                    storage_path=get_session_path(url),
                )
                if task:
                    task["url_original"] = url
                    self.tasks[idx] = task
                    self._actualizar_ok += 1
            except Exception as e:
                err_msg = str(e)
                is_login_err = any(kw in err_msg.lower() for kw in [
                    "captcha", "expired", "inicio de sesión", 
                    "sesión", "sesion", "login", "contraseña", "credenciales"
                ])
                if is_login_err:
                    self.root.after(0, lambda u=url, m=err_msg: self._on_scrape_error(m, u))
                    return
        self.root.after(0, self._on_actualizar_done)

    def _on_actualizar_done(self):
        self.scraping = False
        self._refresh_table()
        self._save()
        self.actualizar_btn.config(text="\u21bb Actualizar")
        self.status_var.set(
            f"\u2705 Actualizadas {self._actualizar_ok}/{self._actualizar_total} tareas")
        self._hide_progress()

    # ---------- actions ----------

    def _add_manual(self):
        win = tk.Toplevel(self.root)
        win.title("Agregar tarea manual")
        win.geometry("520x340")
        win.configure(bg=COLORS["card"])
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Nueva tarea", font=("Segoe UI", 12, "bold"),
                 bg=COLORS["card"], fg=COLORS["text"]).pack(pady=(14, 10))

        form = tk.Frame(win, bg=COLORS["card"], padx=20)
        form.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("T\u00edtulo *", "titulo"),
            ("Materia", "materia"),
            ("Tipo", "tipo"),
            ("Fecha apertura (YYYY-MM-DD)", "fecha_apertura"),
            ("Fecha entrega (YYYY-MM-DD)", "fecha_entrega"),
        ]
        entries = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label, font=("Segoe UI", 9),
                     bg=COLORS["card"], fg=COLORS["text"],
                     anchor="w").grid(row=i, column=0, sticky=tk.W+tk.E,
                                      pady=4)
            e = ttk.Entry(form, font=("Segoe UI", 10))
            e.grid(row=i, column=1, sticky=tk.W+tk.E, padx=(10, 0), pady=4)
            entries[key] = e

        form.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(win, bg=COLORS["card"], pady=14)
        btn_frame.pack(fill=tk.X)

        def submit():
            task = {}
            for _, key in fields:
                val = entries[key].get().strip()
                if key == "titulo" and not val:
                    messagebox.showwarning("Campo requerido",
                                           "El t\u00edtulo es obligatorio",
                                           parent=win)
                    return
                task[key] = val or ("?" if key != "tipo" else "tarea")
            task["estado"] = "pendiente"
            task["descripcion"] = ""
            self.tasks.append(task)
            self._refresh_table()
            self._save()
            self._update_counter()
            self.status_var.set(f"\u2705 Tarea manual agregada: {task['titulo'][:40]}")
            win.destroy()

        tk.Button(btn_frame, text="Agregar", command=submit,
                  font=("Segoe UI", 10),
                  bg=COLORS["accent"], fg="#ffffff",
                  relief="flat", padx=24, pady=4,
                  activebackground=COLORS["accent_hover"],
                  cursor="hand2").pack()

    def _delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        if messagebox.askyesno("Confirmar",
                               f"\u00bfEliminar {len(selected)} tarea(s)?"):
            indices = sorted([self.tree.index(i) for i in selected],
                             reverse=True)
            for idx in indices:
                del self.tasks[idx]
            self._refresh_table()
            self._save()
            self._update_counter()
            self.status_var.set(f"Eliminadas {len(selected)} tarea(s)")

    def _clear_all(self):
        if not self.tasks:
            return
        if messagebox.askyesno("Confirmar",
                               "\u00bfEliminar TODAS las tareas?\n"
                               "Esta acci\u00f3n no se puede deshacer."):
            self.tasks.clear()
            self._refresh_table()
            self._save()
            self._update_counter()
            self.status_var.set("Lista limpiada")

    def _export_csv(self):
        if not self.tasks:
            messagebox.showinfo("Sin datos", "No hay tareas para exportar")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Guardar CSV")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                cols = [
                    "titulo", "descripcion", "fecha_entrega",
                    "estado", "materia", "tipo", "fecha_apertura"]
                writer = csv.DictWriter(f, fieldnames=cols,
                                        delimiter=";",
                                        extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.tasks)
            self.status_var.set(f"\u2705 CSV exportado: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {e}")

    def _on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0, font=("Segoe UI", 9),
                       bg=COLORS["card"], fg=COLORS["text"],
                       activebackground=COLORS["accent"],
                       activeforeground="#ffffff")
        menu.add_command(label="Eliminar seleccionadas",
                         command=self._delete_selected)
        menu.add_separator()
        menu.add_command(label="Exportar CSV",
                         command=self._export_csv)
        menu.add_command(label="Limpiar todo",
                         command=self._clear_all)
        menu.add_separator()
        menu.add_command(label="Salir",
                         command=self._quit)
        menu.post(event.x_root, event.y_root)

    def _show_help(self):
        text = (
            "\u2022 Scrapear URL \u2192 obtiene la tarea autom\u00e1ticamente\n"
            "\u2022 + Manual \u2192 agrega datos a mano\n"
            "\u2022 CSV \u2192 exporta a Excel\n"
            "\u2022 Supr \u2192 elimina filas seleccionadas\n"
            "\u2022 Sesi\u00f3n \u2192 renovar login manual (punto verde = activa)"
        )
        messagebox.showinfo("Ayuda", text)


    def _quit(self):
        if messagebox.askokcancel("Salir", "\u00bfDeseas salir de la aplicaci\u00f3n?"):
            cleanup_scraper()
            try:
                self.root.destroy()
            except Exception:
                pass


def main():
    root = tk.Tk()
    try:
        app = ScrapingApp(root)
        root.mainloop()
    except Exception as e:
        safe_msg = str(e)[:_MAX_ERROR_LEN] if str(e) else "Error desconocido"
        messagebox.showerror("Error fatal",
                             f"La aplicaci\u00f3n no pudo iniciarse:\n{safe_msg}")
        try:
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()
