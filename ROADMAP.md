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
     sekme olarak üst üste binmez); 28 Ekim'den beri bir tarafta yan yana ikinci sütun da olabilir; sürüklerken yer gösteren bant temanın ahşap renginde
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
Sıra 27 Ekim'de yeniden belirlendi (arkadaşın C++ / OpenGL projesiyle karşılaştırmadan sonra; kod kopyalanmadı,
sadece genel teknikler öğrenildi: döngünün tamamını derlemek, trail buffer, yüzey basıncı paneli, komut satırı doğrulama):

11. ✅ **Paket R1 — Yapı düzeni** (davranış aynı: 20 farklı durumun ekran görüntüsü önce / sonra piksel piksel aynı)
    - `app/canvas/` paketi: `PlotCanvas` ortak durumu tutar, her olayı katmanlara iletir; katmanlar ortak
      `PlotLayer` arayüzüyle ayrı dosyalarda (streamline, stagnation, field, element), fare işleri `interaction.py`'de,
      plot ayarları tek yerde (`PlotSettings`, sahne dosyasına kaydedilen her şey) → yeni katman = bir sınıf + bir satır
    - `app/window/`: ana pencerenin parçaları (layout, menus, files, exporting, status); `main_window.py` sadece birleştirir
    - `app/export/` (figure / data / dialogs; CSV kısmı Qt'siz → Paket V'deki komut satırı için hazır),
      `app/chrome/` (style / header / cards / palette; kunduz header'a gelecek)
    - Katman anahtarları ve slider ölçekleri tek listede (önceden iki yerde tanımlıydı)
    - Kullanılmayan kod silindi; kapanan pencere ve diyaloglar artık bellekten siliniyor (önceden kalıyordu:
      testlerde her pencere bir sonrakini yavaşlatıyordu)
12. ✅ **Paket R2 — Hız**
    - Numba kernel'i: sahne tek bir tablo (16 ayrı dizi yerine) → bir hız hesabı 244 → 38 ns; çizgiler kompakt döner
    - Jobard–Lefer'in Python'da kalan işleri derlendi: raster işaretleme / test, komşu seed'ler, seed seçimi,
      ok yerleri, soluklaşan uçların parçaları, stagnation için Newton (Numba yoksa NumPy yolu aynen var, testli)
    - Kısa yardımcılar GIL'i bırakmıyor (bırakıp geri almak pencereyle yarışta işin kendisinden pahalıydı)
    - Ölçüm (en iyi 5): görünen çizgiler ~38 → ~10 ms, tam güncelleme ~270 → ~55 ms, pan adımı ~150 → ~20 ms;
      `streamline_quality.py` sonuçları birebir aynı (çizgi sayısı, aralık, iç uçlar)
    - Not: NumPy'nin |z|'si işlemciye göre son bitte farklı yuvarlanıyor; bu yüzden bazı sahnelerde 1–2 çizgi
      farklı yere konabiliyor (eski kod da makineden makineye böyleydi); kalite aynı
    - Sürüklerken elementin sembolleri yeniden kurulmuyor, yerinde taşınıyor: sürükleme ~27 → ~39 fps
    - **Live update while dragging** (Plot settings → Computation, program ayarı, varsayılan açık): sürüklerken
      görünen bölgenin çizgileri arka planda yeniden hesaplanır (en yeni konum önce); bırakınca her şey tam
      hesaplanır, Esc eski çizgileri geri getirir. Ölçüm (2 çekirdekli test makinesi, yazılımsal çizim):
      saniyede ~27–33 çizgi güncellemesi, pencere ~26–32 fps (canlı kapalıyken ~39 fps)
13. ⏸ **Ara kontrol — deneme exe'si**: 27 Ekim'de Faz 5'e bırakıldı (sadece erken risk kontrolüydü; Numba
    exe'de çalışmazsa program NumPy yoluyla yine çalışır)
14. ✅ **Faz 4b — Animasyon** [5] (stil A: particle'lar, stil B: streamline üstünde darbeler)
    - Static / Animated (üst bar ve View menüsü); Animated'da streamline'lar soluk, oklar gizli
    - Particle'lar Numba'da (RK2 + ara adımlar, ~0.2–0.7 ms / kare); görünümden / akışkandan çıkan, tekil noktaya
      yaklaşan, plakayı geçecek olan veya ömrü dolan yeniden doğar (ömürler kaydırılmış: hepsi birden değil)
    - Hıza göre renk: pastel mavi (yavaş) → kırmızı (hızlı), ölçek ≈ 2 × görünümün tipik hızı, sağ üstte lejant
      (|V| / Cp bantları açıksa onların lejantı)
    - İz: tek bir resim her karede biraz soluklaşır (aşağı yuvarlayan tam sayı: hayalet iz kalmaz), adımlar
      üstüne Numba'da antialiased çizgi olarak çizilir; çok uzun adım (tekil nokta dibi) çizilmez
    - Animasyon sırasında diğer tüm plot öğeleri resim olarak önbellekte (DeviceCoordinateCache): bir kare
      ~2–3 ms, ~60 fps (test makinesinde); export sırasında önbellek kapanır (keskin çıktı)
    - Ayarlar: Particles / Speed / Trail length (sahneyle kaydedilir); Space = Pause (kısayol değiştirilebilir)
    - Sürüklerken particle'lar yeni akışta akmaya devam eder
    - ✅ Stil B (27 Ekim): her streamline ~2 piksellik parçalara bölünür, her parçaya çizginin başından
      yolculuk süresi τ = ∫ds/|V| hesaplanır; frac((t − τ)/T) küçükken parça yanar (parlak baş, sönen kuyruk).
      Darbeler eşit ZAMAN aralıklı: hızlı yerde uzar, yavaş yerde (durma noktası) sıkışır. Sürüklerken önizleme
      çizgilerini takip eder; Pause'dayken zoom / pan yeniden çizer. Kare ~3–4 ms
    - ✅ Üst barda üç görünüm düğmesi: Static · Particles · Pulses (View menüsünde de, kısayol atanabilir).
      Plot settings'te iki ayrı bölüm: Particles (Count, Speed, Trail length) ve Pulses (Speed, Pulse length,
      Spacing); ayarlar sahneyle kaydedilir, görünüm modu kaydedilmez
    - ✅ Solid bodies katmanı (27 Ekim, Layers → "Solid bodies (filled)", varsayılan kapalı): cismin içi
      (silindir, Rankine oval / half-body) kum rengi + hafif tarama ile dolu, yüzeyi koyu çizgi; içerideki
      streamline / ok / particle / pulse görünmez, particle'lar cismin içinde doğmaz. Cisim = geriye doğru
      izlenen streamline'ı source / doublet'ten başlayan ya da onların etrafında dönen akışkan
      (`stagnation.trace_origin`); dividing streamline'lar ekran ızgarasında sınır, bölgeler birkaç izle
      sınıflanır. Serbest akış yoksa cisim yok; serbest vortex'in etrafındaki kapalı döngüler cisim sayılmaz.
      Γ > 4πV∞R'de silindirle birlikte dönen halka da cismin parçası (akışta aralarını ayıran bir şey yok)
    - ✅ GIF / MP4 kaydı (27 Ekim): File → Export animation… (Ctrl+Shift+E) veya üst bardaki Export menüsü.
      Seçenekler: Particles / Pulses, süre 1 · 2 · 3 · 5 · 10 s, kare hızı (GIF 20 / 25, MP4 24 / 30 / 60 fps),
      çözünürlük (GIF 1–2×, MP4 1–4×), arka plan, dört kenarda eksen, açık renkler. Kareler ekran görüntüsü
      değil: animasyon her karede tam 1/fps ilerletilip PNG export'u gibi çizilir (bilgisayar hızından bağımsız
      akıcı); önce ~1.5 s görünmeden çalışır. GIF: Pillow (ortak palet, değişmeyen pikseller saydam), MP4:
      imageio-ffmpeg (H.264, CRF 18). İkisi de isteğe bağlı paket; yoksa diyalog hangi paketin gerektiğini yazar.
      Ek düzeltme: renk lejantı k× PNG'de de büyüyor (önceden ekran boyunda kalıyordu)
14b. ✅ **Gözden geçirme ve optimizasyon** (27 Ekim)
    - Hata düzeltmesi: bazı pencere boylarında (ör. 1200 × 760) görünüm saniyede ~40 kez ileri geri
      zıplıyordu (sol eksen yazısının genişliği "-2.5" / "-2" arasında gidip geliyor, aspect lock y aralığını
      değiştiriyordu); eksen yazı alanı artık sadece büyüyor
    - `app/paths.py` (dosya yolları tek yerde), `packaging/potential_flow_lab.spec` (Linux'ta denendi: exe
      Numba çekirdeklerini kullanıcının önbellek klasöründe tutuyor; 1. açılış ~18 s CPU, 2. ~2 s)
    - Tek cisim tanımı: `stagnation.trace_origin` (serbest akış / cisim / kapalı döngü / bilinmiyor) hem
      durma noktası türlerinde hem çizilen dividing dallarında hem Solid bodies'de; serbest vortex artık
      "in the flow". `bodies.find_bodies`: her cismin yüzeyi saat yönünün tersine sıralı (Paket S için)
    - Plot ayarları tek tablodan: `model/plot_settings.py` + `app/canvas/settings.SLIDERS` +
      `PlotCanvas.set_<ad>` (yeni ayar 6 yer yerine 3 yer)
    - `physics/verification.py` (doğrulama tablosu modül; script, test, ileride `--verify`),
      `PlotCanvas.compute_now()` (pencere açmadan her şeyi hemen çizer: komut satırı export'u için)
    - Pencere küçültülünce animasyon dinleniyor; çekirdekler ilk streamline'lardan sonra arka planda
      hazırlanıyor (ilk Particles / Pulses / Solid bodies tıklamasında donma yok); animasyon açıkken PNG
      export'unda particle / pulse resmi figür çözünürlüğünde yeniden çiziliyor (keskin); dividing seed'leri
      tekrar tekrar eklenmiyor
    - `physics/streamlines.py` → `physics/streamlines/` paketi (aynı sonuç, bit bit karşılaştırıldı);
      animasyon katmanı üç dosya; `requirements-dev.txt`; sürüm 0.5.0
14c. ✅ **Kullanıcı geri bildirimi — 5 düzeltme** (27 Ekim, her biri ayrı commit)
    - Üst bar: Static · Particles · Pulses düğmeleri arasında Select · Move · Pan ile aynı boşluk; Pulses ile
      Select arası biraz daha geniş
    - Equipotential lines: tekil noktaların etrafında pürüzlü boşluk yerine temiz daire (yarıçap: halkadaki en
      yüksek hız 5× tipik hıza inene kadar); Solid bodies açıkken cismin içinde φ çizilmez. Yeniden çizim
      ~245 → ~9 ms (kesikli kalem 1 px kozmetik: Qt'nin hızlı yolu; ekran kartına gerek kalmadı)
    - Particles: Select / Pan ile kaydırırken izler kaybolmuyor (eski resim yeni görünüme kaydırılarak /
      ölçeklenerek taşınır; çok büyük zoom'da temizlenir)
    - Stagnation point'ler büyük / hızlı bir zoom'dan sonra eksik kalmıyor: görünüm aranan bölgeden 2.5×
      küçülünce tekrar aranır (zayıf source dibindeki, birbirine çok yakın noktalar)
    - Doublet ekseni serbest akışla hizalı değilse (δ ≠ α) durum çubuğunda uyarı: "bu silindir akışı değil,
      serbest akışın bir kısmı doublet'in içinden geçiyor; silindir için δ = α". Solid bodies böyle içinden
      akış geçen bölgeleri (net kaynak ≤ 0 iken örneklerin %25'ten fazlası serbest akıştan gelip gidiyorsa)
      doldurmuyor (eğik source–sink çifti de)
    - Ek: zoom yapılmış görünümde (ör. silindirin sadece üstü) cisim doğru doluyor: tüm sahnenin durma
      noktaları / dividing streamline'ları bir kez hesaplanıp görünümde yerel olarak yeniden izleniyor, uzak
      kutu sahneye göre; dolgu görünümün kenarına kadar (önceden yarım pikselde altındaki çizgi seçiliyordu)
14d. ✅ **Solid bodies: zoom'dan bağımsız kural + düzeltmeler** (27 Ekim, kullanıcı geri bildirimi)
    - Plot settings taşması: V∞'suz sahnede Cp kutusunun yazısı "— needs V_ref" ile uzuyor, panel içeriği
      panelden genişleyip sağ taraf (slider uçları, handle'lar, yazı) kesiliyordu. Not artık kutunun altında
      küçük satır ("set V_ref…" linki); içerik genişlerse panel de genişliyor
    - Yeni kural (`stagnation.open_elements`): free stream'in İÇİNDEN geçtiği source / doublet cisim yapmaz
      (gerçek bir cisim free stream'i yutamaz). Her source / doublet etrafındaki küçük halkadan streamline'lar
      iki yöne izlenir; free stream bir sink / doublet'e giriyorsa (ya da net çıkışı olmayan bir grubun
      fluid'i uzağa gidiyorsa) o grup cisim değildir. Sahneye bağlı, görünüme bağlı değil → her zoom'da aynı.
      Eski bölge bazlı "%25" kuralı kalktı
    - Örnek: lifting cylinder'da vortex doublet'in merkezinden ayrılınca (vortex doublet'teki akışı −15.6°
      döndürüyor) zoom in'de yanlış dolgu vardı, artık yok; durum çubuğunda uyarı: "The flow at the doublet …
      goes at −15.59° … For a lifting cylinder put the vortex at the doublet's center." (δ ≠ α uyarısı artık
      doublet'teki gerçek akışa göre: duvar image'ları vb. dahil)
    - Sector flow da free stream sayılıyor: köşe akışındaki source'un half-body'si dolu
    - Kontrol: 21 preset + 8 ek sahne, her biri 3–7 görünümde (tam, 3× uzak, pan, 4× ve 12× zoom) sahne
      ölçeğinde izlenen referans haritayla karşılaştırıldı: 135 görünümde 274 311 hücreden 3'ü farklı
      (hepsi cisim kenarında)
    - Hata düzeltmesi (bu kontrolde bulundu): "Source in a 90° corner" sahnesinde bazı zoom'larda derlenmiş
      tracer hızı tam 0 olan noktaya (iki duvarın köşesi) basınca ZeroDivisionError veriyordu → o görünümde
      stagnation point / çizgiler hesaplanmıyordu
14e. ✅ **Solid bodies kökten + φ kesik boşluğu** (28 Ekim, kullanıcı geri bildirimi)
    - φ: vortex'in branch cut'ında (solunda) boşluk vardı (çizgiler iki yanda duruyordu, aralık eşit değildi).
      Δφ artık en güçlü vortex'in Γ'sını çift katına tam bölen değere yakın seçiliyor ve çizgiler sin(πφ/Δφ)'nin
      sıfırları olarak çiziliyor (bu fonksiyon Γ'lık sıçramayı görmüyor): çizgiler kesikten geçip vortex'in
      etrafında kapanıyor; her nokta Newton ile tam φ = n·Δφ'ye oturtuluyor
    - Kök neden 1 — kayıp stagnation point: zayıf bir source hızlı bir akıştaysa noktası çok yakında
      (m/2πU); Newton'un başlangıç halkası görünüme göre (0.05·L) olduğundan bulunmuyordu → half-body'nin
      yüzeyi yok, bölgeler birleşiyor, dolgu saçmalıyordu. Artık her elemanın kendi ölçeğinde de halka var;
      uzak görünümde "cismin içinde" diye atılmaması için o noktalar kendi ölçeklerinde izleniyor
    - Kök neden 2 — uyarı ile dolgu çelişiyordu: doublet'in açık/kapalı kararı artık uyarıyla AYNI test
      (doublet ekseni oradaki akışla ±0.5° içinde mi; sızıntı ≈ açı(rad) × cismin kestiği akış). Uyarı
      "For a (nearly) closed body set δ = …" diyor; söyleneni yapınca cisim temiz kapanıyor
    - Kök neden 3 — neredeyse kapalı doublet'in ince sızıntısı kuyruk / çentik yapıyordu: net çıkışı olmayan
      cismin fluid'i uzağa gidiyorsa cisim sayılmıyor; cismin içine giden dallar (çizilmeyen) sınır olarak
      kullanılıyor; birkaç piksellik kıymıklar çevresine göre doluyor; kenar çizgisi durma noktasında kapanıyor
    - Kök neden 4 — tüm sahne ölçeğinde küçük half-body'nin burnundaki yüzey dalları tracer'ın tekil nokta
      yarıçapının içinde kalıp siliniyordu (zoom'da o yüzey eksik): yakında tekil nokta varsa ince tracer
    - Kontrol: 21 preset + 11 elle seçilmiş + 65 rastgele sahne (uniform + 1–3 source / sink / doublet / vortex),
      her biri 3–7 görünümde, sahne ölçeğinde izlenen referans haritayla karşılaştırıldı (sonuç commit
      mesajında)
15. ✅ **Paket S — Surface pressure** (28 Ekim)
    - Layers → "Surface pressure (Cp on surfaces)": cisim yüzeyleri ve ıslak duvarlar (symmetry wall, sector
      flow kenarları) kalın çizgi olarak Cp renginde (mavi = emme, kırmızı = durma, Cp = 1), sol üstte lejant
    - Cisim yüzeyleri görünümden bağımsız, tüm sahne için arka planda bulunur (`physics/surface.py`: kapalı
      cisim saat yönünün tersine tek halka; half-body açık); yüzeyde eşit aralıklı noktalar, hız tam orada
    - Surface pressure paneli (solda açılır; View → Panels): yüzey seçimi, Cp grafiği θ (merkez etrafında,
      serbest akıştan; Anderson'daki gibi ön durma noktası 180°) / s (yüzey boyunca) / x (akış boyunca) —
      açık cisimde x, duvarda s'ye kendiliğinden geçer; "Suction up" (−Cp yukarı); silindir / lifting
      cylinder'da analitik Cp = 1 − (2 sin θ − Γ/2πaV∞)² kesikli; grafikte gezinince plot'ta halka
    - Kapalı cisimde basınç integrali −∮ p n ds (birim açıklık): L′/ρ, D′/ρ ve ρ ile N/m; cisim tek başına
      uniform akıştaysa Kutta–Joukowski (−ρV∞Γ) ve d'Alembert (0) ile fark %; duvar / başka eleman varsa
      neden karşılaştırma olmadığı yazılı. Ölçülen: lifting cylinder Γ = −2 → L′/ρ = 2.0002 (%0.01),
      Γ = −15 (halkalı) 15.0013, Rankine oval / silindir sürüklemesi < 1e-3; ard arda iki silindir: eşit ve
      zıt kuvvet; zemindeki silindir aşağı çekiliyor
    - CSV: panelde Export CSV… ve File → Export data → "Surface pressure" (yüzey, x, y, s, θ, x akış boyunca,
      u, v, |V|, Cp); V∞ yoksa panel Cp reference'a link veriyor
    - `find_bodies` artık bitişik cisim bölgelerini tek cisim sayıyor, içe giden dalları sınır olarak alıyor
    - Düzeltmeler (28 Ekim, kullanıcı geri bildirimi): grafikte gezinirken tepe noktalarında grafik zıplamıyor
      (eksen aralıkları sabit, nokta aralığa dahil değil); "x along the flow"da halka üst / alt yüzey arasında
      atlamıyor (ekranda fareye en yakın nokta); sayılar bölümlü ve kısa satırlı (CP ON THE SURFACE / FORCE PER
      UNIT SPAN, değerler N/m, teori ve fark % altında küçük); panel kaydırılabilir → sağdaki sütuna alt / üst
      olarak ya da yanına ikinci sütun olarak taşınabiliyor (nested docks), yeri hatırlanıyor, açılışta kendiliğinden
      açılmıyor (katmanla ya da View → Panels); 125 % ölçekte plot'un sağ kenarında çıkan ikinci koyu çizgi
      (önbelleğe alınmış arka planın boyanmayan son piksel sütunu) — arka plan önbelleği kapalı
16. ▶ **Paket V — Komut satırı + otomatik doğrulama**: pencere açmadan figür / CSV export, `--verify`: verification
    case'ler ve analitik çözümlerle karşılaştırma tablosu (Markdown + CSV) ve rapor figürleri
17. ☐ **Dye rake** (isteğe bağlı): çizilen rake'ten pulse'lı boya → streakline; taşınır, döndürülür, kaydedilir
18. ☐ **Paket E2 — Performans + ekran kartı** (isteğe bağlı): animasyon çalışırken profiling, gerekirse
    "Use graphics card (OpenGL)" seçeneği (açılamazsa normal çizime döner)
19. ☐ **Faz 6 — Kunduz rehber ve cilalama** [7]: ilk açılışta atlanabilir tanıtım turu, Help yanındaki yeri,
    açma / kapama ayarı, animasyon modunda akışla süzülüp kaybolması ve geri dönmesi
20. ☐ **Faz 5 — Paketleme**: Python gerektirmeyen Windows 10/11 exe (zip içinde klasör), GitHub Releases,
    isteğe bağlı kurulum dosyası (Inno Setup), Numba önbelleği, .pflow dosyasına çift tıklayınca açılma
21. ☐ **Faz 3 — Rapor ve user guide**: malzemenin çoğu Paket V'den (figürler, tablolar, doğrulama), sector
    kuralının yazılı açıklaması, 4–6 sayfa rapor, user guide
22. ☐ **Demo provası**

Sıkışırsa bırakılacaklar (önce bırakılan önce): dye rake, OpenGL, tanıtım turu. Animasyon, surface paneli,
doğrulama ve exe dokunulmaz.

(Köşeli parantezdeki numaralar 26 Ekim'deki istek listesindeki madde numaralarıdır.)

Bir değişiklik beğenilmezse: her paket ayrı commit → GitHub Desktop → History → commit'e sağ tık →
"Revert changes in commit".
