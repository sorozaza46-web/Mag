import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import pydivert
import keyboard

# --- AYARLAR ---
LAG_KEY = "x"  # Lag switch'i tetikleyecek tuş
# ---------------

is_lagging = False
game_ip = None
target_process = None
filter_thread = None

def get_running_processes():
    """Arka planda çalışan aktif .exe süreçlerini listeler"""
    processes = set()
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name and name.endswith(".exe"):
                processes.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(list(processes))

def find_game_ip_and_start_filter(process_name, status_label):
    """Seçilen oyunun harici IP'sini bulur ve WinDivert filtresini başlatır"""
    global game_ip, is_lagging
    
    status_label.config(text=f"[{process_name}] için ağ bağlantısı aranıyor...\nLütfen oyunda bir maça girin.", foreground="orange")
    
    # Oyun sunucu IP'sini bulma döngüsü
    while game_ip is None and target_process == process_name:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() == process_name.lower():
                    connections = proc.connections(kind='inet')
                    for conn in connections:
                        if conn.status == 'ESTABLISHED' and conn.raddr:
                            # Yerel ağ IP'lerini filtrele
                            if not conn.raddr.ip.startswith("127.") and not conn.raddr.ip.startswith("192.168."):
                                game_ip = conn.raddr.ip
                                break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(1)
    
    if target_process != process_name:
        return # Eğer kullanıcı başka bir süreç seçtiyse iptal et

    status_label.config(text=f"Bağlantı Kuruldu!\nIP: {game_ip}\nOyun içinde '{LAG_KEY.upper()}' tuşuna basılı tutun.", foreground="green")
    
    # WinDivert Ağ Filtresi
    filter_string = f"ip.DstAddr == {game_ip} and outbound"
    try:
        with pydivert.WinDivert(filter_string) as w:
            for packet in w:
                if is_lagging:
                    continue  # Paket engelleniyor
                else:
                    w.send(packet)
    except Exception as e:
        status_label.config(text=f"Sürücü Hatası!\nYönetici olarak çalıştırdığınızdan emin olun.", foreground="red")

def on_key_event(e):
    """Klavye tuş basışlarını dinler"""
    global is_lagging
    if game_ip is None:
        return

    if e.name == LAG_KEY:
        if e.event_type == keyboard.KEY_DOWN and not is_lagging:
            is_lagging = True
        elif e.event_type == keyboard.KEY_UP and is_lagging:
            is_lagging = False

def start_lag_switch(combobox, status_label):
    """Seçilen süreç için arka plan thread'lerini tetikler"""
    global target_process, game_ip, filter_thread
    
    selected = combobox.get()
    if not selected:
        messagebox.showwarning("Uyarı", "Lütfen listeden bir oyun/süreç seçin!")
        return
    
    target_process = selected
    game_ip = None # Eski IP'yi temizle
    
    # Arayüzün donmaması için ağ dinleyicisini yeni bir Thread'de başlat
    filter_thread = threading.Thread(target=find_game_ip_and_start_filter, args=(target_process, status_label), daemon=True)
    filter_thread.start()

def refresh_list(combobox):
    """Süreç listesini günceller"""
    procs = get_running_processes()
    combobox['values'] = procs
    if procs:
        combobox.set("Bir süreç seçin...")

# --- TKINTER ARAYÜZÜ ---
root = tk.Tk()
root.title("Lag Switch Manager")
root.geometry("400x250")
root.resizable(False, False)

frame = ttk.Frame(root, padding="20")
frame.pack(fill=tk.BOTH, expand=True)

# Süreç Seçim Alanı
ttk.Label(frame, text="Hedef Oyunu Seçin (.exe):", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
proc_combobox = ttk.Combobox(frame, width=40, state="readonly")
proc_combobox.pack(fill=tk.X, pady=5)

# Butonlar Paneli
btn_frame = ttk.Frame(frame)
btn_frame.pack(fill=tk.X, pady=10)

ttk.Button(btn_frame, text="Yenile", command=lambda: refresh_list(proc_combobox)).pack(side=tk.LEFT, padx=5)
ttk.Button(btn_frame, text="Filtreyi Başlat", command=lambda: start_lag_switch(proc_combobox, status_lbl)).pack(side=tk.RIGHT, padx=5)

# Durum Bilgisi
status_lbl = ttk.Label(frame, text="Lütfen listeden oyununuzu seçip Başlat'a tıklayın.", font=("Arial", 9), justify=tk.CENTER)
status_lbl.pack(pady=20)

# İlk yüklemede süreçleri getir ve klavyeyi dinlemeye başla
refresh_list(proc_combobox)
keyboard.hook(on_key_event)

root.mainloop()
  
