import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import psutil
import pydivert
import keyboard

# --- AYARLAR ---
TARGET_PROCESS = "sonoyuncuclient.exe"  # Hedef süreç güncellendi
LAG_KEY = "x"                           # Tetikleme tuşu
# ---------------

is_lagging = False
game_ip = None
filter_thread = None
running = True

def get_game_ip(status_label):
    """SonOyuncu uzak sunucu IP'sini bulur"""
    global game_ip
    status_label.config(text="SonOyuncu ağ bağlantısı aranıyor...\nLütfen bir sunucuya/maça girin.", foreground="orange")
    
    while game_ip is None and running:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() == TARGET_PROCESS.lower():
                    connections = proc.connections(kind='inet')
                    for conn in connections:
                        if conn.status == 'ESTABLISHED' and conn.raddr:
                            ip = conn.raddr.ip
                            # Yerel ağ adreslerini filtrele
                            if not ip.startswith(("127.", "192.168.", "10.", "172.")):
                                game_ip = ip
                                return
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(0.5)

def lag_switch_worker(status_label):
    """WinDivert filtre döngüsü"""
    global game_ip, is_lagging
    
    get_game_ip(status_label)
    if not running or game_ip is None:
        return
        
    status_label.config(text=f"SonOyuncu Bağlantısı Yakalandı!\nIP: {game_ip}\n'{LAG_KEY.upper()}' tuşuna basılı tutun.", foreground="green")
    
    filter_string = f"ip.DstAddr == {game_ip} and outbound"
    try:
        with pydivert.WinDivert(filter_string) as w:
            for packet in w:
                if is_lagging:
                    continue  # Paket engelleniyor
                else:
                    w.send(packet)
    except Exception as e:
        status_label.config(text="Sürücü Hatası! Sağ tıklayıp\nYönetici Olarak Çalıştırın.", foreground="red")

def on_key_event(e):
    """Tuş hareketlerini dinler ve menüde bildirim verir"""
    global is_lagging
    if game_ip is None:
        return

    if e.name == LAG_KEY:
        if e.event_type == keyboard.KEY_DOWN and not is_lagging:
            is_lagging = True
            # Menüde görsel bildirim ver
            status_lbl.config(text=">>> LAG AKTİF <<<", foreground="red")
            
        elif e.event_type == keyboard.KEY_UP and is_lagging:
            is_lagging = False
            # Menü bildirimini temizle ve eski haline getir
            status_lbl.config(text=f"Bağlantı Temiz.\nIP: {game_ip}", foreground="green")

def on_closing():
    global running
    running = False
    root.destroy()

# --- GÖRSEL ARAYÜZ ---
root = tk.Tk()
root.title("SonOyuncu Lag Switch")
root.geometry("380x200")
root.resizable(False, False)
root.protocol("WM_DELETE_WINDOW", on_closing)

frame = ttk.Frame(root, padding="20")
frame.pack(fill=tk.BOTH, expand=True)

title_lbl = ttk.Label(frame, text="SonOyuncu Otocut Geciktirici", font=("Arial", 11, "bold"))
title_lbl.pack(pady=5)

status_lbl = ttk.Label(frame, text="Sistem başlatılıyor...", font=("Arial", 10, "bold"), justify=tk.CENTER)
status_lbl.pack(pady=20)

# Klavye dinleyicisini bağla ve işlemi başlat
keyboard.hook(on_key_event)
filter_thread = threading.Thread(target=lag_switch_worker, args=(status_lbl,), daemon=True)
filter_thread.start()

root.mainloop()
