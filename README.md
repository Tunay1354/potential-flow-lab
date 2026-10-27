# Potential Flow Lab

Interactive 2D potential-flow simulator (Aerodynamics semester project, IZTECH Mechanical Engineering).

**Durum:** Paket F — fizik çekirdeği tamam; elementler toolbar'dan eklenir, listeden / Elements menüsünden
düzenlenir, gizlenir, çoğaltılır, silinir, her değişiklik geri alınabilir (Ctrl+Z / Ctrl+Y) ve sahneler
dosyaya kaydedilip açılabilir. Sıradaki işler: `ROADMAP.md`.

## Kullanım (kısa)

| Ne | Nasıl |
|---|---|
| Element ekle | Soldaki toolbar ya da **Elements → Add** → değerleri gir → **Apply** |
| Düzenle | Listede çift tıkla, Enter, **Edit…** butonu ya da **Elements → (element) → Edit…** |
| Stagnation point | Plot'ta ⊗ sembolü. Tıkla → parlar, içinden geçen dividing streamline'lar (koyu kalın çizgiler) ve x, y kutusu görünür; boş yere tıkla / Esc → kaybolur. Hepsini birden görmek: **Plot settings → Layers → All dividing streamlines** |
| Seç | Listede ya da plot'ta sembole / duvara tıkla (üst üste binenlerde tekrar tıkla); boş yere tıkla veya Esc → seçim kalkar; sembole çift tık → düzenle |
| Geçici gizle | Listede elementin tik kutusu |
| Çoğalt | **Duplicate** butonu / Ctrl+D (kopya (0.5, 0.5) kaydırılır) |
| Sil | **Delete** butonu / listede veya plot'ta Delete tuşu |
| Geri al / yinele | **Edit → Undo / Redo**, Ctrl+Z / Ctrl+Y |
| Hazır sahne | **Presets** menüsü (bu da geri alınabilir); ilk grup hocanın doğrulama durumları |
| Kaydet / aç | **File → Save** (Ctrl+S), **Save as…** (Ctrl+Shift+S), **Open…** (Ctrl+O), **Open recent**; `.pflow` dosyasını pencereye sürükleyip bırakmak da açar |
| Yeni sahne | **File → New** (Ctrl+N) |
| Hepsini sil | **File → Clear all** veya **Elements → Delete all elements** (geri alınabilir) |

Dialog, girdiğin değerin sahnede yaratacağı sorunları canlı gösterir (örn. "duvarın arkasında").
Hata varsa buton **Apply anyway** olur; uygularsan plot'un üstünde kırmızı uyarı şeridi çıkar ve
status bar'da ✖ görünür (ayrıntı için üzerine gel). Hatalar listedeki numarayla gösterilir: `[2] ...`.

### Sahne dosyaları (.pflow)

- İçinde elementler, başlık, view aralığı ve streamline ayarları (density, line width, oklar) var; sayılar tam
  hassasiyetle saklanır, yani kaydedip açınca liste ve plot birebir aynı gelir (hocanın 5. doğrulama durumu).
- Düz JSON'dur, her element bir satır; Not Defteri ile açılıp okunabilir.
- Kaydedilmemiş değişiklik varsa başlıkta `*` görünür; New / Open / kapatma öncesi program sorar.
- Bozuk ya da eksik dosyada program çökmez, sebebini söyler; küçük sorunlarda (eksik bir değer vb.) dosyayı
  açar ve neyi düzelttiğini listeler.
- Kendi preset'ini eklemek için: sahneyi `presets/` altındaki bir klasöre kaydet
  (**Presets → Show presets folder**), programı yeniden aç.
- Komut satırından: `python main.py dosya.pflow`

## Kurulum (Windows, VS Code) — bir kez

1. Repoyu GitHub Desktop ile clone'la, sonra **Repository → Open in Visual Studio Code**.
2. **Terminal → New Terminal** ve sırayla:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   - `python` bulunamazsa: python.org'dan Python 3.12 kur, ilk ekranda **"Add python.exe to PATH"** işaretle.
   - PowerShell "running scripts is disabled" derse bir kez:
     `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (soruya `Y`).

## Her seferinde

```
.venv\Scripts\activate          # satırın başında (.venv) görünmeli
python main.py                  # arayüzü aç
pytest                          # fizik testlerini çalıştır
python scripts/verify_physics.py   # analitik vs. sayısal doğrulama tablosu
```
Güncelleme geldiğinde: GitHub Desktop'ta **Fetch origin → Pull origin**.
`requirements.txt` değiştiyse `pip install -r requirements.txt` komutunu tekrar çalıştır
(Paket E1'den sonra bir kez gerekli: hızlı streamline motoru için **numba** eklendi).

İlk açılışta streamline motoru bir kez derlenir (birkaç saniye, durum çubuğunda yazar); sonraki
açılışlarda hazır gelir.

Ölçüm scriptleri: `python scripts/streamline_quality.py` (çizgi kalitesi),
`python scripts/smoothness.py` (pan / zoom sırasında kare aralıkları, arayüz akıcılığı).

## Klasör yapısı

| Klasör / dosya | İçerik |
|---|---|
| `main.py` | Programı başlatır (`python main.py sahne.pflow` dosyayı da açar) |
| `app_info.py` | Program adı ve sürümü |
| `presets/` | Hazır sahneler (`.pflow` dosyaları, klasör = menüdeki grup) |
| `app/main_window.py` | Ana pencere: parçaları birleştirir, sinyalleri bağlar, element komutları (ekle / düzenle / taşı / sil, undo / redo) |
| `app/window/` | Ana pencerenin parçaları: `layout.py` (yan paneller, palette sağ/sol, düzeni hatırlama), `menus.py` (palette, menüler, kısayollar), `files.py` (New / Open / Save, preset'ler), `exporting.py` (figür ve CSV export), `status.py` (durum çubuğu, probe, sahne kontrolü, başlıklar) |
| `app/canvas/` | Plot kartı. `canvas.py` ortak durumu tutar (elementler, ayarlar, katman anahtarları, seçim) ve her olayı katmanlara iletir. Katmanlar: `streamline_layer.py` (arka planda hesap), `stagnation_layer.py`, `field_layer.py` (φ, \|V\|, Cp; `contours.py`, `legend.py`), `element_layer.py` (semboller, duvarlar, seçme). `interaction.py`: fare modları, sürükleme, palette'ten bırakma. `settings.py`: sahneyle kaydedilen plot ayarları |
| `app/export/` | `figure.py` (PNG / SVG / PDF), `data.py` (CSV, Qt'siz), `dialogs.py` |
| `app/chrome/` | Pencerenin "çizim kağıdı" görünümü: `style.py` (font, renk), `header.py` (logo, tahta şerit, cetvel + menüler), `cards.py` (panel kartları, title block), `palette.py` (element paleti) |
| `app/panels.py`, `app/dialogs.py` | Elements / Plot settings panelleri; parametre penceresi (alanlar `app/element_specs.py`'den otomatik) |
| `app/theme.py` | Renkler (açık / koyu), fontlar, boyutlar, marker'lar |
| `app/geometry.py` | Duvarların çizim geometrisi (köşelerde sadece akışkana bakan kısım çizilir) |
| `app/scene.py`, `app/recent_files.py`, `app/shortcuts.py` | Başlangıç sahnesi ve preset listesi; son açılanlar; değiştirilebilir kısayollar |
| `model/` | Sahne modeli: element listesi, komutlar, undo/redo, değişiklik önizlemesi (Qt'siz) |
| `model/scene_file.py` | Dosya formatı (.pflow, sürüm numaralı JSON), okuma / yazma, anlaşılır hata mesajları |
| `physics/` | Fizik motoru — GUI'den bağımsız, sadece NumPy |
| `physics/base.py` | Tüm elementlerin ortak temel sınıfı (`FlowElement`) |
| `physics/elements/` | Her element ayrı dosya: `uniform.py`, `source.py`, `vortex.py`, `doublet.py`, `sector.py`, `wall.py` |
| `physics/images.py` | Method of images: duvarlarda ardışık yansıtma, π/k köşeler, kanal (kapalı form) |
| `physics/validation.py` | Sahne kontrolü: duvar arkasında/üstünde element, paralel olmayan uniform flow ... |
| `physics/registry.py` | Hangi element tipleri var (yeni element otomatik eklenir) |
| `physics/field.py` | Superposition (w = Σ wₖ), grid hesabı, Cp, singularity masking, fluid region |
| `physics/streamlines.py` | Eşit aralıklı streamline'lar (Jobard–Lefer, RK4), soluklaşan uçlar, ok yerleri; pan'de çizgileri yerinde tutan önbellek (`StreamlineCache`) |
| `physics/stagnation.py` | Stagnation point'ler (w = 0, Newton) ve dividing streamline'lar; cisim içi / yüzeyi ayrımı |
| `physics/kernel.py` | Numba ile derlenmiş hız alanı ve integrator (aynı matematik, ~10× hızlı, arayüzü bekletmez) |
| `physics/diagnostics.py` | Flux, circulation, yüzey kuvvetleri (L′, D′) ölçümleri |
| `tests/` | Otomatik doğrulama testleri (`pytest`) |
| `scripts/verify_physics.py` | Rapor için doğrulama tablosu |
| `scripts/streamline_quality.py` | Streamline resminin kalite ölçümü (aralık düzgünlüğü, kesik uçlar, süre) |

**Yeni bir plot katmanı eklemek** (ör. animasyon): `app/canvas/layer.py`'deki `PlotLayer`'dan bir sınıf
(sadece gereken olaylar: tema, sahne, görünüm, sürükleme…), `PlotCanvas.__init__`'te bir `add_layer(...)`
satırı ve gerekiyorsa `LAYERS` listesine bir anahtar (Plot settings ve View menüsünde kendiliğinden çıkar).
**Yeni bir plot ayarı**: `app/canvas/settings.py`'de bir alan (+ `model/scene_file.py` → `SETTINGS`);
sahne dosyasına kaydedilir ve açılır.

## Notasyon (ders notlarıyla aynı)

- F(z) = φ + iψ (complex potential), w = dF/dz = u − iv (complex velocity)
- Source/sink: F = (m/2π) log(z − z₀), m > 0 source
- Vortex: F = −i(Γ/2π) log(z − z₀), **Γ > 0 counter-clockwise**
- Doublet: F = μ e^{iδ}/(z − z₀), μ = mε/π; uniform + doublet → cylinder, a = √(μ/V∞)
- Cp = 1 − (V/V∞)²
- Symmetry wall: z* = z_w + e^{2iθ_w} conj(z − z_w); image kuralları plane theorem'den
  (F_total = F(z) + conj F(z*)): source → aynı m, vortex → −Γ, doublet → δ* = 2θ_w − δ,
  uniform flow image'lanmaz (duvara paralel olmalı)
- Sector flow: ζ = (z − z₀)e^{−iθ₁}, F = Vζⁿ, n = π/β, β = θ₂ − θ₁ (saat yönünün tersine, (0°, 360°]);
  V > 0: akış θ₂ duvarından girer, θ₁ duvarından çıkar. Akışkan bölgesi sadece wedge'in içi.
  Branch cut wedge'in dışında (β = 360°'de plakanın kendisi).
- Sector flow + diğer elementler (açıkça tanımlanmış politika):
  wedge kenarları diğer elementler için duvardır; β = 180°/k ise source/vortex/doublet köşe image'larıyla
  tam olarak eklenir (90°: 3 image); diğer β'larda, β > 180°'de, birden fazla sector'da, sector + symmetry
  wall'da ve wedge dışındaki/kenarındaki elementlerde hata verilir. Uniform flow sadece β = 180° ve duvara
  paralelse kabul edilir. Sector flow'un kendisi image'lanmaz (zaten kendi duvarlarını sağlar).

## Fonts

The program ships IBM Plex Mono, Barlow and Barlow Condensed (`assets/fonts`), all under the
SIL Open Font License 1.1 (license text next to each font).
