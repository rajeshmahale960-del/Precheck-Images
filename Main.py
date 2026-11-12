import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from Precheck import parse_skus, extract_drive_folder_id, main as run_backend

class RoundedActionButton(tk.Canvas):
    """Canvas button with rounded corners and explicit enabled/disabled colors."""
    def __init__(self, master, text, command, fill, hover, disabled_fill, **kwargs):
        super().__init__(master, height=50, bd=0, highlightthickness=0,
                         relief="flat", bg="#111827", cursor="hand2", **kwargs)
        self.label, self.command = text, command
        self.fill, self.hover, self.disabled_fill = fill, hover, disabled_fill
        self.enabled, self.hovered = True, False
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 80), max(self.winfo_height(), 44)
        color = self.disabled_fill if not self.enabled else (self.hover if self.hovered else self.fill)
        r, x1, y1, x2, y2 = 12, 2, 2, w-2, h-2
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
               x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        self.create_polygon(pts, smooth=True, splinesteps=24, fill=color, outline=color)
        self.create_text(w/2, h/2, text=self.label, fill="#FFFFFF",
                         font=("Segoe UI", 10, "bold"))

    def _enter(self, _e):
        self.hovered = True
        self._draw()

    def _leave(self, _e):
        self.hovered = False
        self._draw()

    def _click(self, _e):
        if self.enabled and self.command:
            self.command()

    def config(self, **kwargs):
        if "state" in kwargs:
            self.enabled = kwargs.pop("state") != "disabled"
            self.configure(cursor="hand2" if self.enabled else "arrow")
            self._draw()
        if kwargs:
            super().config(**kwargs)

    configure = config


# Desktop presentation layer. The JSON backend above is intentionally unchanged.
def launch_desktop_ui():
    import subprocess
    import tkinter as tk
    from tkinter import ttk

    class DesktopApp:
        def __init__(self, root):
            self.root = root
            root.title("Images Precheck")

            bundle_dir = getattr(
                sys, "_MEIPASS",
                os.path.dirname(os.path.abspath(__file__))
            )
            
            icon_path = os.path.join(bundle_dir, "icon.ico")
            
            if os.path.exists(icon_path):
                root.iconbitmap(default=icon_path)

            root.resizable(False, False)
            root.configure(bg="#111827")
            self.process = None
            self.running = False
            self.enabled = {"SCAN": True, "REPORT_CSV": False, "RESET": True}
            self.link = tk.StringVar()
            self.status_text = tk.StringVar(value="Ready")
            style = ttk.Style(root)
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure("App.TFrame", background="#111827")
            style.configure("Title.TLabel", background="#111827",
                            foreground="#F8FAFC", font=("Segoe UI", 18, "bold"))
            style.configure("Field.TLabel", background="#111827",
                            foreground="#E2E8F0", font=("Segoe UI", 10, "bold"))
            style.configure("Muted.TLabel", background="#111827",
                            foreground="#AAB8CC", font=("Segoe UI", 9))
            style.configure("App.TEntry", fieldbackground="#1F2937",
                            foreground="#F8FAFC", padding=9,
                            bordercolor="#64748B", lightcolor="#64748B",
                            darkcolor="#64748B")
            style.configure("Primary.TButton", background="#1747B8",
                            foreground="#FFFFFF", font=("Segoe UI", 10, "bold"),
                            padding=(16, 11), borderwidth=1,
                            bordercolor="#12398F", focusthickness=2,
                            focuscolor="#93C5FD", anchor="center")
            style.map("Primary.TButton",
                      background=[("disabled", "#8FA7D8"), ("active", "#12398F")],
                      foreground=[("disabled", "#F8FAFC")])
            style.configure("Success.TButton", background="#08745E",
                            foreground="#FFFFFF", font=("Segoe UI", 10, "bold"),
                            padding=(16, 11), borderwidth=1,
                            bordercolor="#075744", focusthickness=2,
                            focuscolor="#6EE7B7", anchor="center")
            style.map("Success.TButton",
                      background=[("disabled", "#8BBDB2"), ("active", "#064E3B")],
                      foreground=[("disabled", "#F8FAFC")])
            style.configure("Neutral.TButton", background="#344256",
                            foreground="#FFFFFF", font=("Segoe UI", 9, "bold"),
                            padding=(14, 11), borderwidth=1,
                            bordercolor="#1E293B", focusthickness=2,
                            focuscolor="#94A3B8", anchor="center")
            style.map("Neutral.TButton", background=[("active", "#1E293B")],
                      foreground=[("active", "#FFFFFF")])
            style.configure("App.Horizontal.TProgressbar",
                            troughcolor="#263449", background="#3B82F6",
                            bordercolor="#263449", lightcolor="#3B82F6",
                            darkcolor="#3B82F6", thickness=10)
            main_frame = ttk.Frame(root, padding=18, style="App.TFrame")
            main_frame.grid(row=0, column=0, sticky="nsew")


            header = ttk.Frame(main_frame, style="App.TFrame")
            header.grid(row=0, column=0, columnspan=3,
                        sticky="w", pady=(0, 14))
            
            
            ttk.Label(
                header,
                text="Images PreCHeck",
                style="Title.TLabel"
            ).pack(side="left")


            ttk.Label(main_frame, text="SKUs", style="Field.TLabel").grid(row=1, column=0,
                columnspan=2, sticky="w", pady=(0, 5))
            self.sku_count = ttk.Label(main_frame, text="0 SKUs", style="Muted.TLabel")
            self.sku_count.grid(row=1, column=2, sticky="e", pady=(0, 5))
            self.skus = tk.Text(main_frame, width=60, height=8, wrap="none",
                                relief="flat", borderwidth=0, padx=9, pady=8,
                                bg="#1F2937", fg="#F8FAFC", insertbackground="#60A5FA",
                                selectbackground="#1D4ED8", selectforeground="#FFFFFF",
                                font=("Consolas", 10), highlightthickness=1,
                                highlightbackground="#475569", highlightcolor="#60A5FA")
            self.skus.grid(row=2, column=0, columnspan=3, sticky="ew")
            self.skus.bind("<KeyRelease>", self.update_count)
            ttk.Label(main_frame, text="Google Drive Folder Link",
                      style="Field.TLabel").grid(
                row=3, column=0, columnspan=3, sticky="w", pady=(14, 5))
            # Match the SKU field's 9px text inset without changing the
            # Drive field's outer width or its grid position.
            self.link_field = tk.Frame(
                main_frame, bg="#1F2937", bd=0, highlightthickness=1,
                highlightbackground="#64748B", highlightcolor="#60A5FA")
            self.link_field.grid(
                row=4, column=0, columnspan=3, sticky="ew", ipady=8)
            self.link_entry = tk.Entry(
                self.link_field, textvariable=self.link, width=70,
                bg="#1F2937", fg="#F8FAFC",
                insertbackground="#60A5FA", insertwidth=1,
                selectbackground="#1D4ED8", selectforeground="#FFFFFF",
                relief="flat", bd=0, highlightthickness=0,
                font=("Segoe UI", 10), justify="left")
            self.link_entry.pack(fill="both", expand=True, padx=9, pady=1)
            actions = ttk.Frame(main_frame, style="App.TFrame")
            actions.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(18, 4))
            self.buttons = {}
            actions.columnconfigure(0, weight=1, uniform="action_buttons")
            actions.columnconfigure(1, weight=1, uniform="action_buttons")
            actions.columnconfigure(2, weight=1, uniform="action_buttons")
            action_specs = (
                ("SCAN", "Process", "#2563EB", "#1D4ED8", "#334155"),
                ("REPORT_CSV", "Report CSV", "#059669", "#047857", "#334155"),
                ("RESET", "Reset Progress", "#475569", "#334155", "#475569"),
            )
            for col, (key, caption, fill, hover, disabled_fill) in enumerate(action_specs):
                button = RoundedActionButton(
                    actions, text=caption,
                    command=lambda k=key: self.click(k),
                    fill=fill, hover=hover, disabled_fill=disabled_fill,
                    width=170)
                button.grid(row=0, column=col,
                            padx=6, sticky="ew")
                self.buttons[key] = button
            ttk.Label(main_frame, textvariable=self.status_text,
                      style="Muted.TLabel").grid(
                row=6, column=0, columnspan=3, sticky="w", pady=(12, 5))
            self.progressbar = ttk.Progressbar(main_frame, orient="horizontal",
                length=500, mode="determinate", maximum=100,
                style="App.Horizontal.TProgressbar")
            self.progressbar.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 2))
            for col in range(3):
                main_frame.columnconfigure(col, weight=1)
            self.refresh_buttons()
            root.protocol("WM_DELETE_WINDOW", self.close)
            root.update_idletasks()
            fixed_width = root.winfo_reqwidth()
            fixed_height = root.winfo_reqheight()
            root.geometry(f"{fixed_width}x{fixed_height}")
            root.minsize(fixed_width, fixed_height)
            root.maxsize(fixed_width, fixed_height)

        def update_count(self, event=None):
            count = len(parse_skus(self.skus.get("1.0", "end")))
            self.sku_count.config(text=f"{count} SKU{'s' if count != 1 else ''}")

        def refresh_buttons(self):
            for key, button in self.buttons.items():
                # Reset is intentionally always available, including during active work.
                can_click = key == "RESET" or (self.enabled[key] and not self.running)
                button.config(state="normal" if can_click else "disabled")

        def reset_backend(self):
            old = self.process
            self.process = None
            if old is not None:
                try:
                    old.terminate()
                except OSError:
                    pass
            self.running = False
            self.enabled = {"SCAN": True, "REPORT_CSV": False, "RESET": True}
            self.refresh_buttons()

        def start_backend(self):
            skus = parse_skus(self.skus.get("1.0", "end"))
            if not skus:
                self.status_text.set("Failed")
                return False
            if not extract_drive_folder_id(self.link.get()):
                self.status_text.set("Failed")
                return False
            if getattr(sys, "frozen", False):
                # In a one-file EXE, run this same executable in backend mode.
                backend_command = [sys.executable, "--backend"]
            else:
                # During development, run the separate Python backend file.
                backend_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "Precheck.py"
                )
                backend_command = [sys.executable, backend_path, "--backend"]

            self.process = subprocess.Popen(
                backend_command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", bufsize=1)
            self.process.stdin.write(json.dumps({"SKU": self.skus.get("1.0", "end"),
                "drive_link": self.link.get().strip()}) + "\n")
            self.process.stdin.flush()
            proc = self.process
            threading.Thread(target=self.read_events, args=(proc,), daemon=True).start()
            return True

        def read_events(self, proc):
            try:
                for line in proc.stdout:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    self.root.after(0, lambda e=event, p=proc: self.handle_event(p, e))
            except (OSError, ValueError):
                pass
            self.root.after(0, lambda p=proc: self.backend_exited(p))

        def backend_exited(self, proc):
            if proc is self.process:
                self.reset_backend()
                self.status_text.set("Backend stopped. Click Process to restart.")

        def handle_event(self, proc, event):
            if proc is not self.process:
                return
            kind = event.get("type")
            if kind == "button_status" and event.get("id") in self.enabled:
                self.enabled[event["id"]] = bool(event.get("clickable"))
            elif kind == "progress":
                self.progressbar["value"] = event.get("value", 0)
            elif kind == "status":
                self.status_text.set(event.get("text", ""))
            elif kind == "error":
                self.status_text.set(event.get("text", "Failed"))
            elif kind == "complete":
                self.running = False
            self.refresh_buttons()

        def click(self, key):
            if key == "RESET":
                # Stop the current backend/session and clear progress/results only.
                # The SKU and Google Drive inputs remain untouched.
                self.reset_backend()
                self.progressbar["value"] = 0
                self.status_text.set("Progress reset. Inputs preserved; click Process to scan again.")
                self.enabled["RESET"] = True
                self.refresh_buttons()
                return
            if self.running:
                return
            if key == "REPORT_CSV":
                if not self.process:
                    self.status_text.set("Failed")
                    return
            if key == "SCAN":
                # A new Process uses current inputs and starts a fresh backend session.
                self.reset_backend()
                if not self.start_backend():
                    return
            elif not self.process or not self.enabled.get(key):
                return
            self.running = True
            self.progressbar["value"] = 0
            self.refresh_buttons()
            try:
                self.process.stdin.write(json.dumps({"button": key}) + "\n")
                self.process.stdin.flush()
            except (OSError, ValueError):
                self.reset_backend()
                self.status_text.set("Failed")

        def close(self):
            self.reset_backend()
            self.root.destroy()

    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    if "--backend" in sys.argv:
        run_backend()
    else:
        launch_desktop_ui()
