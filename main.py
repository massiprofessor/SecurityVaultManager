import customtkinter as ctk
from tkinter import messagebox, filedialog
import json
import os
import shutil
import base64
import secrets
import string
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME    = "SecureAccountManager"
APP_VERSION = "0.4"
APP_AUTHOR  = "Mezzina Pasquale Massimo"
APP_YEAR    = "2026"

APP_DIR    = os.path.join(os.getenv("LOCALAPPDATA"), APP_NAME)
os.makedirs(APP_DIR, exist_ok=True)
VAULT_FILE = os.path.join(APP_DIR, "vault.dat")

accounts = {}
fernet   = None
salt     = None


# ================= CRYPTO =================

def derive_key(password, salt):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def load_vault(password):
    global accounts, fernet, salt

    if not os.path.exists(VAULT_FILE):
        salt = os.urandom(16)
        key  = derive_key(password, salt)
        fernet = Fernet(key)
        save_vault()
        return True

    with open(VAULT_FILE, "rb") as f:
        salt           = f.read(16)
        encrypted_data = f.read()

    key    = derive_key(password, salt)
    fernet = Fernet(key)

    try:
        decrypted = fernet.decrypt(encrypted_data)
        accounts.clear()
        accounts.update(json.loads(decrypted.decode()))
        return True
    except Exception:
        return False


def save_vault():
    encrypted = fernet.encrypt(json.dumps(accounts).encode())
    with open(VAULT_FILE, "wb") as f:
        f.write(salt)
        f.write(encrypted)


# ================= PASSWORD UTIL =================

def generate_password(length=18):
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(chars) for _ in range(length))


def password_strength(password):
    score = 0
    if len(password) >= 8:  score += 1
    if len(password) >= 12: score += 1
    if any(c.isupper() for c in password): score += 1
    if any(c.isdigit() for c in password): score += 1
    if any(c in string.punctuation for c in password): score += 1
    return score


def get_duplicates():
    counts = {}
    for acc in accounts.values():
        pwd = acc["password"]
        counts[pwd] = counts.get(pwd, 0) + 1
    return [pwd for pwd, count in counts.items() if count > 1]


# ================= STRENGTH HELPER =================

STRENGTH_MAP = {
    0: ("red",        "Molto Debole"),
    1: ("red",        "Molto Debole"),
    2: ("orange",     "Debole"),
    3: ("yellow",     "Media"),
    4: ("lightgreen", "Forte"),
    5: ("green",      "Fortissima"),
}

def apply_strength(bar, label, password):
    score = password_strength(password)
    bar.set(score / 5)
    color, text = STRENGTH_MAP.get(score, ("red", "Molto Debole"))
    bar.configure(progress_color=color)
    label.configure(text=text)


# ================= LOGIN =================

def login_window():
    is_first = not os.path.exists(VAULT_FILE)

    login = ctk.CTk()
    login.title("Secure Account Manager – Accesso")
    login.geometry("420x420" if is_first else "420x280")
    login.resizable(False, False)
    login.columnconfigure(0, weight=1)

    if is_first:
        banner = ctk.CTkFrame(login, fg_color="#1A3A5C", corner_radius=12)
        banner.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        ctk.CTkLabel(banner, text="🔐  Primo Accesso",
                     font=("Segoe UI", 16, "bold"),
                     text_color="#5BC8FF").grid(row=0, column=0, padx=16, pady=(12, 4))
        ctk.CTkLabel(banner,
                     text="Nessun database trovato.\n"
                          "Crea ora la tua Master Password:\n"
                          "verrà usata per cifrare tutte le credenziali.\n"
                          "Conservala in un posto sicuro — non è recuperabile.",
                     font=("Segoe UI", 12),
                     justify="center",
                     wraplength=340).grid(row=1, column=0, padx=16, pady=(0, 14))
        start_row = 1
    else:
        ctk.CTkLabel(login, text="🔒  Secure Account Manager",
                     font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, pady=(24, 8))
        start_row = 0

    lbl_pwd = "Crea Master Password:" if is_first else "Master Password:"
    ctk.CTkLabel(login, text=lbl_pwd, anchor="w").grid(
        row=start_row + 1, column=0, padx=24, sticky="w")

    entry_master = ctk.CTkEntry(login, show="*", height=42)
    entry_master.grid(row=start_row + 2, column=0, padx=24, pady=(2, 8), sticky="ew")

    if is_first:
        sf = ctk.CTkFrame(login, fg_color="transparent")
        sf.grid(row=start_row + 3, column=0, padx=24, pady=(0, 4), sticky="ew")
        sf.columnconfigure(0, weight=1)
        strength_bar_login = ctk.CTkProgressBar(sf)
        strength_bar_login.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        strength_bar_login.set(0)
        strength_lbl_login = ctk.CTkLabel(sf, text="", width=90, anchor="w")
        strength_lbl_login.grid(row=0, column=1)
        entry_master.bind("<KeyRelease>",
            lambda e: apply_strength(strength_bar_login,
                                     strength_lbl_login,
                                     entry_master.get()))

        ctk.CTkLabel(login, text="Conferma Master Password:", anchor="w").grid(
            row=start_row + 4, column=0, padx=24, sticky="w")
        entry_confirm = ctk.CTkEntry(login, show="*", height=42)
        entry_confirm.grid(row=start_row + 5, column=0, padx=24, pady=(2, 12), sticky="ew")
        entry_confirm.bind("<Return>", lambda e: login_attempt())
    else:
        entry_confirm = None
        entry_master.bind("<Return>", lambda e: login_attempt())

    def login_attempt():
        pwd = entry_master.get()
        if not pwd:
            messagebox.showwarning("Attenzione", "Inserisci la Master Password.", parent=login)
            return

        if is_first:
            if len(pwd) < 8:
                messagebox.showwarning("Password troppo corta",
                                       "La Master Password deve essere di almeno 8 caratteri.",
                                       parent=login)
                return
            if entry_confirm and pwd != entry_confirm.get():
                messagebox.showerror("Errore", "Le due password non coincidono.", parent=login)
                return

        if load_vault(pwd):
            login.destroy()
            main_app()
        else:
            messagebox.showerror("Accesso negato", "Master Password errata.", parent=login)

    btn_lbl = "Crea Vault e Accedi" if is_first else "Accedi"
    ctk.CTkButton(login, text=btn_lbl, height=42,
                  command=login_attempt).grid(
        row=start_row + 6, column=0, padx=24, pady=12, sticky="ew")

    login.mainloop()


# ================= MAIN APP =================

def main_app():

    root = ctk.CTk()
    root.title(f"Secure Account Manager v{APP_VERSION}")
    root.geometry("650x900")
    root.minsize(480, 620)

    selected        = {"name": None}
    account_buttons = {}

    def open_dashboard():
        overlay = ctk.CTkFrame(root, fg_color="#0A0A0A")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        frame = ctk.CTkFrame(overlay, width=480, corner_radius=20)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        frame.columnconfigure(0, weight=1)

        total      = len(accounts)
        duplicates = len(get_duplicates())
        weak = strong = 0
        for acc in accounts.values():
            if password_strength(acc["password"]) <= 2:
                weak  += 1
            else:
                strong += 1
        score = int((strong / total) * 100) if total else 0

        ctk.CTkLabel(frame, text="📊  Dashboard Sicurezza",
                     font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, pady=20, padx=30)

        rows = [
            ("Account Totali",       str(total),      "#FFFFFF"),
            ("Password Duplicate",   str(duplicates), "#FF6B6B" if duplicates else "#6BFF8E"),
            ("Password Deboli",      str(weak),       "#FFA94D" if weak else "#6BFF8E"),
            ("Password Forti",       str(strong),     "#6BFF8E"),
            ("Indice Sicurezza",     f"{score}%",     "#6BFF8E" if score >= 70
                                                       else "#FFA94D" if score >= 40
                                                       else "#FF6B6B"),
        ]
        for i, (label, value, color) in enumerate(rows):
            row_frame = ctk.CTkFrame(frame, fg_color="#1E1E1E", corner_radius=8)
            row_frame.grid(row=i + 1, column=0, padx=20, pady=4, sticky="ew")
            row_frame.columnconfigure(0, weight=1)
            ctk.CTkLabel(row_frame, text=label, anchor="w",
                         font=("Segoe UI", 13)).grid(row=0, column=0, padx=12, pady=8)
            ctk.CTkLabel(row_frame, text=value, anchor="e",
                         font=("Segoe UI", 13, "bold"),
                         text_color=color).grid(row=0, column=1, padx=12)

        ctk.CTkButton(frame, text="Chiudi",
                      command=overlay.destroy).grid(
            row=len(rows) + 1, column=0, padx=20, pady=20, sticky="ew")

    def open_tutorial():
        tut = ctk.CTkToplevel(root)
        tut.title("📖  Tutorial – Come usare l'app")
        tut.geometry("580x640")
        tut.minsize(480, 500)
        tut.grab_set()
        tut.columnconfigure(0, weight=1)
        tut.rowconfigure(1, weight=1)

        ctk.CTkLabel(tut, text="📖  Guida all'uso",
                     font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, pady=16, padx=20)

        scroll = ctk.CTkScrollableFrame(tut)
        scroll.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="nsew")
        scroll.columnconfigure(0, weight=1)

        sezioni = [
            ("🔐  Master Password",
             "La Master Password è l'unica chiave che protegge tutto il vault.\n"
             "Viene usata per derivare una chiave crittografica AES-256 tramite PBKDF2.\n"
             "Se la dimentichi, non è possibile recuperare i dati: non esiste reset.\n"
             "Sceglila lunga, complessa e conservala in un posto sicuro."),
            ("➕  Aggiungere un Account",
             "Compila i campi 'Nome Account', 'Username' e 'Password' nella parte alta.\n"
             "Puoi usare il pulsante 'Genera Password' per creare una password sicura automatica.\n"
             "L'indicatore di forza mostra in tempo reale la qualità della password.\n"
             "Premi 'Aggiungi Account' per salvare nel vault cifrato."),
            ("🔎  Cercare un Account",
             "Usa la barra di ricerca per filtrare la lista in tempo reale.\n"
             "La ricerca è case-insensitive e funziona sul nome dell'account."),
            ("✏️  Modificare un Account",
             "Seleziona un account dalla lista (diventa evidenziato in blu).\n"
             "Premi 'Modifica' nella barra azioni in basso.\n"
             "Nella finestra che si apre puoi cambiare username e/o password.\n"
             "Puoi anche generare una nuova password direttamente dal popup."),
            ("📋  Copiare Credenziali",
             "Seleziona un account, poi premi 'Copia User' o 'Copia Pwd'.\n"
             "Le credenziali vengono copiate negli appunti e cancellate automaticamente\n"
             "dopo 15 secondi per motivi di sicurezza."),
            ("🗑️  Eliminare un Account",
             "Seleziona l'account e premi 'Elimina'.\n"
             "Viene richiesta conferma prima di procedere.\n"
             "L'operazione è irreversibile: il vault viene aggiornato immediatamente."),
            ("📊  Dashboard Sicurezza",
             "Mostra una panoramica dello stato del vault:\n"
             "• Account totali\n"
             "• Password duplicate (evidenziate in rosso nella lista)\n"
             "• Password deboli e forti\n"
             "• Indice di sicurezza percentuale"),
            ("💾  Backup e Ripristino",
             "Dal menu 'Vault' in basso puoi:\n"
             "• Esportare il vault cifrato in una posizione a tua scelta (backup).\n"
             "• Importare un vault precedentemente esportato (sovrascrive quello attuale).\n"
             "• Eliminare definitivamente il vault dal PC (utile su macchine condivise).\n"
             "Il file esportato è cifrato: senza la Master Password è illeggibile."),
            ("⚠️  Note di Sicurezza",
             "• Il vault è cifrato con Fernet (AES-128-CBC + HMAC-SHA256).\n"
             "• La chiave viene derivata con PBKDF2-HMAC-SHA256 (390.000 iterazioni).\n"
             "• I dati vengono salvati solo in locale, mai inviati in rete.\n"
             "• Su PC condivisi usa la funzione 'Elimina Vault' prima di lasciare la macchina."),
        ]

        for i, (titolo, testo) in enumerate(sezioni):
            sec = ctk.CTkFrame(scroll, fg_color="#1A1A2E", corner_radius=10)
            sec.grid(row=i, column=0, pady=6, sticky="ew")
            sec.columnconfigure(0, weight=1)
            ctk.CTkLabel(sec, text=titolo,
                         font=("Segoe UI", 13, "bold"),
                         anchor="w").grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")
            ctk.CTkLabel(sec, text=testo,
                         font=("Segoe UI", 11),
                         justify="left",
                         anchor="w",
                         wraplength=480).grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        ctk.CTkButton(tut, text="Chiudi",
                      command=tut.destroy).grid(
            row=2, column=0, padx=20, pady=12, sticky="ew")

    def open_credits():
        cr = ctk.CTkToplevel(root)
        cr.title("ℹ️  Informazioni")
        cr.geometry("400x380")  # FIX: era 400x320, aumentato per evitare troncamento pulsante
        cr.resizable(False, False)
        cr.grab_set()
        cr.columnconfigure(0, weight=1)

        ctk.CTkLabel(cr, text="🔐  Secure Account Manager",
                     font=("Segoe UI", 18, "bold")).grid(row=0, column=0, pady=(28, 4))
        ctk.CTkLabel(cr, text=f"Versione {APP_VERSION}",
                     font=("Segoe UI", 13),
                     text_color="#8899AA").grid(row=1, column=0, pady=2)

        sep = ctk.CTkFrame(cr, height=2, fg_color="#2A3A4A")
        sep.grid(row=2, column=0, padx=40, pady=16, sticky="ew")

        ctk.CTkLabel(cr, text="Sviluppato da",
                     font=("Segoe UI", 12),
                     text_color="#8899AA").grid(row=3, column=0)
        ctk.CTkLabel(cr, text=APP_AUTHOR,
                     font=("Segoe UI", 15, "bold")).grid(row=4, column=0, pady=4)
        ctk.CTkLabel(cr, text=f"© {APP_YEAR}  –  Tutti i diritti riservati",
                     font=("Segoe UI", 11),
                     text_color="#8899AA").grid(row=5, column=0, pady=2)

        sep2 = ctk.CTkFrame(cr, height=2, fg_color="#2A3A4A")
        sep2.grid(row=6, column=0, padx=40, pady=16, sticky="ew")

        ctk.CTkLabel(cr, text="Crittografia: PBKDF2-HMAC-SHA256 + AES (Fernet)",
                     font=("Segoe UI", 10),
                     text_color="#5A6A7A").grid(row=7, column=0, pady=2)

        ctk.CTkButton(cr, text="Chiudi",
                      command=cr.destroy).grid(row=8, column=0, padx=40, pady=16, sticky="ew")

    def open_vault_menu():
        vm = ctk.CTkToplevel(root)
        vm.title("💾  Gestione Vault")
        vm.geometry("400x340")
        vm.resizable(False, False)
        vm.grab_set()
        vm.columnconfigure(0, weight=1)

        ctk.CTkLabel(vm, text="💾  Gestione Vault",
                     font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, pady=20, padx=24)

        def do_backup():
            dest = filedialog.asksaveasfilename(
                parent=vm,
                title="Salva backup vault",
                defaultextension=".dat",
                filetypes=[("Vault cifrato", "*.dat"), ("Tutti i file", "*.*")],
                initialfile="vault_backup.dat"
            )
            if dest:
                shutil.copy2(VAULT_FILE, dest)
                messagebox.showinfo("Backup completato",
                                    f"Vault esportato con successo in:\n{dest}",
                                    parent=vm)

        ctk.CTkButton(vm, text="📤  Esporta Backup",
                      height=44,
                      command=do_backup).grid(row=1, column=0, padx=24, pady=6, sticky="ew")
        ctk.CTkLabel(vm,
                     text="Salva una copia cifrata del vault in una posizione a tua scelta.",
                     font=("Segoe UI", 10), text_color="#8899AA",
                     wraplength=340).grid(row=2, column=0, padx=24)

        def do_import():
            src = filedialog.askopenfilename(
                parent=vm,
                title="Importa vault",
                filetypes=[("Vault cifrato", "*.dat"), ("Tutti i file", "*.*")]
            )
            if not src:
                return
            if not messagebox.askyesno(
                    "Conferma importazione",
                    "Importando questo vault SOVRASCRIVERAI quello attuale.\n"
                    "Assicurati di conoscere la Master Password del file che stai importando.\n\n"
                    "Continuare?",
                    parent=vm):
                return
            shutil.copy2(src, VAULT_FILE)
            messagebox.showinfo("Importazione completata",
                                "Vault importato. Riavvia l'applicazione per accedere.",
                                parent=vm)
            vm.destroy()
            root.destroy()

        ctk.CTkButton(vm, text="📥  Importa Vault",
                      height=44,
                      command=do_import).grid(row=3, column=0, padx=24, pady=(14, 6), sticky="ew")
        ctk.CTkLabel(vm,
                     text="Sostituisce il vault attuale con un file importato.",
                     font=("Segoe UI", 10), text_color="#8899AA",
                     wraplength=340).grid(row=4, column=0, padx=24)

        def do_delete_vault():
            if not messagebox.askyesno(
                    "⚠️  Elimina Vault",
                    "Stai per ELIMINARE DEFINITIVAMENTE il vault e tutte le credenziali.\n"
                    "Questa operazione è IRREVERSIBILE.\n\n"
                    "Sei assolutamente sicuro?",
                    parent=vm):
                return
            if not messagebox.askyesno(
                    "Ultima conferma",
                    "Confermi l'eliminazione definitiva del vault?\n"
                    "Non sarà possibile recuperare i dati.",
                    parent=vm):
                return
            os.remove(VAULT_FILE)
            messagebox.showinfo("Vault eliminato",
                                "Il vault è stato eliminato dal disco.\n"
                                "L'applicazione verrà chiusa.",
                                parent=vm)
            vm.destroy()
            root.destroy()

        ctk.CTkButton(vm, text="🗑️  Elimina Vault dal PC",
                      height=44,
                      fg_color="#6B0000", hover_color="#8B0000",
                      command=do_delete_vault).grid(
            row=5, column=0, padx=24, pady=(14, 6), sticky="ew")
        ctk.CTkLabel(vm,
                     text="Rimuove definitivamente il database dal disco. Non recuperabile.",
                     font=("Segoe UI", 10), text_color="#FF6B6B",
                     wraplength=340).grid(row=6, column=0, padx=24)

        ctk.CTkButton(vm, text="Chiudi",
                      command=vm.destroy).grid(row=7, column=0, padx=24, pady=16, sticky="ew")

    def refresh_accounts():
        for w in list_frame.winfo_children():
            w.destroy()
        account_buttons.clear()
        search     = search_var.get().lower()
        duplicates = get_duplicates()

        for name, data in accounts.items():
            if search in name.lower():
                color = "#1E1E1E"
                if data["password"] in duplicates:
                    color = "#5A0000"
                btn = ctk.CTkButton(
                    list_frame, text=name,
                    fg_color=color, height=45,
                    command=lambda n=name: select_account(n)
                )
                btn.pack(fill="x", pady=4)
                account_buttons[name] = btn

    def select_account(name):
        selected["name"] = name
        for btn in account_buttons.values():
            btn.configure(fg_color="#1E1E1E")
        account_buttons[name].configure(fg_color="#2E7CCB")

    def copy_username():
        name = selected["name"]
        if name:
            root.clipboard_clear()
            root.clipboard_append(accounts[name]["username"])
            root.after(15000, lambda: root.clipboard_clear())

    def copy_password():
        name = selected["name"]
        if name:
            root.clipboard_clear()
            root.clipboard_append(accounts[name]["password"])
            root.after(15000, lambda: root.clipboard_clear())

    def delete_account():
        name = selected["name"]
        if name:
            if messagebox.askyesno("Conferma", f"Eliminare l'account '{name}'?"):
                del accounts[name]
                save_vault()
                selected["name"] = None
                refresh_accounts()

    def edit_account():
        name = selected["name"]
        if not name:
            messagebox.showwarning("Attenzione", "Seleziona prima un account da modificare.")
            return

        popup = ctk.CTkToplevel(root)
        popup.title(f"✏️  Modifica — {name}")
        popup.geometry("440x460")
        popup.minsize(360, 420)
        popup.grab_set()
        popup.columnconfigure(0, weight=1)

        ctk.CTkLabel(popup, text=f"✏️  Modifica: {name}",
                     font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, pady=20, padx=20, sticky="ew")

        ctk.CTkLabel(popup, text="Username", anchor="w").grid(
            row=1, column=0, padx=20, sticky="w")
        edit_username = ctk.CTkEntry(popup, height=40)
        edit_username.insert(0, accounts[name]["username"])
        edit_username.grid(row=2, column=0, padx=20, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(popup, text="Password", anchor="w").grid(
            row=3, column=0, padx=20, sticky="w")
        edit_password = ctk.CTkEntry(popup, height=40, show="*")
        edit_password.insert(0, accounts[name]["password"])
        edit_password.grid(row=4, column=0, padx=20, pady=(0, 6), sticky="ew")

        psf = ctk.CTkFrame(popup, fg_color="transparent")
        psf.grid(row=5, column=0, padx=20, pady=4, sticky="ew")
        psf.columnconfigure(0, weight=1)
        pop_bar   = ctk.CTkProgressBar(psf)
        pop_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        pop_label = ctk.CTkLabel(psf, text="", width=90, anchor="w")
        pop_label.grid(row=0, column=1)

        def upd(*_):
            apply_strength(pop_bar, pop_label, edit_password.get())

        edit_password.bind("<KeyRelease>", upd)
        upd()

        ctk.CTkButton(popup, text="🔀  Genera Password",
                      command=lambda: (
                          edit_password.delete(0, "end"),
                          edit_password.insert(0, generate_password()),
                          upd()
                      )).grid(row=6, column=0, padx=20, pady=6, sticky="ew")

        def confirm_edit():
            new_user = edit_username.get().strip()
            new_pwd  = edit_password.get().strip()
            if not new_user or not new_pwd:
                messagebox.showwarning("Errore",
                                       "Username e password non possono essere vuoti.",
                                       parent=popup)
                return
            accounts[name]["username"] = new_user
            accounts[name]["password"] = new_pwd
            save_vault()
            refresh_accounts()
            if name in account_buttons:
                select_account(name)
            popup.destroy()

        ctk.CTkButton(popup, text="✅  Salva Modifiche",
                      fg_color="#1A6B2A", hover_color="#228035",
                      command=confirm_edit).grid(
            row=7, column=0, padx=20, pady=14, sticky="ew")

    def add_account():
        name     = entry_name.get().strip()
        username = entry_username.get().strip()
        password = entry_password.get().strip()
        if not name or not username or not password:
            messagebox.showwarning("Errore", "Compila tutti i campi.")
            return
        if name in accounts:
            if not messagebox.askyesno("Attenzione",
                                       f"L'account '{name}' esiste già. Sovrascrivere?"):
                return
        accounts[name] = {"username": username, "password": password}
        save_vault()
        refresh_accounts()

    def update_strength(*_):
        apply_strength(strength_bar, strength_label, entry_password.get())

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    main_frame = ctk.CTkFrame(root, corner_radius=20)
    main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(7, weight=1)

    header = ctk.CTkFrame(main_frame, fg_color="transparent")
    header.grid(row=0, column=0, padx=20, pady=(18, 6), sticky="ew")
    header.columnconfigure(0, weight=1)
    ctk.CTkLabel(header, text="🔐  Secure Account Manager",
                 font=("Segoe UI", 24, "bold"), anchor="center").grid(
        row=0, column=0, sticky="ew")
    ctk.CTkLabel(header, text=f"v{APP_VERSION}  –  {APP_AUTHOR}  –  {APP_YEAR}",
                 font=("Segoe UI", 10), text_color="#5A7A9A",
                 anchor="center").grid(row=1, column=0, sticky="ew")

    entry_name = ctk.CTkEntry(main_frame, placeholder_text="Nome Account", height=45)
    entry_name.grid(row=1, column=0, padx=20, pady=6, sticky="ew")

    entry_username = ctk.CTkEntry(main_frame, placeholder_text="Username", height=45)
    entry_username.grid(row=2, column=0, padx=20, pady=6, sticky="ew")

    entry_password = ctk.CTkEntry(main_frame, placeholder_text="Password",
                                  height=45, show="*")
    entry_password.grid(row=3, column=0, padx=20, pady=6, sticky="ew")
    entry_password.bind("<KeyRelease>", update_strength)

    sf = ctk.CTkFrame(main_frame, fg_color="transparent")
    sf.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
    sf.columnconfigure(0, weight=1)
    strength_bar   = ctk.CTkProgressBar(sf)
    strength_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))
    strength_bar.set(0)
    strength_label = ctk.CTkLabel(sf, text="", width=90, anchor="w")
    strength_label.grid(row=0, column=1)

    br = ctk.CTkFrame(main_frame, fg_color="transparent")
    br.grid(row=5, column=0, padx=20, pady=8, sticky="ew")
    br.columnconfigure(0, weight=1)
    br.columnconfigure(1, weight=1)
    ctk.CTkButton(br, text="🔀  Genera Password",
                  command=lambda: (
                      entry_password.delete(0, "end"),
                      entry_password.insert(0, generate_password()),
                      update_strength()
                  )).grid(row=0, column=0, padx=(0, 6), sticky="ew")
    ctk.CTkButton(br, text="➕  Aggiungi Account",
                  command=add_account).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    search_var = ctk.StringVar()
    sf2 = ctk.CTkFrame(main_frame, fg_color="transparent")
    sf2.grid(row=6, column=0, padx=20, pady=(8, 4), sticky="ew")
    sf2.columnconfigure(1, weight=1)
    ctk.CTkLabel(sf2, text="🔎", font=("Segoe UI", 18)).grid(row=0, column=0, padx=(0, 6))
    ctk.CTkEntry(sf2, textvariable=search_var,
                 placeholder_text="Cerca account...", height=45).grid(
        row=0, column=1, sticky="ew")
    search_var.trace_add("write", lambda *_: refresh_accounts())

    lc = ctk.CTkFrame(main_frame)
    lc.grid(row=7, column=0, padx=20, pady=6, sticky="nsew")
    lc.columnconfigure(0, weight=1)
    lc.rowconfigure(0, weight=1)
    list_frame = ctk.CTkScrollableFrame(lc)
    list_frame.pack(fill="both", expand=True)

    action_frame = ctk.CTkFrame(main_frame)
    action_frame.grid(row=8, column=0, padx=20, pady=(6, 4), sticky="ew")

    row1 = ctk.CTkFrame(action_frame, fg_color="transparent")
    row1.pack(fill="x", padx=6, pady=(8, 2))
    for i in range(5):
        row1.columnconfigure(i, weight=1)

    acc_btns = [
        ("📊 Dashboard",  None,      None,       open_dashboard),
        ("👤 Copia User", None,      None,       copy_username),
        ("🔑 Copia Pwd",  None,      None,       copy_password),
        ("✏️ Modifica",   "#1A5C8A", "#1E72AA",  edit_account),
        ("🗑️ Elimina",    "#8B0000", "#A00000",  delete_account),
    ]
    for col, (text, fg, hover, cmd) in enumerate(acc_btns):
        kw = {"text": text, "command": cmd, "height": 38}
        if fg:    kw["fg_color"]    = fg
        if hover: kw["hover_color"] = hover
        ctk.CTkButton(row1, **kw).grid(row=0, column=col, padx=3, sticky="ew")

    row2 = ctk.CTkFrame(action_frame, fg_color="transparent")
    row2.pack(fill="x", padx=6, pady=(2, 8))
    for i in range(3):
        row2.columnconfigure(i, weight=1)

    extra_btns = [
        ("💾 Vault",    "#1A3A2A", "#1E5A3A", open_vault_menu),
        ("📖 Tutorial", "#2A2A1A", "#4A4A1A", open_tutorial),
        ("ℹ️ Crediti",  "#1A1A3A", "#2A2A5A", open_credits),
    ]
    for col, (text, fg, hover, cmd) in enumerate(extra_btns):
        ctk.CTkButton(row2, text=text, command=cmd,
                      fg_color=fg, hover_color=hover,
                      height=36).grid(row=0, column=col, padx=3, sticky="ew")

    refresh_accounts()
    root.mainloop()


if __name__ == "__main__":
    login_window()