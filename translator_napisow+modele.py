import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import google.generativeai as genai
import threading
import time
import os
import re

def select_file():
    filepath = filedialog.askopenfilename(filetypes=[("Subtitle Files", "*.srt")])
    if filepath:
        file_label.config(text=filepath)
        app_data['filepath'] = filepath

def log_message(msg):
    log_area.insert(tk.END, msg + "\n")
    log_area.see(tk.END)

def fetch_models():
    api_key = api_entry.get().strip()
    if not api_key:
        messagebox.showerror("Błąd", "Najpierw podaj klucz Google API!")
        return

    def do_fetch():
        try:
            log_message("Łączenie z API w celu pobrania modeli...")
            genai.configure(api_key=api_key)
            available_models = []
            
            # Pobieranie modeli i filtrowanie tych, które obsługują generowanie tekstu
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    # Usuwamy prefiks 'models/' dla lepszej czytelności w GUI
                    clean_name = m.name.replace('models/', '')
                    available_models.append(clean_name)
            
            # Aktualizacja GUI musi odbyć się w głównym wątku, dlatego używamy root.after
            root.after(0, update_model_dropdown, available_models)
            
        except Exception as e:
            root.after(0, lambda err=e: messagebox.showerror("Błąd", f"Nie udało się pobrać modeli:\n{str(err)}"))
            root.after(0, lambda: log_message("❌ Błąd pobierania modeli."))

    # Uruchamiamy pobieranie w osobnym wątku
    threading.Thread(target=do_fetch, daemon=True).start()

def update_model_dropdown(models):
    if not models:
        log_message("Nie znaleziono modeli obsługujących tekst dla tego klucza.")
        return
        
    model_combobox['values'] = models
    
    # Rekomendowany model ustawiany jako domyślny
    recommended_model = "gemini-2.5-flash"
    if recommended_model in models:
        model_combobox.set(recommended_model)
    else:
        model_combobox.set(models[0]) # Wybierz pierwszy z listy, jeśli brakuje 2.5-flash
        
    log_message(f"✅ Pobrano listę modeli. Domyślnie wybrano: {model_combobox.get()}")

def process_translation():
    api_key = api_entry.get().strip()
    file_path = app_data.get('filepath')
    context = context_entry.get("1.0", tk.END).strip()
    selected_model = model_combobox.get()

    if not api_key:
        messagebox.showerror("Błąd", "Podaj klucz Google API!")
        return
    if not selected_model:
        messagebox.showerror("Błąd", "Wybierz model z listy! Kliknij 'Pobierz modele'.")
        return
    if not file_path:
        messagebox.showerror("Błąd", "Wybierz plik z napisami (.srt)!")
        return

    # Uruchamiamy tłumaczenie w osobnym wątku, żeby nie zaciąć okna programu
    threading.Thread(target=run_translation, args=(api_key, file_path, context, selected_model), daemon=True).start()

def run_translation(api_key, file_path, context, selected_model_name):
    try:
        log_message(f"Konfigurowanie połączenia z API (Model: {selected_model_name})...")
        genai.configure(api_key=api_key)
        
        # Inicjalizacja wybranego przez użytkownika modelu
        model = genai.GenerativeModel(selected_model_name)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Dzielenie napisów na bloki
        blocks = re.split(r'\n\s*\n', content.strip())
        translated_blocks = []
        
        chunk_size = 150 # Duża paczka, by zmieścić się w limitach
        total_chunks = (len(blocks) + chunk_size - 1) // chunk_size

        log_message(f"Znaleziono {len(blocks)} linii dialogowych. Podzielono na {total_chunks} paczek.")

        for i in range(0, len(blocks), chunk_size):
            chunk = blocks[i:i+chunk_size]
            chunk_text = '\n\n'.join(chunk)

            prompt = f"""
            Jesteś profesjonalnym tłumaczem napisów filmowych.
            Przetłumacz poniższe napisy z języka angielskiego na polski.
            KONTEKST FILMU: {context if context else 'Brak specyficznego kontekstu.'}

            WYMOGI:
            1. Zwróć DOKŁADNIE ten sam format SRT (indeks, czas, tekst). Nie pomijaj żadnego bloku!
            2. Nie zmieniaj znaczników czasu.
            3. Nie dodawaj żadnych własnych komentarzy ani tagów markdown.
            4. Tłumacz naturalnie, biorąc pod uwagę podany kontekst.

            NAPISY:
            {chunk_text}
            """
            
            log_message(f"Tłumaczenie paczki {i//chunk_size + 1} z {total_chunks}...")
            response = model.generate_content(prompt)
            
            # Czyszczenie z ewentualnych znaczników markdown
            clean_text = response.text.replace("```srt", "").replace("```", "").strip()
            translated_blocks.append(clean_text)

            # Pauza chroniąca przed blokadą anty-spamową Google (Error 429)
            if i + chunk_size < len(blocks):
                log_message("Czekam 16 sekund przed wysłaniem kolejnej paczki...")
                time.sleep(16)

        # Zapisywanie nowego pliku
        out_path = file_path.replace('.srt', '_PL.srt')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(translated_blocks))

        log_message(f"✅ ZAKOŃCZONO! Zapisano plik: {out_path}")

    except Exception as e:
        log_message(f"❌ WYSTĄPIŁ BŁĄD: {str(e)}")

# --- Inicjalizacja GUI ---
app_data = {}
root = tk.Tk()
root.title("Geminislator by Krzysiek")
root.geometry("550x700") # Zwiększono lekko okno, by pomieścić nowy element

tk.Label(root, text="Klucz Google Gemini API:").pack(pady=(10,0))
api_entry = tk.Entry(root, width=60, show="*")
api_entry.pack(pady=5)

# --- Nowa sekcja: Wybór modelu ---
model_frame = tk.Frame(root)
model_frame.pack(pady=5)

tk.Label(model_frame, text="Model (Zalecany: gemini-2.5-flash):").grid(row=0, column=0, padx=5)

model_combobox = ttk.Combobox(model_frame, width=25, state="readonly")
model_combobox.grid(row=0, column=1, padx=5)

fetch_btn = tk.Button(model_frame, text="Pobierz modele", command=fetch_models)
fetch_btn.grid(row=0, column=2, padx=5)
# ---------------------------------

tk.Label(root, text="Opis filmu (Opcjonalne, ale zalecane):").pack(pady=(10,0))
context_entry = tk.Text(root, width=60, height=5)
context_entry.pack(pady=5)

tk.Button(root, text="Wybierz plik .srt", command=select_file).pack(pady=10)
file_label = tk.Label(root, text="Brak wybranego pliku", fg="blue")
file_label.pack()

tk.Button(root, text="TŁUMACZ", bg="green", fg="white", font=("Arial", 12, "bold"), command=process_translation).pack(pady=20)

tk.Label(root, text="Logi z postępu pracy:").pack()
log_area = scrolledtext.ScrolledText(root, width=60, height=12)
log_area.pack(pady=5)

root.mainloop()