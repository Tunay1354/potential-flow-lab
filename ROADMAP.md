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
Teslim: yaklaşık 26 Kasım 2026 (rapor + user guide + canlı demo).

1. ✅ **Paket A — Hızlı düzeltmeler**: seçim kendi renginde parlıyor, küçük oklar, coincident uyarısı bilgi notu,
   plot'ta tıklayarak seçme, başka yere tıklayınca seçimin kalkması
2. ✅ **Paket B — Streamline kalitesi**
   - [1] Çizgiler eşit aralıklı: ilk çizgiler akışın görünüme girdiği kenardan tam d aralıkla, sonra her
     çizginin iki yanına d mesafede yeni tohum (Jobard–Lefer); uniform flow'da aralık sapması %20 → %0
   - [1] Oklar plot'a eşit dağılır (sabit hexagonal lattice, satırlar yarım aralık kaymalı); ayar "Arrow density"
   - [2] Kesilen çizgi uçları soluklaşarak biter; duvarlar streamline sayılır; saddle noktasında çizgi durur
   - Hesap arka planda (yeni istek eskisini iptal eder); ölçüm: `python scripts/streamline_quality.py`
3. ✅ **Faz 2b — File menüsü**: New / Open / Save / Save as (JSON, sürüm numaralı), son açılanlar,
   kaydedilmemiş değişiklik uyarısı, presetler dosya olarak (hocanın verification case'leri dahil;
   case 5 = kaydet → aç → aynı liste ve aynı plot)
4. ✅ **Paket E1 — Akıcılık**
   - Çizim ~12× hızlı: grid tek öğe, çizgiler segment modunda, oklar tek öğe; ekran dışı çizgiler çizilmez
   - Hesap Numba ile derlenmiş kernel'de (`physics/kernel.py`): bir sahne ~180 ms → ~40 ms, GIL'i bırakır
   - Pan'de çizgiler yerinde kalır (StreamlineCache): kenarda kesilen çizgiler devam ettirilir, sadece yeni
     alan tohumlanır; görünenin çevresi önceden hesaplanır (overscan), pan sırasında kenar hiç boş kalmaz
   - Zoom: çizgi aralığı 2'nin kuvvetleri, belirgin bir zoom'dan sonra değişir (hysteresis)
   - Ölçüm (`scripts/smoothness.py`, lifting cylinder pan): ~17 fps → ~60 fps (ortanca), boş kenar %0
   - Not: kaba seviyenin çizgilerini ince seviyede tutma (zoom'da yarı çizgiler yerinde) hazır ama kapalı
     (`COARSE_LEVELS`): kaynak gibi açılan akışlarda boşluk bırakıyor; uçları uzatarak ileride açılabilir
   - Not: geri kalan kare süresi Qt'nin CPU'da antialiased çizimi (~10 ms) → E2'de OpenGL denenecek
5. ✅ **Paket F — Stagnation point'ler + dividing streamline**
   - w(z) = 0 noktaları Newton yöntemiyle bulunur, plot'ta ⊗ sembolü; üzerine gelince koordinat ve türü
     (akışta / duvarda / köşe / cisim yüzeyinde) durum çubuğunda
   - Revize: dividing streamline'lar normalde gizli; ⊗'e tıklayınca o noktanın çizgileri, parlama ve
     x, y kutusu görünür, boş yere tıklayınca / Esc ile kaybolur ("All dividing streamlines" katmanı ayrıca var)
   - Duvar arkasındaki (image kaynaklı) sıfırlar ve cismin içindeki fiziksel olmayan kök gösterilmez
     (ör. Γ > 4πV∞a'da silindir içindeki ikinci kök); sector köşesi (n > 1) dahil
   - Dividing streamline'lar durma noktalarından çizilir (silindir yüzeyi, Rankine gövdeleri, iki vortex
     arasındaki lemniskat …); normal streamline'lar bunlardan tohumlanır
   - Katmanlar çalışıyor: Streamlines, Dividing streamlines, Stagnation points, Element markers, Walls
     (Plot settings → Layers ve View → Layers aynı anahtarlar)
   - Analitik karşılaştırma testleri: silindir, lifting cylinder (sin θ = Γ/4πV∞a, Γ = 4πV∞a çift kök,
     Γ > 4πV∞a), Rankine half-body / oval, köşe, duvar, vortex çiftleri
   - Not: cisim içindeki streamline'ları gizleme / cismi doldurma seçeneği Faz 4 katmanlarına eklenebilir
6. ✅ **Paket C — Tema "teknik çizim kâğıdı"** [6] (konseptler canvas'ta seçildi, Tur 2 = C revize)
   - Program tam ekran açılır; üstte füme meşe (#A98B6D) ahşap band: logo (kare kâğıt + streamline + silindir),
     POTENTIAL FLOW LAB, sürüm, açık dosya
   - Menüler cetvel şeklindeki rail'de (mm / cm çizgili); Help'in sağında kunduz için boş yer (`beaver_perch_px`)
   - Kareli kâğıt zemin; paneller çift çizgili kart (antet gibi), başlık + kalın çizgi; plot kalın mürekkep
     çerçeveli kart, altında antet şeridi (SCENE / ELEMENTS / VIEW / FILE)
   - Açık + koyu tema (View → Theme); fontlar programla birlikte geliyor (IBM Plex Mono, Barlow,
     Barlow Condensed — SIL OFL, `assets/fonts`)
   - Tüm renk / boyutlar `app/theme.py`, çizimler `app/chrome.py`
   - Not (Paket D'de bakılacak): panellerin yeri değişince kartların görünümü; Properties paneli
   - Not (Faz 6): kunduz bu turda eklenmedi — tasarımı daha "tatlı" olacak şekilde revize edilecek.
     Yeri ve duruşu kesin: Help'in sağında; kafası cetvelin üst kenarının üstünde (ahşap bandın içinde),
     patileri cetvelin kenarına tutunuyor, gövdesi cetvelin arkasında; sürükleyince yerinden çıkar.
     Konuşma kutusu: pixel yazı (VT323), harf harf yazılır, kâğıt renk kutu + mürekkep pixel çerçeve;
     "İleri" butonu ileride header ahşap rengi olacak
7. ✅ **Paket D — Panel sistemi** [4] (27 Ekim'de kapsam güncellendi)
   - Paneller sadece plot'un solunda veya sağında, alt alta (üste / alta konamaz, yüzen pencere yok,
     sekme olarak üst üste binmez); sürüklerken yer gösteren bant temanın ahşap renginde
   - ADD paleti başlığından tutulup bütün olarak plot'un soluna / sağına taşınır (boyutu değişmez)
   - Plot settings bölümleri (View range, Streamlines, Layers, Animation, Computation): başlığa sağ tık
     veya View → Panels → Plot settings sections ile gizlenir / geri gelir (başlıkta "n HIDDEN")
   - Yerleşim kapanışta kaydedilir, açılışta aynı gelir; View → Panels → Reset layout ilk hale döndürür
   - Alt alta panellerin boyunu ayarlama (aradaki çizgiyi çekme) aynen duruyor
8. ✅ **Faz 2c — Plot'ta sürükleme + fare modları + klavye kısayolları**
   - Plot'un üstünde Select · Move · Pan (View → Mouse mode, tuşlar V / M / H)
     - Select: tıklayınca seçer, sürükleyince element kaymaz (yanlışlıkla taşımaya karşı)
     - Move: elementi tutup taşı (source, vortex, doublet, sector köşesi, duvar paralel kayar);
       Shift = ızgaraya yapış (görünüme göre 0.1 / 1 …), Esc = iptal; bırakınca tek undo adımı
     - Pan: her yer görünümü kaydırır, hiçbir şey seçilmez
     - Her modda tekerlek zoom, boş yeri sürükleme pan
   - Sürüklerken hiçbir şey hesaplanmaz (streamline'lar soluklaşır, stagnation gizlenir), bırakınca hesap
   - ADD paletinden plot'a sürükle-bırak (her modda): bırakılan nokta pencerede konum olarak gelir,
     hız / şiddet girilir, Cancel = eklenmez; Shift ile ızgaraya yapışır; uniform flow'da sadece pencere
   - Edit → Keyboard shortcuts… (Help'te de): tüm kısayollar görülür / değiştirilir, çakışma engellenir,
     "Reset all to defaults"; değişiklikler kalıcı
   - Düzeltme: sürüklemeden sonra stagnation point'e tıklayınca dividing streamline yine çiziliyor
   - Sector köşesi artık stagnation point olarak işaretlenmiyor (ödevde istenmiyor; köşe zaten duvarların
     birleşimi); fizik tarafında hâlâ biliniyor
9. ✅ **Export** (File menüsü, Ctrl+E, plot barındaki Export butonu)
   - Figür: PNG (1×–4×; çizgi, ok ve semboller ölçekle büyür → ekrandaki gibi ama keskin), SVG ve PDF (vektör,
     rapor için); arka plan: plot rengi / beyaz / şeffaf; koyu temada "Light colors (for printing)"
   - SVG'de plot alanı kırpılır (Qt'nin SVG çıktısı kırpamadığı için eksenler ayrı çizilip birleştirilir),
     fontlar başka bilgisayarda yoksa Consolas / Arial'a düşer
   - Veri (CSV): elementler, stagnation point'ler, görünen streamline'lar, ızgarada u, v, |V|, Cp, φ, ψ
     (katı bölge ve tekil noktalar boş); ayraç virgül veya noktalı virgül + ondalık virgül (Türkçe Excel)
   - Seçenekler ve son klasör hatırlanır
   - Figürde eksenler dört tarafta (üst / sağ, alt / sol ile aynı; plot alanı ortada) — sadece dosyada,
     ekran değişmez; "with numbers and axis titles" ile üst / sağdaki sayılar kapatılabilir
10. ✅ **Faz 4a — Alan katmanları** (animasyon hariç)
    - Equipotential lines φ: kesikli çizgiler, aralık streamline aralığına göre (akış ağı: kareler);
      vortex / sector'ün branch cut'ında sahte çizgi yok; tekil noktaların dibinde (|V| > 5× tipik) çizilmez
    - Speed |V| ve Cp: dolu kontur bantları (vektör: ekranda pürüzsüz, SVG / PDF'te keskin), bant sınırlarında
      ince çizgi, sağ üstte değer lejantı (export'ta da var); aynı anda tek renk haritası
    - Cp için referans hız: Computation → Cp reference (V∞ veya Custom V_ref); probe, Cp bantları ve CSV aynı
    - Computation → Grid quality (Low / Medium / High) gerçek: alan katmanlarının ızgarası
    - Ayarlar sahne dosyasına kaydedilir (field_quality, cp_reference)
    - Probe: u, v, |V|, Cp yanında φ ve ψ
    - Sürüklerken alan katmanları da soluklaşır, bırakınca yeniden hesaplanır
    - V∞ olmayan sahnede (sink, source + wall, sector) Cp: lejant yerine açıklama kartı, tıklayınca
      Computation → Custom V_ref açılır; Cp kutusunda "— needs V_ref" yazar
    - Bantlar tekil noktaya kadar dolu (ortada ızgaraya bağlı sekizgen boşluk yok); lejant aralığı
      görünen akışkandan, tekil noktalardan uzakta ve medyan hıza göre sınırlı (zoom'da patlamaz); Cp lejantı tam 1'de biter
11. ☐ **Faz 4b — Animasyon** [5]: parçacıklar ve / veya çizgi üstünde kayan desen, 60 fps hedefi,
    ayarları sonradan değiştirilebilir; (isteğe bağlı) cismin içindeki çizgileri gizleme / cismi doldurma
12. ☐ **Paket E2 — Animasyon performansı**: profiling, gerekirse OpenGL (ekran kartı) çizim, animasyon ile arka
    plan hesabının birlikte akıcı çalışması
13. ☐ **Faz 5 — Paketleme**: Python gerektirmeyen Windows 10/11 exe (zip içinde klasör), GitHub Releases,
    isteğe bağlı kurulum dosyası (Inno Setup), Numba önbelleği, .pflow dosyasına çift tıklayınca açılma
    (macOS şimdilik kapsam dışı)
14. ☐ **Faz 6 — Kunduz rehber ve cilalama** [7]: ilk açılışta atlanabilir tanıtım turu, Help yanındaki yeri,
    açma / kapama ayarı, animasyon modunda akışla süzülüp kaybolması ve geri dönmesi
15. ☐ **Faz 3 — Rapor malzemesi** (27 Ekim: program bitince, en sona alındı): doğrulama scripti, figürler ve
    tablolar (verification case'ler, duvarda V·n, stagnation karşılaştırmaları), sector kuralının yazılı
    açıklaması, 4–6 sayfa rapor, user guide
16. ☐ **Demo provası**

(Köşeli parantezdeki numaralar 26 Ekim'deki istek listesindeki madde numaralarıdır.)

Bir değişiklik beğenilmezse: her paket ayrı commit → GitHub Desktop → History → commit'e sağ tık →
"Revert changes in commit".
