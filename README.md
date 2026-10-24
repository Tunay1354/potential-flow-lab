# Potential Flow Lab

Interactive 2D potential-flow simulator (Aerodynamics semester project, IZTECH Mechanical Engineering).

**Durum:** Faz 2a — fizik çekirdeği tamam; program artık tamamen kullanılabilir: elementler toolbar'dan
eklenir, listeden / Elements menüsünden düzenlenir, gizlenir, çoğaltılır, silinir ve her değişiklik geri
alınabilir (Ctrl+Z / Ctrl+Y). Dosyaya kaydet / aç Faz 2b'de gelecek.

## Kullanım (kısa)

| Ne | Nasıl |
|---|---|
| Element ekle | Soldaki toolbar ya da **Elements → Add** → değerleri gir → **Apply** |
| Düzenle | Listede çift tıkla, Enter, **Edit…** butonu ya da **Elements → (element) → Edit…** |
| Geçici gizle | Listede elementin tik kutusu |
| Çoğalt | **Duplicate** butonu / Ctrl+D (kopya (0.5, 0.5) kaydırılır) |
| Sil | **Delete** butonu / listede veya plot'ta Delete tuşu |
| Geri al / yinele | **Edit → Undo / Redo**, Ctrl+Z / Ctrl+Y |
| Hazır sahne | **Presets** menüsü (bu da geri alınabilir) |
| Hepsini sil | **File → Clear all** veya **Elements → Delete all elements** (geri alınabilir) |

Dialog, girdiğin değerin sahnede yaratacağı sorunları canlı gösterir (örn. "duvarın arkasında").
Hata varsa buton **Apply anyway** olur; uygularsan plot'un üstünde kırmızı uyarı şeridi çıkar ve
status bar'da ✖ görünür (ayrıntı için üzerine gel). Hatalar listedeki numarayla gösterilir: `[2] ...`.

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
`requirements.txt` değiştiyse `pip install -r requirements.txt` komutunu tekrar çalıştır.

## Klasör yapısı

| Klasör / dosya | İçerik |
|---|---|
| `main.py` | Programı başlatır |
| `app/` | Arayüz. Renkler/boyutlar/marker'lar: `app/theme.py`, başlangıç sahnesi ve presetler: `app/scene.py` |
| `app/dialogs.py` | Parametre penceresi (alanlar `app/element_specs.py`'den otomatik; işaretli değerler için Source/Sink, Counter-clockwise/Clockwise seçimi) |
| `app/geometry.py` | Duvarların çizim geometrisi (köşelerde sadece akışkana bakan kısım çizilir) |
| `model/` | Sahne modeli: element listesi, komutlar, undo/redo, değişiklik önizlemesi (Qt'siz) |
| `physics/` | Fizik motoru — GUI'den bağımsız, sadece NumPy |
| `physics/base.py` | Tüm elementlerin ortak temel sınıfı (`FlowElement`) |
| `physics/elements/` | Her element ayrı dosya: `uniform.py`, `source.py`, `vortex.py`, `doublet.py`, `sector.py`, `wall.py` |
| `physics/images.py` | Method of images: duvarlarda ardışık yansıtma, π/k köşeler, kanal (kapalı form) |
| `physics/validation.py` | Sahne kontrolü: duvar arkasında/üstünde element, paralel olmayan uniform flow ... |
| `physics/registry.py` | Hangi element tipleri var (yeni element otomatik eklenir) |
| `physics/field.py` | Superposition (w = Σ wₖ), grid hesabı, Cp, singularity masking, fluid region |
| `physics/streamlines.py` | Eşit aralıklı streamline'lar (Jobard–Lefer, RK4) ve ok yerleri |
| `physics/diagnostics.py` | Flux, circulation, yüzey kuvvetleri (L′, D′) ölçümleri |
| `tests/` | Otomatik doğrulama testleri (`pytest`) |
| `scripts/verify_physics.py` | Rapor için doğrulama tablosu |

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
