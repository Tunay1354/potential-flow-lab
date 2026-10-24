# Potential Flow Lab

Interactive 2D potential-flow simulator (Aerodynamics semester project, IZTECH Mechanical Engineering).

**Durum:** Faz 1c — fizik çekirdeği (uniform flow, source/sink, vortex, doublet), streamline motoru ve
symmetry wall (method of images) hazır. Element ekleme/düzenleme butonları Faz 2'de bağlanacak;
o zamana kadar sahneler **Presets** menüsünden yüklenebilir.

Şu an çalışanlar: Presets menüsü (duvarlı örnekler dahil), zoom (mouse tekerleği) / pan (sürükleme),
Fit view, Elements listesindeki tik kutuları (elementi geçici olarak kapatma), Plot settings → View range,
Density, Line width, Direction arrows, Arrows per line, alttaki probe (u, v, |V|, Cp), sahne kontrolü
(status bar'da ✓ / ⚠ / ✖, ayrıntı için üzerine gel), View → Theme.

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
| `physics/` | Fizik motoru — GUI'den bağımsız, sadece NumPy |
| `physics/base.py` | Tüm elementlerin ortak temel sınıfı (`FlowElement`) |
| `physics/elements/` | Her element ayrı dosya: `uniform.py`, `source.py`, `vortex.py`, `doublet.py`, `wall.py` |
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
