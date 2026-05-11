# 📄 Truccolo Angelo — PDF Tool

<p align="center">
  <img src="https://cdn-ikpfegl.nitrocdn.com/AakdWbLrQBXaLlLaoucOtDmmiOQrFVyM/assets/images/optimized/rev-86bef17/www.truccoloangelo.com/wp-content/uploads/2025/06/LOGO-PNG.png"/>
</p>

<p align="center">
  <strong>Unione Fronte/Retro · Rinomina RENTRI automatica tramite OCR</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3B7A2B?style=flat-square&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white"/>
  <img src="https://img.shields.io/badge/GUI-Tkinter-4E9E3A?style=flat-square"/>
  <img src="https://img.shields.io/badge/License-Proprietary-2D3A3A?style=flat-square"/>
</p>

---

## Descrizione

**PDF Tool** è un'applicazione desktop sviluppata internamente per **Truccolo Angelo Srl** che automatizza due operazioni quotidiane sulla gestione dei FIR (Formulari Identificazione Rifiuti):

1. **Unione Fronte/Retro** — Prende due PDF separati (uno con tutti i fronti, uno con tutti i retro) e li accoppia pagina per pagina in file PDF individuali.
2. **Rinomina RENTRI automatica** — Tramite OCR (Tesseract), legge il codice RENTRI da ogni FIR e rinomina il file di conseguenza (es. `TRUCC0 123456 IT.pdf`). Se il codice non viene trovato, il file viene salvato come `FILE_NON_VALIDO.pdf`, `FILE_NON_VALIDO 2.pdf`, ecc.
3. **Pulizia automatica** — I file PDF originali (fronti e retro) vengono eliminati automaticamente dopo l'elaborazione.

---
## Requisiti di sistema

| Componente | Versione |
|---|---|
| Python | 3.10 o superiore |
| Tesseract OCR | 5.x — installato in `O:\TESSERACT\` |
| Poppler | 24.08.0 — installato in `O:\GIOVANNI PIO\poppler-24.08.0\` |

---

## Installazione dipendenze

```bash
pip install PyPDF2 pytesseract pymupdf pdf2image Pillow
```

---

## Configurazione percorsi

Apri `pdf_tool_truccolo.py` e modifica la sezione `PATHS` in cima al file:

```python
PATHS = {
    'tesseract': r"O:\TESSERACT\tesseract.exe",
    'poppler':   r"O:\GIOVANNI PIO\poppler-24.08.0\Library\bin",
    'logo':      r"O:\GIOVANNI PIO\logo.png",
}
```

In alternativa, metti il file `logo.png` o `LOGO-Bianco.jpg` nella **stessa cartella** dello script: verrà caricato automaticamente.

---

## Utilizzo

### Modalità script Python
```bash
python pdf_tool_truccolo.py
```

### Modalità eseguibile (.exe)
```bash
pyinstaller --onefile --noconsole pdf_tool_truccolo.py
```
Il file `.exe` si troverà nella cartella `dist/`.

> ⚠️ Prima di compilare, assicurarsi di aver disinstallato il pacchetto `pathlib` da PyPI (backport obsoleto incompatibile con PyInstaller su Python 3.13+):
> ```bash
> pip uninstall pathlib
> ```

---

## Come funziona — flusso operativo

```
PDF Fronti  ──┐
               ├──► Accoppiamento pagine ──► OCR RENTRI ──► Rinomina ──► Output
PDF Retro   ──┘                                                    │
                                                             Elimina originali
```

1. Seleziona il **PDF Fronti** (tutte le pagine fronte in un unico file)
2. Seleziona il **PDF Retro** (tutte le pagine retro in un unico file)
3. Seleziona la **cartella di output**
4. Premi **ELABORA PDF**

Il programma inverte automaticamente l'ordine delle pagine retro (compensazione stampa manuale fronte/retro).

---

## Struttura del progetto

```
truccolo-pdf-tool/
├── pdf_tool_truccolo.py     # Script principale
├── LOGO-Bianco.jpg          # Logo aziendale (opzionale, per caricamento automatico)
├── requirements.txt         # Dipendenze Python
├── build.bat                # Script di compilazione .exe
├── .gitignore
└── README.md
```

---

## Dipendenze Python

Vedi [`requirements.txt`](requirements.txt).

---

## Sviluppato da
**Giovanni Pio**
🌐 [familiarigiovannipio.it](https://familiarigiovannipio.it)
---

*Uso interno — software proprietario.*
