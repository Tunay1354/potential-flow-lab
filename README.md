# Potential Flow Lab — Arayüz prototipi

Bu sürüm sadece **arayüzü görmek ve karar vermek** için. Butonların çoğu çalışmıyor;
tıklayınca alttaki status bar'da "Prototype: … is not connected yet" yazar.
Ekrandaki akış resmi geçici bir demodur (lifting cylinder), gerçek fizik motoru değildir.

Çalışan kısımlar: toolbar'dan açılan parametre dialogları, Elements menüsü/listesinden
"Edit…", View → Theme (Light/Dark), plot'ta zoom/pan (mouse tekerleği ve sürükleme),
fare plot üzerindeyken alttaki probe (u, v, |V|, Cp), panelleri taşıma/kapatma.

## Çalıştırma (Windows, VS Code)

1. Klasörü VS Code ile aç: **File → Open Folder…**
2. Terminal aç: **Terminal → New Terminal**
3. Python kurulu mu kontrol et:
   ```
   python --version
   ```
   3.10 veya daha yeni bir sürüm görmelisin. Görmüyorsan python.org'dan Python 3.12'yi kur ve
   kurulumun ilk ekranında **"Add python.exe to PATH"** kutusunu işaretle, sonra VS Code'u kapatıp aç.
4. Sanal ortam (virtual environment) oluştur ve aktive et:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```
   PowerShell "running scripts is disabled" hatası verirse bir kez şunu çalıştır:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (soruya `Y` de), sonra aktive etmeyi tekrar dene.
5. Paketleri kur:
   ```
   pip install -r requirements.txt
   ```
6. Programı başlat:
   ```
   python main.py
   ```
Sonraki seferlerde sadece 4. adımdaki `.venv\Scripts\activate` ve `python main.py` yeterli.

## Neyi değiştirmek için hangi dosya?

| Değiştirmek istediğin | Dosya |
|---|---|
| Renkler, font, boyutlar, panel genişliği, ikon boyutu | `app/theme.py` |
| Element isimleri, açıklamaları, formülleri, parametreleri, varsayılan değerler | `app/element_specs.py` |
| Toolbar ikonlarının çizimi | `app/icons.py` |
| Menüler, toolbar, panellerin yerleşimi, status bar | `app/main_window.py` |
| Sağdaki Elements ve Plot settings panelleri | `app/panels.py` |
| Parametre dialog'unun görünümü | `app/dialogs.py` |
| Plot alanı ve üstündeki bar | `app/canvas.py` |
| Demo akış (sonra silinecek) | `app/demo_flow.py` |
