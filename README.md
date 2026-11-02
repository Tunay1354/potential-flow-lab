# Flowy

Interactive 2D potential-flow simulator (Aerodynamics semester project, IZTECH Mechanical Engineering).

**Durum:** ROADMAP 1–21 tamam (fizik, streamline'lar, duvarlar, sector flow, undo / redo, stagnation point'ler,
alan katmanları, animasyon, export, Solid bodies, Surface pressure, GPU, `--verify` 102 / 102, kunduz, kod
temizliği). Sıradaki işler ve her paketin ayrıntısı: `ROADMAP.md`. Programın kullanımı: **Help → User guide (F1)**.

## Kurulum (Windows, VS Code) — bir kez

1. Repoyu GitHub Desktop ile clone'la → **Repository → Open in Visual Studio Code**.
2. **Terminal → New Terminal**:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```
   `requirements.txt` = programın çalışması için gereken paketler; `requirements-dev.txt` = onlar + `pytest`
   (testler) + `pyinstaller` (exe). Exe'yi kullanan kişinin bunlara ihtiyacı yok.
   - `python` bulunamazsa: python.org'dan Python kur, ilk ekranda **"Add python.exe to PATH"** işaretle.
   - PowerShell "running scripts is disabled" derse bir kez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Her seferinde

```
.venv\Scripts\activate             # satırın başında (.venv) görünmeli
python main.py                     # programı aç   (python main.py sahne.pflow: sahneyle aç)
python main.py --first-run         # ilk açılış gibi (kunduz turu önerir)
pytest                             # tüm testler
python main.py --verify            # doğrulama raporu → verification/ (102 / 102 olmalı)
```
Güncelleme: GitHub Desktop → **Fetch origin → Pull origin**. `requirements*.txt` değiştiyse
`pip install -r requirements-dev.txt` komutunu tekrar çalıştır.

Bu bilgisayarda ilk açılış ~15–30 s (hızlı hesap çekirdekleri bir kez derlenir, donanım bir kez bulunur;
yükleme ekranı söyler); sonraki açılışlar birkaç saniye.

## Özellikler (kısa)

- **Elementler:** uniform flow, source / sink, vortex, doublet, sector (wedge) flow, symmetry wall (method of
  images; π/k köşeler, kanal, ucu kapalı kanal ve dikdörtgen kutu kesin — kapalı form satırlar). Ekle: soldaki palette (tıkla ya da plota sürükle) veya
  Elements → Add. Dialog, değerlerin sahnede yaratacağı sorunları canlı gösterir; durum çubuğundaki sahne
  kontrolü (✓ / ⚠ / ✖) tıklanınca hepsini listeler.
- **Plot:** eşit aralıklı streamline'lar ve oklar, stagnation point'ler (⊗, tıklayınca dividing streamline'lar),
  katmanlar: φ çizgileri, |V| ve Cp renk bantları, Solid bodies, Surface pressure (yüzeylerde Cp + panel:
  grafik, basınç integraliyle L′ / D′, Kutta–Joukowski / d'Alembert karşılaştırması). Fare modları Select /
  Move / Pan, tekerlekle zoom (Fit genişliğinin 10 000 katı yakına / uzağa kadar).
- **Animasyon:** Particles (iz bırakan tracer'lar) ve Pulses (streamline boyunca darbeler); Space duraklatır.
- **Dosyalar:** `.pflow` (düz JSON, tam hassasiyet: kaydet → aç = aynı liste ve aynı plot), Presets menüsü
  (ilk grup ödevin doğrulama durumları), undo / redo, kaydedilmemiş sahnenin otomatik kopyası ve çökmeden
  sonra geri getirme.
- **Export:** figür (PNG 1–4×, SVG, PDF), animasyon (GIF, MP4), veri (CSV).
- **Doğrulama:** Help → Run verification (ya da `--verify`): analitik formüller, ödevin 9 sahnesi, sayısal
  yöntemlerin doğruluğu; her check'in "nasıl hesaplandı" açıklaması.
- **GPU:** başlıktaki GPU kutusu plotu ve animasyonları ekran kartıyla çizer (değiştirmek programı birkaç
  saniyede yeniden başlatır, hiçbir şey kaybolmaz); yanındaki ok Graphics card panelini açar (FPS, frame rate
  sınırı, genişleyen slider sınırları). Laptop'ta NVIDIA kartı kendiliğinden istenir.
- **Kunduz** (isim geçici: `app_info.MASCOT_NAME`): cetvelde oturur; tıkla (ya da P) → soru–cevap, tanıtım turu,
  ilginç bilgi; plota sürükle → moduna göre camda / akışta / pulse'larda gezer. View → Beaver kapatır.
- **Bir hata olursa:** program kapanmaz, "Unexpected error" penceresi çıkar; her şey log'a yazılır
  (Help → Open log folder → `flowy.log`). Sorun bildirirken log dosyasını gönder.

## Komut satırı (pencere açmadan)

```
python main.py --verify [--out KLASÖR] [--no-figures]
python main.py sahne.pflow --figure sekil.png [--data veri.csv] [--view X0 X1 Y0 Y1] [--layers +bodies,-markers]
python main.py --help              # tüm seçenekler
```
Hata (dosya yok, bilinmeyen katman…) → çıkış kodu 2; `--verify`'da tutmayan bir check → 1.

## Ölçüm ve exe

- `python scripts/benchmark.py --full --out benchmarks/<isim>.json`: programın her şeyinin hızı (açılış, hesaplar,
  çizim, pan / zoom, animasyon, sınırlar, export), sonra bir de ekran kartıyla; ~8–10 dk, ayarlarına dokunmaz.
- `python scripts/random_test.py [--minutes 25] [--quick] [--seed N]`: kapsamlı rastgele test (ROADMAP 23) —
  rastgele / uç sahnelerde fizik check'leri ve pencerede rastgele işlemler; sonuç `random_test_results/<tarih-saat>/`
  (`summary.md`, hatalı sahneler `failures/` altında .pflow olarak; `--replay DOSYA` tek sahneyi tekrar dener).
- `python scripts/streamline_quality.py` (çizgi kalitesi), `python scripts/smoothness.py` (pan / zoom akıcılığı).
- **Exe (Windows, ROADMAP 24):** GitHub kendi Windows bilgisayarında derler (`.github/workflows/windows-build.yml`):
  bir sürüm etiketi (`v1.0.0`) pushlanınca zip **Releases** sayfasına konur; elle başlatmak: Actions → Windows
  build → Run workflow (zip o çalışmanın Artifacts'ında). Derleme exe'yi de dener: pencere olmadan doğrulama
  102 / 102, preset'ten figür, pencere açılıyor ve log'da hata yok. Kendi bilgisayarında:
  `pyinstaller --noconfirm packaging/build_exe.spec` → `dist/Flowy/` (Flowy.exe + `_internal\`; adı ve sürümü
  `app_info.py`'den, ikon logodan: `packaging/make_icon.py`).

## Klasör yapısı

| Klasör / dosya | İçerik |
|---|---|
| `main.py` | Başlatır: yükleme ekranı → donanım → çekirdekler → pencere; komut satırı seçenekleri |
| `app_info.py` | Programın adı, alt başlığı, sürümü, kunduzun adı — isim değiştirmek için tek yer |
| `physics/` | Fizik motoru (Qt'siz): `elements/` (her element ayrı dosya), `field.py` (superposition), `images.py` (method of images), `validation.py` (sahne kontrolü), `kernel.py` + `warmup.py` (Numba), `parallel.py` (çok çekirdek), `streamlines/` (Jobard–Lefer + RK4, önbellek), `stagnation.py` (w = 0, dividing streamline'lar), `origin.py` (akışkan nereden geliyor = cisim), `bodies.py`, `surface.py` (Cp, kuvvetler), `particles.py`, `verification.py` + `program_checks.py` + `diagnostics.py` (doğrulama) |
| `model/` | Sahne modeli + undo / redo (`scene_model.py`), `.pflow` formatı (`scene_file.py`), plot ayarları |
| `app/main_window.py`, `app/window/` | Ana pencere ve parçaları: düzen, menüler, dosyalar, export, durum çubuğu, GPU |
| `app/canvas/` | Plot: `canvas.py` + katmanlar (`*_layer.py`), fare (`interaction.py`), ekran kartı (`gl_*.py`) |
| `app/export/`, `app/cli/` | Figür / animasyon / CSV export; komut satırı ve doğrulama raporu |
| `app/chrome/`, `app/theme.py` | "Çizim kağıdı" görünümü; bütün renkler, fontlar, boyutlar |
| `app/panels.py`, `app/dialogs.py`, `app/surface_panel.py`, `app/gpu_panel.py` | Elements / Plot settings panelleri, element penceresi, Surface pressure ve Graphics card panelleri |
| `app/beaver/` | Kunduz: davranış, piksel art, konuşma balonu, replikler, soru–cevap, tur |
| `app/errors.py`, `app/recovery.py`, `app/restart.py` | Log + hata penceresi + çökme notu; otomatik kopya; yeniden başlatma |
| `app/hardware.py`, `app/gpu.py`, `app/splash.py`, `app/startup.py`, `app/paths.py` | Donanım, GPU kuralları, yükleme ekranı, uygulama ayarları, dosya / veri klasörü yolları |
| `app/user_guide*.py`, `app/conventions_dialog.py`, `app/verification_dialog.py` | Help menüsü: User guide, Sign conventions, Run verification |
| `presets/` | Hazır sahneler (klasör = menüdeki grup) |
| `assets/` | Fontlar, ikonlar |
| `packaging/`, `.github/workflows/` | Exe tarifi (`build_exe.spec`), ikon (`make_icon.py`), Releases notu; GitHub'ın Windows derlemesi |
| `scripts/`, `benchmarks/` | Ölçüm scriptleri; son tam ölçüm (`windows_full_nvidia.json`) |
| `tests/` | Otomatik testler (`pytest`) |
| `CLAUDE.md`, `ROADMAP.md` | AI asistan için devir notu; yapılanlar ve sıradaki işler |

**Yeni bir plot katmanı:** `app/canvas/layer.py`'deki `PlotLayer`'dan bir sınıf, `PlotCanvas.__init__`'te bir
`add_layer(...)` satırı, gerekiyorsa `canvas.LAYERS`'a bir anahtar. **Yeni bir plot ayarı:** `model/plot_settings.py`'de
bir alan, slider'ı varsa `app/canvas/settings.py` → `SLIDERS`'a bir satır, `PlotCanvas.set_<ad>(değer)`.

## Notasyon (ders notlarıyla aynı)

- F(z) = φ + iψ (complex potential), w = dF/dz = u − iv (complex velocity)
- Source/sink: F = (m/2π) log(z − z₀), m > 0 source
- Vortex: F = −i(Γ/2π) log(z − z₀), **Γ > 0 counter-clockwise** (dersteki dönen silindir clockwise Γ_cw = −Γ
  ile yazılır: L′ = ρ V∞ Γ_cw; Help → Sign conventions)
- Doublet: F = μ e^{iδ}/(z − z₀); uniform + doublet (δ = α) → cylinder, a = √(μ/V∞)
- Cp = 1 − (V/V∞)²
- Symmetry wall: image'lar plane theorem'den: source → aynı m, vortex → −Γ, doublet → δ* = 2θ_w − δ; uniform
  flow duvara paralel olmalı. Kanal (iki paralel duvar): image satırları kapalı formda, (π/P) cot(π(z − z₀)/P);
  karşısına dik 1 duvar → satırların aynası, 2 duvar (dikdörtgen) → satırlar kanal boyunca 2L arayla tekrar
  (birkaç kopya yeter, e^(−πd/H) ile sönüyor). Kapalı kutuda source'ların toplamı Σm = 0 olmalı
- Sector flow: ζ = (z − z₀)e^{−iθ₁}, F = Vζⁿ, n = π/β; akışkan sadece wedge'in içi. Wedge kenarları diğer
  elementler için duvardır; β = 180°/k ise source / vortex / doublet köşe image'larıyla tam eklenir, diğer
  durumlar hata verir (ayrıntı: User guide → Adding elements)

## Fonts

The program ships IBM Plex Mono, Barlow and Barlow Condensed (`assets/fonts`), all under the
SIL Open Font License 1.1 (license text next to each font).
