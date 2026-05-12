import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PyPDF2 import PdfReader, PdfWriter
import os
import json
import re
import string
import random
import threading
import pytesseract
import fitz  # PyMuPDF
from datetime import datetime
from pdf2image import convert_from_path
from PIL import Image, ImageTk
import webbrowser
from pathlib import Path
import subprocess
import sys


# ─────────────────────────────────────────────
#  CONFIGURAZIONE GLOBALE
# ─────────────────────────────────────────────
PATHS = {
    'tesseract': r"O:\TESSERACT\tesseract.exe",
    'poppler':   r"O:\GIOVANNI PIO\poppler-24.08.0\Library\bin",
    'logo':      r"O:\GIOVANNI PIO\logo.png",
}
pytesseract.pytesseract.tesseract_cmd = PATHS['tesseract']


CONFIG_DIR  = Path.home() / ".truccolotool"
CONFIG_FILE = CONFIG_DIR / "settings.json"


# ─────────────────────────────────────────────
#  FIX CMD — nasconde TUTTE le finestre console
#  Patcha pdf2image E pytesseract (entrambi hanno
#  un riferimento locale a Popen/subprocess)
# ─────────────────────────────────────────────
if sys.platform == "win32":
    _si = subprocess.STARTUPINFO()
    _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _si.wShowWindow = 0  # SW_HIDE

    class _SilentPopen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            kwargs['startupinfo'] = _si
            kwargs['creationflags'] = (
                kwargs.get('creationflags', 0) | subprocess.CREATE_NO_WINDOW
            )
            super().__init__(*args, **kwargs)

    # Patcha pdf2image (usa "from subprocess import Popen" internamente)
    import pdf2image.pdf2image as _pdf2image_module
    _pdf2image_module.Popen = _SilentPopen

    # Patcha pytesseract (usa "subprocess.Popen" tramite il modulo)
    import pytesseract.pytesseract as _pytesseract_module
    _pytesseract_module.subprocess.Popen = _SilentPopen

    # Patcha anche subprocess globale come terza sicurezza
    subprocess.Popen = _SilentPopen


# ─────────────────────────────────────────────
#  PERSISTENZA IMPOSTAZIONI
# ─────────────────────────────────────────────
def salva_config(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        existing = carica_config()
        existing.update(data)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass


def carica_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────
def nome_casuale(lunghezza=15):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=lunghezza))


def unique_dest_path(folder: str, base_name: str) -> str:
    candidate = os.path.join(folder, f"{base_name}.pdf")
    if not os.path.exists(candidate):
        return candidate
    counter = 2
    while True:
        candidate = os.path.join(folder, f"{base_name} {counter}.pdf")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


# ─────────────────────────────────────────────
#  LOGICA CORE — FRONTE/RETRO + OCR RENTRI
# ─────────────────────────────────────────────
def separa_fronte_retro(front_path, back_path, output_folder,
                        log_cb=None, progress_cb=None):
    try:
        front_reader = PdfReader(front_path)
        back_reader  = PdfReader(back_path)

        n_front = len(front_reader.pages)
        n_back  = len(back_reader.pages)

        if n_front != n_back:
            return False, (f"I PDF hanno numero di pagine diverso:\n"
                           f"Fronti: {n_front}  |  Retro: {n_back}")

        os.makedirs(output_folder, exist_ok=True)

        retro_pages = list(back_reader.pages)[::-1]

        bbox_map = {
            'RENTRI NOSTRI':  (1259, 37,  1649, 122),
            'RENTRI PORTALE': (1197, 72,  1633, 205),
        }

        used_names = set()
        for existing in os.listdir(output_folder):
            if existing.lower().endswith('.pdf'):
                used_names.add(os.path.splitext(existing)[0])

        for i in range(n_front):
            writer = PdfWriter()
            writer.add_page(front_reader.pages[i])
            writer.add_page(retro_pages[i])

            tmp_path = os.path.join(output_folder, f"__tmp_{nome_casuale()}.pdf")
            with open(tmp_path, "wb") as f:
                writer.write(f)

            rentri_name = None
            try:
                images = convert_from_path(tmp_path, first_page=1, last_page=1,
                                           poppler_path=PATHS['poppler'])
                if images:
                    for scan_type, bbox in bbox_map.items():
                        cropped = images[0].crop(bbox)
                        text    = pytesseract.image_to_string(cropped).strip().upper()
                        match   = re.search(r'\b([A-Z]{5})\s+(\d{6})\s+([A-Z]{2})\b', text)
                        if match:
                            rentri_name = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                            if log_cb:
                                log_cb(f"  ✓ Pag.{i+1} — RENTRI trovato [{scan_type}]: {rentri_name}", 'ok')
                            break
            except Exception as ocr_err:
                if log_cb:
                    log_cb(f"  ⚠ Pag.{i+1} — OCR fallita: {ocr_err}", 'warn')

            if rentri_name:
                base_name = rentri_name
            else:
                base_name = "FILE_NON_VALIDO"
                if log_cb:
                    log_cb(f"  ⚠ Pag.{i+1} — Codice RENTRI non trovato", 'warn')

            final_name = base_name
            counter = 2
            while final_name in used_names:
                final_name = f"{base_name} {counter}"
                counter += 1
            used_names.add(final_name)

            dest_path = os.path.join(output_folder, f"{final_name}.pdf")
            os.rename(tmp_path, dest_path)

            if log_cb and not rentri_name:
                log_cb(f"       Salvato come: {final_name}.pdf", 'warn')
            elif log_cb:
                log_cb(f"       Salvato come: {final_name}.pdf", 'ok')

            if progress_cb:
                progress_cb(i + 1, n_front)

        deleted = []
        for path in [front_path, back_path]:
            try:
                os.remove(path)
                deleted.append(os.path.basename(path))
            except Exception as del_err:
                if log_cb:
                    log_cb(f"  ⚠ Impossibile eliminare: {os.path.basename(path)} — {del_err}", 'warn')

        if log_cb and deleted:
            log_cb(f"\n🗑  Originali eliminati: {', '.join(deleted)}", 'info')

        return True, f"Completato: {n_front} PDF creati in:\n{output_folder}"

    except Exception as e:
        return False, f"Errore critico:\n{str(e)}"


# ─────────────────────────────────────────────
#  PALETTE COLORI
# ─────────────────────────────────────────────
C = {
    'bg':           '#1E2A1E',
    'surface':      '#243024',
    'surface2':     '#2D3D2D',
    'surface3':     '#344534',
    'accent':       '#3B7A2B',
    'accent_light': '#4E9E3A',
    'accent_dark':  '#2D5E20',
    'green_text':   '#5BBD45',
    'text':         '#E8F0E8',
    'text_muted':   '#8FA88F',
    'text_faint':   '#566856',
    'success':      '#5BBD45',
    'warning':      '#D4A017',
    'error':        '#C94040',
    'border':       '#2F3F2F',
    'border_light': '#3D503D',
    'divider':      '#28382A',
}

FONT_TITLE   = ('Segoe UI', 18, 'bold')
FONT_SUB     = ('Segoe UI', 10, 'bold')
FONT_BODY    = ('Segoe UI', 10)
FONT_SMALL   = ('Segoe UI', 9)
FONT_SMALLER = ('Segoe UI', 8)
FONT_MONO    = ('Consolas', 9)
FONT_BTN     = ('Segoe UI', 10, 'bold')
FONT_BTN_LG  = ('Segoe UI', 12, 'bold')


# ─────────────────────────────────────────────
#  APPLICAZIONE
# ─────────────────────────────────────────────
class TruccoloTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Truccolo Angelo Srl — PDF Tool")
        self.geometry("900x680")
        self.minsize(750, 580)
        self.configure(bg=C['bg'])
        self.resizable(True, True)

        cfg = carica_config()
        self.front_path    = tk.StringVar(value="")
        self.back_path     = tk.StringVar(value="")
        self.output_folder = tk.StringVar(value=cfg.get('output_folder', ''))
        self.processing    = False

        self._build_ui()
        self._load_logo()
        self._update_status()

    def _build_ui(self):
        self._build_header()
        self._build_body()
        self._build_styles()

    def _build_header(self):
        hdr = tk.Frame(self, bg=C['surface'], pady=0)
        hdr.pack(fill='x')

        tk.Frame(hdr, bg=C['accent'], height=4).pack(fill='x')

        inner = tk.Frame(hdr, bg=C['surface'], pady=12)
        inner.pack(fill='x')

        self.logo_canvas = tk.Canvas(inner, width=100, height=72,
                                     bg=C['surface'], highlightthickness=0,
                                     cursor='hand2')
        self.logo_canvas.pack(side='left', padx=(16, 12))
        self.logo_canvas.bind("<Button-1>",
                              lambda e: webbrowser.open("https://truccoloangelo.com"))

        title_frame = tk.Frame(inner, bg=C['surface'])
        title_frame.pack(side='left', padx=4)

        tk.Label(title_frame, text="PDF Tool",
                 font=('Segoe UI', 22, 'bold'),
                 fg=C['text'], bg=C['surface']).pack(anchor='w')

        tk.Label(title_frame,
                 text="Unione Fronte/Retro  ·  Rinomina RENTRI automatica",
                 font=FONT_SMALL, fg=C['green_text'],
                 bg=C['surface']).pack(anchor='w', pady=(1, 0))

        tk.Label(title_frame, text="Truccolo Angelo Srl",
                 font=FONT_SMALLER, fg=C['text_muted'],
                 bg=C['surface']).pack(anchor='w')

        info_btn = tk.Button(inner, text="ℹ  Info",
                             font=FONT_BTN,
                             fg=C['text'], bg=C['surface2'],
                             activebackground=C['surface3'],
                             activeforeground=C['text'],
                             relief='flat', padx=14, pady=7,
                             cursor='hand2',
                             command=self._show_info)
        info_btn.pack(side='right', padx=16)
        self._hover(info_btn, C['surface3'], C['surface2'])

        tk.Frame(hdr, bg=C['border_light'], height=1).pack(fill='x')

    def _build_body(self):
        body = tk.Frame(self, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=6)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=C['bg'])
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 14))

        self._section_label(left, "📄  SELEZIONE FILE")

        self._file_row(left, "PDF Fronti", self.front_path,
                       lambda: self._pick_file(self.front_path, "Seleziona PDF FRONTI"))
        self._file_row(left, "PDF Retro", self.back_path,
                       lambda: self._pick_file(self.back_path, "Seleziona PDF RETRO"))
        self._file_row(left, "Output", self.output_folder,
                       lambda: self._pick_folder(self.output_folder),
                       is_folder=True)

        tk.Frame(left, bg=C['bg'], height=22).pack()

        self.btn_run = tk.Button(left,
                                 text="▶  ELABORA PDF",
                                 font=FONT_BTN_LG,
                                 fg='white', bg=C['accent'],
                                 activebackground=C['accent_dark'],
                                 activeforeground='white',
                                 relief='flat', pady=13,
                                 cursor='hand2',
                                 command=self._run)
        self.btn_run.pack(fill='x', ipady=2)

        tk.Frame(left, bg=C['bg'], height=10).pack()

        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(left,
                                            variable=self.progress_var,
                                            maximum=100,
                                            style='TA.Horizontal.TProgressbar')

        self.status_var = tk.StringVar(value="Seleziona i file per iniziare")
        tk.Label(left, textvariable=self.status_var,
                 font=FONT_SMALL, fg=C['text_muted'],
                 bg=C['bg'], wraplength=330,
                 justify='left').pack(anchor='w', pady=(6, 0))

        right = tk.Frame(body, bg=C['bg'])
        right.grid(row=0, column=1, sticky='nsew')
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._section_label(right, "📋  LOG ELABORAZIONE")

        log_outer = tk.Frame(right, bg=C['surface'],
                             highlightthickness=1,
                             highlightbackground=C['border_light'])
        log_outer.pack(fill='both', expand=True)

        self.log_text = tk.Text(log_outer,
                                bg=C['surface'], fg=C['text'],
                                font=FONT_MONO, relief='flat', bd=8,
                                wrap='word', state='disabled',
                                cursor='arrow',
                                selectbackground=C['surface3'])
        vsb = tk.Scrollbar(log_outer, command=self.log_text.yview,
                           bg=C['border'], troughcolor=C['surface'],
                           activebackground=C['accent'])
        self.log_text.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.log_text.pack(fill='both', expand=True)

        self.log_text.tag_configure('ok',      foreground=C['success'])
        self.log_text.tag_configure('warn',    foreground=C['warning'])
        self.log_text.tag_configure('err',     foreground=C['error'])
        self.log_text.tag_configure('info',    foreground=C['text_muted'])
        self.log_text.tag_configure('heading', foreground=C['green_text'],
                                    font=('Segoe UI', 9, 'bold'))

        btn_clear = tk.Button(right, text="🗑  Svuota log",
                              font=FONT_SMALL,
                              fg=C['text_muted'], bg=C['surface'],
                              activebackground=C['surface2'],
                              relief='flat', cursor='hand2',
                              command=self._clear_log)
        btn_clear.pack(anchor='e', pady=(6, 0))
        self._hover(btn_clear, C['surface2'], C['surface'])

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TA.Horizontal.TProgressbar',
                        troughcolor=C['surface'],
                        background=C['accent'],
                        darkcolor=C['accent_dark'],
                        lightcolor=C['accent_light'],
                        bordercolor=C['border'])

    def _section_label(self, parent, text):
        f = tk.Frame(parent, bg=C['bg'])
        f.pack(fill='x', pady=(0, 10))
        tk.Label(f, text=text, font=FONT_SUB,
                 fg=C['green_text'], bg=C['bg']).pack(side='left')
        tk.Frame(f, bg=C['border_light'], height=1).pack(
            side='left', fill='x', expand=True, padx=(8, 0), pady=5)

    def _file_row(self, parent, label, var, cmd, is_folder=False):
        row = tk.Frame(parent, bg=C['bg'])
        row.pack(fill='x', pady=5)

        icon = "📁" if is_folder else "📄"
        tk.Label(row, text=f"{icon}  {label}",
                 font=FONT_SMALL, fg=C['text_muted'],
                 bg=C['bg'], width=11, anchor='w').pack(side='left')

        path_outer = tk.Frame(row, bg=C['surface'],
                              highlightthickness=1,
                              highlightbackground=C['border_light'])
        path_outer.pack(side='left', fill='x', expand=True, padx=(0, 6))

        display_lbl = tk.Label(path_outer,
                               font=FONT_SMALL, fg=C['text_muted'],
                               bg=C['surface'], anchor='w',
                               padx=8, pady=5,
                               text="—  non selezionato")
        display_lbl.pack(fill='x')

        def on_change(*_, lbl=display_lbl, v=var):
            p = v.get()
            if not p:
                lbl.config(text="—  non selezionato", fg=C['text_muted'])
            else:
                bn = os.path.basename(p)
                lbl.config(
                    text=bn if len(bn) <= 40 else f"…{bn[-38:]}",
                    fg=C['text'])

        var.trace_add('write', on_change)

        btn = tk.Button(row, text="Sfoglia",
                        font=FONT_SMALL,
                        fg=C['text'], bg=C['surface2'],
                        activebackground=C['surface3'],
                        relief='flat', padx=10,
                        cursor='hand2', command=cmd)
        btn.pack(side='left')
        self._hover(btn, C['surface3'], C['surface2'])

    @staticmethod
    def _hover(widget, color_in, color_out):
        widget.bind('<Enter>', lambda e: widget.config(bg=color_in))
        widget.bind('<Leave>', lambda e: widget.config(bg=color_out))

    def _load_logo(self):
        c = self.logo_canvas
        logo_loaded = False

        candidates = [
            PATHS['logo'],
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logo.png'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LOGO-Bianco.jpg'),
        ]
        for path in candidates:
            try:
                img = Image.open(path)
                img.thumbnail((98, 70), Image.Resampling.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                c.config(width=img.width + 4, height=img.height + 4)
                c.create_image(img.width // 2 + 2, img.height // 2 + 2,
                               image=self._logo_img)
                logo_loaded = True
                break
            except Exception:
                continue

        if not logo_loaded:
            c.config(width=90, height=68)
            c.create_oval(5, 4, 85, 64, fill=C['accent_dark'], outline=C['accent_light'], width=2)
            c.create_text(45, 34, text="TA", fill='white',
                          font=('Segoe UI', 22, 'bold'))

    def _pick_file(self, var, title):
        path = filedialog.askopenfilename(
            title=title, filetypes=[("PDF files", "*.pdf")])
        if path:
            var.set(path)
            self._update_status()

    def _pick_folder(self, var):
        path = filedialog.askdirectory(title="Seleziona cartella di output")
        if path:
            var.set(path)
            salva_config({'output_folder': path})
            self._update_status()

    def _update_status(self):
        done = sum([bool(self.front_path.get()),
                    bool(self.back_path.get()),
                    bool(self.output_folder.get())])
        if done == 3:
            self.status_var.set("✅ Tutto pronto — premi ELABORA PDF")
        elif done == 0:
            self.status_var.set("Seleziona i file per iniziare")
        else:
            self.status_var.set(f"Selezione {done}/3 completata...")

    def _log(self, msg: str, tag: str = ''):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', msg + '\n', tag if tag else ())
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    def _run(self):
        if self.processing:
            return
        fp  = self.front_path.get().strip()
        bp  = self.back_path.get().strip()
        out = self.output_folder.get().strip()

        if not fp:
            messagebox.showwarning("Attenzione", "Seleziona il PDF dei FRONTI")
            return
        if not bp:
            messagebox.showwarning("Attenzione", "Seleziona il PDF dei RETRO")
            return
        if not out:
            messagebox.showwarning("Attenzione", "Seleziona la cartella di output")
            return

        self.processing = True
        self.btn_run.config(state='disabled', bg=C['accent_dark'],
                            text="⏳  Elaborazione in corso...")
        self.progress_bar.pack(fill='x')
        self.progress_var.set(0)

        now = datetime.now().strftime('%H:%M:%S')
        self._log(f"\n{'─'*46}", 'info')
        self._log(f"  Avvio  {now}", 'heading')
        self._log(f"  Fronti : {os.path.basename(fp)}", 'info')
        self._log(f"  Retro  : {os.path.basename(bp)}", 'info')
        self._log(f"  Output : {out}", 'info')
        self._log(f"{'─'*46}", 'info')

        def worker():
            def on_log(msg, tag=''):
                self.after(0, lambda m=msg, t=tag: self._log(m, t))

            def on_progress(done, total):
                pct = int(done / total * 100)
                self.after(0, lambda p=pct: self.progress_var.set(p))
                self.after(0, lambda d=done, t=total:
                           self.status_var.set(
                               f"⏳ Elaborazione: {d} / {t} pagine..."))

            ok, msg = separa_fronte_retro(fp, bp, out,
                                          log_cb=on_log,
                                          progress_cb=on_progress)

            def finish():
                self.processing = False
                self.btn_run.config(state='normal', bg=C['accent'],
                                    text="▶  ELABORA PDF")
                self.progress_bar.pack_forget()
                self.progress_var.set(0)
                self.front_path.set("")
                self.back_path.set("")
                self._update_status()

                if ok:
                    self._log(f"\n✅  {msg}", 'ok')
                    self.status_var.set("✅ Elaborazione completata!")
                    messagebox.showinfo("Completato", msg)
                else:
                    self._log(f"\n❌  {msg}", 'err')
                    self.status_var.set("❌ Errore — vedi log")
                    messagebox.showerror("Errore", msg)

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _show_info(self):
        win = tk.Toplevel(self)
        win.title("Informazioni — PDF Tool")
        win.geometry("480x460")
        win.configure(bg=C['surface'])
        win.resizable(False, False)
        win.grab_set()

        tk.Frame(win, bg=C['accent'], height=4).pack(fill='x')

        c2 = tk.Canvas(win, width=120, height=86,
                       bg=C['surface'], highlightthickness=0)
        c2.pack(pady=(18, 4))
        logo_loaded = False
        for path in [PATHS['logo'],
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logo.png'),
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LOGO-Bianco.jpg')]:
            try:
                img2 = Image.open(path)
                img2.thumbnail((116, 82), Image.Resampling.LANCZOS)
                self._info_logo = ImageTk.PhotoImage(img2)
                c2.config(width=img2.width + 4, height=img2.height + 4)
                c2.create_image(img2.width // 2 + 2, img2.height // 2 + 2,
                                image=self._info_logo)
                logo_loaded = True
                break
            except Exception:
                continue
        if not logo_loaded:
            c2.create_oval(10, 4, 110, 82, fill=C['accent_dark'],
                           outline=C['accent_light'], width=2)
            c2.create_text(60, 43, text="TA", fill='white',
                           font=('Segoe UI', 26, 'bold'))

        tk.Label(win, text="Truccolo Angelo Srl",
                 font=('Segoe UI', 13, 'bold'),
                 fg=C['text'], bg=C['surface']).pack()
        tk.Label(win, text="PDF Tool — v2.0",
                 font=FONT_SMALL, fg=C['green_text'],
                 bg=C['surface']).pack(pady=(2, 12))

        box = tk.Frame(win, bg=C['bg'], padx=22, pady=14)
        box.pack(fill='x', padx=22)

        lines = [
            ("📄  Come funziona", 'head'),
            ("1. Seleziona il PDF con tutte le pagine FRONTI.", ''),
            ("2. Seleziona il PDF con tutte le pagine RETRO.", ''),
            ("3. Scegli la cartella di output.", ''),
            ("4. Premi ELABORA PDF.", ''),
            ("", ''),
            ("🔍  Rinomina automatica RENTRI", 'head'),
            ("Ogni coppia viene analizzata tramite OCR.", ''),
            ("Se trovato un codice (es. LZTLX 123456 XX),", ''),
            ("il file viene rinominato con quel codice.", ''),
            ("Se non trovato → FILE_NON_VALIDO, FILE_NON_VALIDO 2...", ''),
            ("", ''),
            ("🗑  I file originali vengono eliminati", ''),
            ("   automaticamente dopo la separazione.", ''),
        ]
        for text, tag in lines:
            color = C['green_text'] if tag == 'head' else C['text']
            font  = ('Segoe UI', 9, 'bold') if tag == 'head' else FONT_SMALL
            tk.Label(box, text=text, font=font, fg=color,
                     bg=C['bg'], anchor='w').pack(fill='x', pady=1)

        tk.Button(win, text="Chiudi", font=FONT_BTN,
                  fg='white', bg=C['accent'],
                  activebackground=C['accent_dark'],
                  relief='flat', padx=22, pady=8,
                  cursor='hand2',
                  command=win.destroy).pack(pady=16)


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = TruccoloTool()
    app.mainloop()
