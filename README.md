# Potential Flow Lab

Interactive 2D potential-flow simulator (Aerodynamics semester project, IZTECH Mechanical Engineering).

**Durum:** ROADMAP 1–19 tamam (fizik çekirdeği, streamline'lar, duvarlar, sector flow, File / Elements menüleri,
undo / redo, stagnation point'ler, alan katmanları, animasyon, export, Solid bodies, Surface pressure,
komut satırı + `--verify` 102 / 102, hata yakalama, otomatik kayıt, kunduz). Sıradaki işler: `ROADMAP.md`.

## Kullanım (kısa)

| Ne | Nasıl |
|---|---|
| Element ekle | Soldaki toolbar ya da **Elements → Add** → değerleri gir → **Apply** |
| Düzenle | Listede çift tıkla, Enter, **Edit…** butonu ya da **Elements → (element) → Edit…** |
| Stagnation point | Plot'ta ⊗ sembolü. Tıkla → parlar, içinden geçen dividing streamline'lar (koyu kalın çizgiler) ve x, y kutusu görünür; boş yere tıkla / Esc → kaybolur. Hepsini birden görmek: **Plot settings → Layers → All dividing streamlines** |
| Seç | Listede ya da plot'ta sembole / duvara tıkla (üst üste binenlerde tekrar tıkla); boş yere tıkla veya Esc → seçim kalkar; sembole çift tık → düzenle |
| Geçici gizle | Listede elementin tik kutusu |
| Parametreleri gör | Listede her elementin tüm parametreleri yazar; panele sığmayanlar alt satıra geçer (panel genişleyince yine tek satır) |
| Çoğalt | **Duplicate** butonu / Ctrl+D (kopya (0.5, 0.5) kaydırılır) |
| Sil | **Delete** butonu / listede veya plot'ta Delete tuşu |
| Geri al / yinele | **Edit → Undo / Redo**, Ctrl+Z / Ctrl+Y |
| Yüzey basıncı | **Layers → Surface pressure (Cp on surfaces)**: cisim yüzeyleri ve duvarlar Cp'ye göre renklenir, solda **Surface pressure** paneli açılır: Cp grafiği (θ / s / x boyunca; silindirde analitik eğri kesikli), kapalı cisimde basınç integraliyle lift / drag ve Kutta–Joukowski / d'Alembert karşılaştırması, ρ ile N/m, **Export CSV…**. Grafiğin üstünde gezinince plot'ta o nokta halkayla gösterilir. Panel: **View → Panels → Surface pressure** |
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
   pip install -r requirements-dev.txt
   ```
   (`requirements-dev.txt` = programın paketleri + `pytest` + exe için `pyinstaller`; sadece programı
   çalıştırmak için `requirements.txt` yeter.)
   - `python` bulunamazsa: python.org'dan Python 3.12 kur, ilk ekranda **"Add python.exe to PATH"** işaretle.
   - PowerShell "running scripts is disabled" derse bir kez:
     `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (soruya `Y`).

## Her seferinde

```
.venv\Scripts\activate          # satırın başında (.venv) görünmeli
python main.py                  # arayüzü aç
pytest                          # fizik testlerini çalıştır
python scripts/verify_physics.py   # analitik vs. sayısal doğrulama tablosu
python main.py --verify         # tüm doğrulama raporu → verification/ (Markdown + CSV + figürler)
```
Güncelleme geldiğinde: GitHub Desktop'ta **Fetch origin → Pull origin**.
`requirements.txt` / `requirements-dev.txt` değiştiyse `pip install -r requirements-dev.txt` komutunu tekrar
çalıştır.

İlk açılışta streamline motoru bir kez derlenir (birkaç saniye, durum çubuğunda yazar); animasyon ve
Solid bodies çekirdekleri hemen ardından arka planda hazırlanır. Sonraki açılışlarda hepsi hazır gelir.

### Kunduz (Psi — isim geçici)

Cetvelde Help'in sağında duran piksel kunduz. Mouse ile tutup plota bırakılır; ne yapacağı görünüm moduna bağlı:
- **Static**: plotun önünde cam var — cama yapışır, tıklatır, espri yapar, rafına döner (ekrana sabit: zoom /
  pan arkadaki plotu oynatır)
- **Particles**: bırakıldığı yerden akışla gider (particle'larla aynı hız ayarı, Space ile durur); görünümden
  çıkınca cetvelde sağdan yürüyerek döner. Sadece vortex: döner, başı döner, zıplar; vortex + sink: dönerek
  küçülür, yutulur; stagnation point'te durur; solid body'ye / duvarın arkasına bırakılamaz
- **Pulses**: en yakın streamline'a basar; her pulse çarpınca düşer ve line boyunca itilir; kenarda "BONK",
  söylenir, döner

Çok yavaş akışta sıkılıp eve gider, çok yavaş pulse'lardan koşarak kaçar; çok hızlı akışta da her satır okunacak
kadar ekranda kalır. Particles / Pulses'ta plota (veriye) bağlıdır: zoom / pan ile birlikte hareket eder, görünümden çıkarsa eve döner.
**Tıklama ve sürükleme ayrı:** kunduza tıklayınca (fare kıpırdamadan) menüsü açılır — Questions & answers,
Show me around (tour), Tell me a fun fact; basılı tutup sürükleyince eline alırsın. **P** tuşu (ya da Help → Beaver →
Questions & answers) her yerden soru–cevap listesini açar: 1–9, 0, oklar + Enter ya da tıklama; Esc kapatır.

**Tanıtım turu:** ilk açılışta kunduz "First time here? Want a quick tour?" diye sorar (bir kez). Evet → boş bir
sayfadan başlayıp pencerenin parçalarını tek tek gösterir (kırmızı çerçeve, gerisi hafif karartılmış) ve asıl
işleri yaptırır: uniform flow ekle, doublet ekle, elementi düzenle, Move'a bas ve doublet'i taşı, Density
slider'ını oynat, Particles'ı aç; sonra Export, File, Presets, Help, kendisi ve P tuşu (18 adım).
- Tur sürerken pencere kilitli: tıklama / çift tıklama / tekerlek / sağ tık sadece o adımın istediği yere gider
  (plot adımlarında zoom / pan; "Your turn!" adımlarında sadece gösterilen şey). Fare her yerde gezer (hover,
  tooltip'ler çalışır).
- Okuma adımları Enter / Space / balona veya kunduza tıklama / **Next ›** butonu ile geçer. "Your turn!" adımları
  istenen yapılınca kendiliğinden geçer; Enter / Space / **Skip** atlar. Esc veya **End tour** turu bitirir. Diğer
  tuşlar tur boyunca çalışmaz (Move adımında M hariç).
- Palette'ten sürüklerken plot aydınlanır; element penceresi açılınca kunduz yanına geçip ne yapılacağını söyler
  (Apply → devam, Cancel → adıma geri). Konuşma balonu gösterdiği yerin üstüne binmez. Plot settings adımlarında
  panel açılır ve slider görünür yere kaydırılır (slider'ın bölümü gizliyse o adım atlanır).
- Bitince boş bir plot bırakır (Select modu, Density eski değerinde). Tekrar: Help → Beaver → Show me
around ya da kunduza tıkla → 2. Sonraki açılışlarda sormaz (arada "Welcome back!").

**İlk açılışı tekrar denemek için:** `python main.py --first-run` (o seferlik ilk açılış gibi davranır) ya da
Help → Beaver → Next start as a first-time user (bir sonraki açılış ilk açılış olur).

Konuşmalar İngilizce, harf harf yazılır. Konuşma balonu "çizim kartı" görünümünde: kalın mürekkep çerçeve, basamaklı
köşeler, gölge; üstte adı (PSI, isim geçici) ve sağda etiket (TOUR 3/18, MENU, QUESTIONS …); yazı IBM Plex Mono;
sağ altta düğmeler (asıl düğme başlıktaki ahşap renginde: Next ›, Yes, show me around ›, More questions ›). Kunduz
export edilen figür ve animasyonlarda görünmez; tekerlek üstündeyken de plotu zoom'lar. **View → Beaver** ile kapatılır.

### Bir hata olursa

Yakalanmamış bir hata programı kapatmaz: "Unexpected error" penceresi çıkar (ayrıntılar, Copy details, Open log
folder), program açık kalır, sahne kaybolmaz. Her hata traceback'iyle log dosyasına yazılır:
**Help → Open log folder** → `potential-flow-lab.log` (en çok 3 × 1 MB). Program tamamen çökerse (derlenmiş
kodda) yığın `crash.txt`'e yazılır ve bir sonraki açılışta log'a aktarılır. Sorun bildirirken log dosyasını gönder.

Kaydedilmemiş değişiklik varken sahnenin bir kopyası son değişiklikten ~3 s sonra programın veri klasörüne
(`recovery/`) yazılır; kaydedince, değişiklikler geri alınınca ya da program normal kapanınca silinir. Program
normal kapanmazsa (çökme, elektrik, görev yöneticisi) bir sonraki açılışta "Restore unsaved scene" sorulur:
Restore (kaydedilmemiş sahne olarak açılır, Undo önceki sahneye döner) / Discard / Not now.

### Komut satırı (pencere açmadan)

```
python main.py --verify [--out KLASÖR] [--no-figures]
python main.py sahne.pflow --figure sekil.png [--data veri.csv] [seçenekler]
python main.py --help           # tüm seçenekler
```
- `--verify`: üç bölümlük rapor — (1) analitik formüller (hız, flux, circulation, kuvvet, duvarlar, sector
  flow; round-off'a kadar), (2) ödevin 9 verification sahnesi: programın çizdiği / bulduğu şeyler teoriyle
  (streamline açıları, stagnation point konumu, yüzey r = a, Cp, basınç integralinden L′ ve D′ — Kutta–Joukowski
  ve d'Alembert), kaydet → tekrar aç (aynı elementler, aynı streamline'lar) ve sahnenin figürü, (3) sayısal
  yöntemlerin doğruluğu (çizgiler boyunca ψ, Newton ile durma noktası, izlenen yüzeylerin şekli, birkaç Γ için
  kaldırma). Her satırın kendi toleransı ve "nasıl hesaplandı" açıklaması var (Theory / Program / Tolerance);
  hepsi tutarsa çıkış kodu 0, tutmayan satırlar konsola da yazılır. Çıktı: `verification.html` (tarayıcıda:
  figürler, her check'in açıklaması tıklayınca açılır), `verification.md`, `verification.csv` (section, case,
  quantity, analytic, numerical, error, tolerance, ok, how), `figures/*.png`. Süre ≈ 15 s.
- Aynısı programın içinden: **Help → Run verification…** (arka planda çalışır; sonuç katlanmış bir ağaç —
  bölüm → durum → check; bir satır seçilince sağda formüller, programın yaptığı hesap, tolerans ve sayılar,
  sahne seçilince figürü; Open full report / Open folder / Save report to… / Run again)
- `--figure` (.png / .svg / .pdf) ve `--data` (CSV, File → Export data ile aynı tablolar): `--view X0 X1 Y0 Y1`,
  `--layers +bodies,+surface,-markers` (ya da işaretsiz liste: sadece bunlar), `--width / --height` (plot alanı,
  piksel), `--scale 1–4`, `--background white|paper|transparent`, `--dark`, `--vref V`, `--tables
  elements,stagnation,streamlines,field,surface`, `--grid N`, `--separator , ; tab`. Hata (dosya yok, bilinmeyen
  katman…) → çıkış kodu 2.

Exe (Faz 5): `pyinstaller packaging/potential_flow_lab.spec` → `dist/Potential Flow Lab/`.

Ölçüm scriptleri: `python scripts/streamline_quality.py` (çizgi kalitesi),
`python scripts/smoothness.py` (pan / zoom sırasında kare aralıkları, arayüz akıcılığı),
`python scripts/benchmark.py [--out sonuc.json] [--quick]` (programın her şeyinin hızı: açılış, hesaplar, çizim, pan /
zoom / sürükleme, tepki süreleri, animasyon, export, verification — ~6 dk; ayarlarına / dosyalarına dokunmaz).

## Klasör yapısı

| Klasör / dosya | İçerik |
|---|---|
| `CLAUDE.md` | Projeyi devralacak bir AI asistan için özet: proje, çalışma tercihleri, mimari, dersler, şu anki durum |
| `main.py` | Programı başlatır (`python main.py sahne.pflow` dosyayı da açar); `--verify`, `--figure`, `--data` ile komut satırı |
| `app/cli/` | Komut satırı: `__init__.py` (seçenekler), `headless.py` (ekranda görünmeyen plot, görünüme göre boyut), `report.py` (doğrulama raporu: HTML, Markdown, CSV, figürler; komut satırı ve Help menüsü ortak) |
| `app_info.py` | Program adı ve sürümü |
| `app/paths.py` | Programın dosyalarının yeri (kaynak klasör veya exe) |
| `packaging/` | Exe yapımı (PyInstaller spec) |
| `presets/` | Hazır sahneler (`.pflow` dosyaları, klasör = menüdeki grup) |
| `app/main_window.py` | Ana pencere: parçaları birleştirir, sinyalleri bağlar, element komutları (ekle / düzenle / taşı / sil, undo / redo) |
| `app/window/` | Ana pencerenin parçaları: `layout.py` (yan paneller, palette sağ/sol, düzeni hatırlama), `menus.py` (palette, menüler, kısayollar), `files.py` (New / Open / Save, preset'ler), `exporting.py` (figür ve CSV export), `status.py` (durum çubuğu, probe, sahne kontrolü, başlıklar) |
| `app/canvas/` | Plot kartı. `canvas.py` ortak durumu tutar (elementler, ayarlar, katman anahtarları, seçim) ve her olayı katmanlara iletir. Katmanlar: `streamline_layer.py` (arka planda hesap), `stagnation_layer.py`, `field_layer.py` (φ, \|V\|, Cp; `contours.py`, `legend.py`), `element_layer.py` (semboller, duvarlar, seçme), `animation_layer.py` + `particle_layer.py` + `pulse_layer.py` (animasyonlar: particle'lar, streamline üstünde darbeler), `body_layer.py` (cisimlerin içi dolu: Solid bodies), `surface_layer.py` (yüzeyler Cp renginde: Surface pressure). `interaction.py`: fare modları, sürükleme, palette'ten bırakma. `settings.py`: Plot settings slider'larının tablosu |
| `app/export/` | `figure.py` (PNG / SVG / PDF), `data.py` (CSV, Qt'siz), `dialogs.py` |
| `app/chrome/` | Pencerenin "çizim kağıdı" görünümü: `style.py` (font, renk), `header.py` (logo, tahta şerit, cetvel + menüler), `cards.py` (panel kartları, title block), `palette.py` (element paleti) |
| `app/panels.py`, `app/dialogs.py` | Elements / Plot settings panelleri; parametre penceresi (alanlar `app/element_specs.py`'den otomatik) |
| `app/surface_panel.py` | Surface pressure paneli: Cp grafiği, kuvvetler, CSV |
| `app/errors.py` | Beklenmeyen hatalar: log dosyası, hata penceresi (program açık kalır), çökme dosyası |
| `app/beaver/` | Kunduz: `art.py` (koddan çizilen piksel art, her poz / açı keskin), `bubble.py` (piksel konuşma balonu, seçenekli diyaloglar), `lines.py` (İngilizce metinler), `faq.py` (soru–cevap), `tour.py` (tanıtım turu adımları), `spotlight.py` (turdaki vurgu), `beaver.py` (davranış: raf, tıklama menüsü, sürükleme, cam, akış, pulse, eve dönüş, tuşlar) |
| `app/recovery.py` | Otomatik kopya ve çökme sonrası sahneyi geri getirme |
| `app/verification_dialog.py` | Help → Run verification…: raporu arka planda üretir, check ağacı ve "nasıl hesaplandı" paneli |
| `app/theme.py` | Renkler (açık / koyu), fontlar, boyutlar, marker'lar |
| `app/geometry.py` | Duvarların çizim geometrisi (köşelerde sadece akışkana bakan kısım çizilir) |
| `app/scene.py`, `app/recent_files.py`, `app/shortcuts.py` | Başlangıç sahnesi ve preset listesi; son açılanlar; değiştirilebilir kısayollar |
| `model/` | Sahne modeli: element listesi, komutlar, undo/redo, değişiklik önizlemesi (Qt'siz) |
| `model/scene_file.py` | Dosya formatı (.pflow, sürüm numaralı JSON), okuma / yazma, anlaşılır hata mesajları |
| `model/plot_settings.py` | Sahneyle kaydedilen plot ayarları (`PlotSettings`) |
| `physics/` | Fizik motoru — GUI'den bağımsız, sadece NumPy |
| `physics/base.py` | Tüm elementlerin ortak temel sınıfı (`FlowElement`) |
| `physics/elements/` | Her element ayrı dosya: `uniform.py`, `source.py`, `vortex.py`, `doublet.py`, `sector.py`, `wall.py` |
| `physics/images.py` | Method of images: duvarlarda ardışık yansıtma, π/k köşeler, kanal (kapalı form) |
| `physics/validation.py` | Sahne kontrolü: duvar arkasında/üstünde element, paralel olmayan uniform flow ... |
| `physics/registry.py` | Hangi element tipleri var (yeni element otomatik eklenir) |
| `physics/field.py` | Superposition (w = Σ wₖ), grid hesabı, Cp, singularity masking, fluid region |
| `physics/streamlines/` | Eşit aralıklı streamline'lar (Jobard–Lefer, RK4): `level.py` (bir aralık seviyesi), `cache.py` (pan'de çizgileri yerinde tutan önbellek), `seeds.py`, `rasters.py`, `arrows.py`, `drawing.py` (soluklaşan uçlar) |
| `physics/stagnation.py` | Stagnation point'ler (w = 0, Newton) ve dividing streamline'lar; akışkanın nereden geldiği (`trace_origin`: serbest akış / cisim / kapalı döngü) |
| `physics/bodies.py` | Cisimler: bölge resmi (`body_map`), yüzeyler saat yönünün tersine sıralı (`find_bodies`) |
| `physics/surface.py` | Yüzeyler (cisimler + ıslak duvarlar), üzerlerinde Cp, basınç integraliyle kuvvet (Kutta–Joukowski / d'Alembert karşılaştırması), silindirin analitik Cp'si |
| `physics/warmup.py` | Numba çekirdeklerini arka planda önceden derler / yükler |
| `physics/particles.py` | Animasyon fiziği: tracer particle'lar, streamline boyunca yolculuk süresi (pulse'lar) |
| `physics/kernel.py` | Numba ile derlenmiş hız alanı ve integrator (aynı matematik, ~10× hızlı, arayüzü bekletmez) |
| `physics/diagnostics.py` | Flux, circulation, yüzey kuvvetleri (L′, D′) ölçümleri |
| `physics/verification.py` | Analitik çözümlerle karşılaştırma tablosu (rapor, testler, `--verify`) |
| `physics/program_checks.py` | Programın sayısal sonuçlarının kontrolü: çizilen streamline'lar, durma noktası araması, izlenen yüzeyler, Cp, basınç integrali (`--verify`) |
| `tests/` | Otomatik doğrulama testleri (`pytest`) |
| `scripts/verify_physics.py` | Doğrulama tablosunu yazdırır (`physics/verification.py`) |
| `scripts/benchmark.py` | Her şeyin hızı tek çalıştırmada (açılış cold / warm, hesaplar, çizim, pan / zoom / sürükleme, tepki süresi, animasyon, export, verify); `--out` ile JSON |
| `benchmarks/` | Kaydedilmiş benchmark sonuçları (JSON): OpenGL vb. değişikliklerden önce / sonra karşılaştırmak için |
| `scripts/streamline_quality.py` | Streamline resminin kalite ölçümü (aralık düzgünlüğü, kesik uçlar, süre) |

**Yeni bir plot katmanı eklemek** (ör. animasyon): `app/canvas/layer.py`'deki `PlotLayer`'dan bir sınıf
(sadece gereken olaylar: tema, sahne, görünüm, sürükleme…), `PlotCanvas.__init__`'te bir `add_layer(...)`
satırı ve gerekiyorsa `LAYERS` listesine bir anahtar (Plot settings ve View menüsünde kendiliğinden çıkar).
**Yeni bir plot ayarı** (3 yer): `model/plot_settings.py`'de bir alan (sahne dosyasına kaydedilir ve açılır,
kontrolü kendiliğinden), slider'ı varsa `app/canvas/settings.py` → `SLIDERS`'a bir satır (bölüm, etiket, aralık;
panel kendiliğinden kurulur) ve `PlotCanvas.set_<ad>(değer)` (ayarı plota uygular).

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
