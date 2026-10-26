# Potential Flow Lab — Roadmap

Bu dosya projenin kalan işlerini ve sırasını tutar. Her adım bittikçe işaretlenir.
(✅ bitti · ▶ sıradaki · ☐ planlı)

## Bitenler
- ✅ Faz 0 — Kurulum, GitHub, arayüz prototipi
- ✅ Faz 1a — Uniform, source/sink, vortex, doublet, superposition, testler
- ✅ Faz 1b — Eşit aralıklı streamline motoru (Jobard–Lefer, RK4)
- ✅ Faz 1c — Symmetry wall (method of images, köşe, kanal)
- ✅ Faz 1d — Sector (wedge) flow ve diğer elementlerle etkileşim politikası
- ✅ Faz 2a — Sahne modeli, ekle / düzenle / sil / çoğalt / gizle, undo / redo, hatalı girdi uyarıları

## Sıra
1. ✅ **Paket A — Hızlı düzeltmeler**
   - [8] Seçili element mavi halka yerine kendi renginde parlasın (duvar dahil)
   - [3] Streamline okları küçülsün
   - Aynı noktadaki doublet + vortex: ⚠ uyarı yerine ℹ bilgi notu
   - Plot'ta sembole / duvara / sector kenarına tıklayarak seçme, üst üste binenlerde tekrar tıklayınca
     sıradaki; boş yere, başka bir yere tıklayınca ya da Esc ile seçim kalkar; çift tık → düzenle
2. ✅ **Paket B — Streamline kalitesi**
   - [1] Çizgiler eşit aralıklı: ilk çizgiler akışın görünüme girdiği kenardan tam d aralıkla, sonra her
     çizginin iki yanına d mesafede yeni tohum (Jobard–Lefer); uniform flow'da aralık sapması %20 → %0
   - [1] Oklar plot'a eşit dağılır (sabit hexagonal lattice, satırlar yarım aralık kaymalı, pan'de yerinde durur);
     ayar "Arrow density"
   - [2] Kesilen çizgi uçları 4 adımda soluklaşarak biter (tapering); çok kısa parçalar çizilmez
   - [2] Duvarlar / wedge kenarları streamline sayılır: hiçbir çizgi duvarın üstünden geçmez, duvar yanındaki
     çizgi de d mesafede
   - Durma (saddle) noktasında çizgi köşe yapıp yön değiştirmez, orada biter
   - Hesap arka planda (arayüz donmaz; yeni istek eskisini iptal eder, eski sonuç atılır)
   - Ölçüm: `python scripts/streamline_quality.py`
   - Not: kaynaktan duvardaki durma noktasına inen dividing streamline gibi özel çizgiler Faz 4'teki
     "dividing streamline" katmanında ayrıca çizilecek (`trace_streamlines(seeds=...)` hazır)
3. ☐ **Faz 2b — File menüsü**: New / Open / Save / Save as (JSON, sürüm numaralı), son açılanlar,
   presetler dosya olarak (hocanın verification case 5'i)
4. ☐ **Paket C — Sıcak, tatlı tema** [6]: 2–3 renk seçeneği gösterilip seçilecek (açık + koyu)
5. ☐ **Paket D — Panel sistemi** [4]: yumuşak animasyonlu yerleşim, sadece izinli yerlere oturma,
   ayrı pencere olarak yüzebilme, her bölüm (View range, Streamlines, Layers, …) ayrı panel,
   başlığa sağ tık → görünecek panelleri tikle, View → Panels, Reset layout, yerleşimi hatırlama
6. ☐ **Faz 2c — Plot'ta fareyle seçme ve sürükleme** (undo'da tek adım)
7. ☐ **Faz 3 — Rapor malzemesi**: doğrulama figürleri ve tabloları, user guide taslağı
8. ☐ **Faz 4 — Ekstralar**: animasyonlu parçacıklar (60 fps hedefi, ayarları ileride değiştirilebilir) [5],
   dividing streamline / cisim, φ, |V|, Cp katmanları, PNG / PDF / CSV export,
   isteğe bağlı OpenGL (ekran kartı) çizim, kunduzun akışta süzülmesi [7b]
9. ☐ **Paket E — Performans**: profiling, Numba ile derlenmiş streamline integrasyonu, kaba → ince çizim,
   önbellek, zayıf bilgisayarda test (hesap işlemcide, çizim gerekirse ekran kartında)
10. ☐ **Faz 5 — Paketleme**: Python gerektirmeyen Windows 10/11 exe (zip içinde klasör), GitHub Releases,
    isteğe bağlı kurulum dosyası (Inno Setup), macOS .app (GitHub Actions)
11. ☐ **Faz 6 — Kunduz rehber ve cilalama** [7a]: ilk açılışta atlanabilir tanıtım turu, Help yanındaki yeri,
    açma / kapama ayarı, demo provası

(Köşeli parantezdeki numaralar 26 Ekim'deki istek listesindeki madde numaralarıdır.)

Bir değişiklik beğenilmezse: her paket ayrı commit → GitHub Desktop → History → commit'e sağ tık →
"Revert changes in commit".
