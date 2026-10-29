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
    - Surface pressure kutusunun altında da Cp'deki gibi "needs a reference speed V_ref: set V_ref…" notu, plot'ta
      da aynı tıklanabilir not kartı (V∞ yoksa); birbirine çok yakın iki half-body (aralarından ince bir serbest
      akış kanalı geçiyor, ~2 ızgara hücresi): yüzeyler artık iki ayrı çizgi (önceden ikisinin etrafından tek
      çizgi + kırıntılar). Izgara iki yanı da cisim görünce çizginin yanından streamline geriye izleniyor;
      parçalar durma noktalarından birleştiriliyor; uzun ince kanal "kıymık" sayılıp doldurulmuyor
    - Boş sayfada V_ref notu / kartı çıkmıyor (eksik bir şey yok); "Along" listesinde o yüzeye uymayan seçenek
      (açık cisimde θ, duvarda θ ve x) hiç görünmüyor
16. ✅ **Paket V — Komut satırı + otomatik doğrulama** (28 Ekim)
    - `python main.py --verify [--out DIR] [--no-figures]`: `verification.md` (figürlerle) + `verification.csv` +
      `figures/*.png`, ~10 s, hepsi tutarsa çıkış kodu 0. Üç bölüm: (1) analitik formüller (34 satır, 1e-9),
      (2) ödevin 9 verification sahnesi — programın çizdiği streamline'lar (uniform: α açısında düz, source / sink:
      radyal ve yönü, vortex: daire ve dönüş yönü), Newton'la bulunan durma noktaları sin θ = Γ/(4πV∞a)'da,
      izlenen yüzey r = a, üzerinde Cp, basınç integralinden L′ (Kutta–Joukowski) ve D′ (d'Alembert), duvardan
      geçiş yok ve duvardaki durma noktası; her sahne kaydedilip tekrar açılıyor (verification case 5: aynı
      elementler, başlık / görünüm / ayarlar, aynı streamline'lar bit bit), (3) sayısal yöntemlerin doğruluğu —
      çizilen çizgiler boyunca ψ (çizgi aralığının %0.2–0.3'ü), half-body burnu, Rankine oval √3, Γ = −4πV∞a çift
      kök, köşedeki çift sıfır, silindir alanı π, half-body şekli, Γ = −2 / −6 / −15 / 3 için kaldırma. Ölçülen:
      102 / 102 OK (lifting cylinder L′ = 2.4502 N/m vs 2.45, durma noktası 1e-16 m, |r − a| ≤ 8e-4, Cp ≤ 1.5e-3)
    - `python main.py sahne.pflow --figure x.png|svg|pdf --data x.csv`: File → Export ile aynı çıktı; görünüm,
      katmanlar (+/−), plot alanı boyutu, ölçek, arka plan, koyu tema, V_ref, tablolar, ayraç seçilebiliyor;
      hatalarda çıkış kodu 2. Plot ekranda hiç görünmüyor (Linux'ta ekran yoksa Qt offscreen)
    - `physics/program_checks.py` (Qt'siz), `app/cli/` (seçenekler, headless plot, rapor), `tests/test_cli.py`
    - **Help → Run verification…** (28 Ekim, kullanıcı isteği): aynı rapor programın içinden, arka planda
      (pencere kullanılabilir kalıyor, ilerleme çubuğu). Sonuç tek satır ("102 of 102 checks OK") + katlanmış
      ağaç (3 bölüm → durumlar / sahneler → check'ler). Bir check seçilince sağda nasıl hesaplandığı: Theory
      (analitik formül), Program (programın yaptığı hesap: hangi kod, kaç nokta, hangi yöntem), Tolerance (neden
      o değer) ve sayılar; sahne seçilince figürü. Open full report (verification.html: aynı açıklamalar her
      satırın altında katlı), Open folder, Save report to…, Run again. Rapor programın veri klasörüne yazılıyor
    - Her check'e `how` alanı (Theory / Program / Tolerance), CSV'de de son sütun
    - Köşedeki durma noktası: w ∝ z³ (üçlü kök) olduğu bulundu → konum ancak (1e-16)^(1/3) ≈ 5e-6 hassasiyetle
      belirlenebilir; tolerans 1e-5 bu yüzden
    - Durum çubuğundaki sahne kontrolü ("⚠ 2 warnings · 1 note") artık tıklanabilir (28 Ekim, kullanıcı isteği):
      üstünde bir panel açılıyor — her error / warning / note, hangi elementle ilgili olduğu ([numara] tip:
      parametreler) ve tam metniyle; satıra tıklayınca o element seçiliyor. Önceden sadece fareyle üstünde
      beklerken tooltip olarak görünüyordu
    - Faz 5 için not: komut satırı modu (`--verify` …) konsolsuz GUI exe'sinde çıktı göstermez; menüden
      çalıştırma bunu karşılıyor, istenirse ayrıca küçük bir konsol exe'si eklenebilir
Kalan işler — 28 Ekim'de yeniden sıralandı (süre sınırsızmış gibi: hepsi yapılacak). Sıra mantığı: önce
sağlamlık (hata yakalama, kurtarma) → son özellik (kunduz) → optimizasyon → kod düzenleme → görsel / metin son
kontrolü → en son kodla kapsamlı rastgele test → paketleme → rapor → son kontrol → demo. Exe bilerek sona
bırakıldı (kullanıcı kararı).

17. ✅ **Beklenmeyen hata yakalayıcı + log dosyası** (28 Ekim)
    - `app/errors.py`: yakalanmamış her hata (buton, çizim, arka plan hesabı, başka thread) log'a traceback'iyle
      yazılır ve "Unexpected error" penceresi çıkar: ne olduğu, Show details, Copy details (sürümlerle), Open log
      folder, Continue — program açık kalır. Aynı hata (aynı yer) bir kez gösterilir, tekrarları sadece
      sayılır (çizimde her karede tekrarlayan bir hata pencere yağdırmaz); pencere açıkken gelen başka hata
      kapanınca gösterilir
    - Log: programın veri klasöründe `logs/potential-flow-lab.log` (3 × 1 MB): açılışta sürümler (program,
      Python, işletim sistemi, PySide6, NumPy, Numba, exe mi), açılan / kaydedilen dosyalar, Qt uyarıları,
      field layer / verification hataları. Help → Open log folder
    - Exe'de konsol yok: print / stderr log'a gider (yoksa ilk print'te program düşerdi)
    - Tam çökme (süreç ölür): faulthandler yığını `logs/crash.txt`'e yazar, sonraki açılış log'a aktarır
      (`previous_crash()` — madde 18'de "geri getir?" için); normal kapanışta dosya silinir
    - Testler: `tests/test_errors.py` (slot'ta, thread'de, çizimde hata; tekrar; sıraya alma; konsolsuz;
      gerçek segfault ile çökme dosyası)
18. ✅ **Otomatik kaydetme / çökme sonrası geri getirme** (28 Ekim)
    - `app/recovery.py`: sahnede kaydedilmemiş değişiklik varken son değişiklikten (ya da görünüm değişiminden)
      3 s sonra kopyası programın veri klasörüne yazılır (`recovery/session-….pflow` + hangi dosya, başlık, saat);
      kaydedince, Undo ile kaydedilmiş hale dönünce, program normal kapanınca silinir. Kullanıcının kendi
      dosyasına hiç dokunulmaz
    - Her oturum bir kilit dosyası tutar (QLockFile); sahibi artık çalışmayan bir kopya = o oturum normal
      kapanmadı. Açılışta "Restore unsaved scene": başlık, dosyası (ya da "never saved"), son değişiklik saati,
      çökme varsa log'a yönlendirme → Restore (kaydedilmemiş sahne olarak, dosya adıyla — Ctrl+S oraya yazar;
      Undo önceki sahneye döner) / Discard / Not now (sonraki açılışta tekrar sorulur). Aynı anda açık başka
      bir programın kopyasına dokunulmaz. Kopya yoksa ama çökme olduysa durum çubuğunda not
    - Testler: `tests/test_recovery.py` (kopya / kaydedince silinme / undo / normal kapanış / çalışan oturum
      sorulmuyor / gerçekten düşen bir süreçten geri getirme / Not now / Discard); testler artık kullanıcının
      veri klasörüne değil Qt'nin test klasörüne yazıyor
    - Düzeltme (28 Ekim): Particles açıkken New / her şey silinince ya da gizlenince eski izler sahnede
      kalıyordu (akış yokken son adımlar her karede yeniden çiziliyordu) — artık resim temizleniyor
    - `CLAUDE.md`: başka bir hesaptaki Claude'un projeyi devralabilmesi için özet (tercihler, mimari, dersler,
      durum); her pakette "Current status" güncellenecek
19. ▶ **Faz 6 — Kunduz rehber** [7]
    - ✅ Aşama 1 (28 Ekim): karakter ve etkileşimler (`app/beaver/`). Görünüm: kullanıcının Gemini taslaklarından
      esinlenen ama baştan çizilmiş piksel kunduz, kırmızı bandana (uçları 3 karede rüzgarda oynuyor); pozlar
      koddan üretiliyor (raf, önden, yandan + 2 adım yürüme, tutulunca, cama vurma, akışta yüzme + kürek, düşme,
      girdap) → her açı / boyut keskin, 125 % ölçekte bile tam piksel. Konuşma: piksel çerçeveli balon, Pixelify
      Sans, harf harf yazma + imleç; metinler İngilizce (`lines.py`)
    - Davranış: rafta göz kırpar, 3 dk işlem yoksa uyur (Zzz), dokununca uyanır; ensesinden tutulup taşınır
      (sarkaç gibi sallanır). Static: cam şakası → zıplayıp cetvelde yürüyerek eve. Particles: tracer (RK4,
      particle'larla aynı zaman ölçeği, Space ile durur), yönüne bakar, en çok 30° eğilir; görünümden çıkınca
      sağdan yürüyerek döner; sadece vortex → 2 tur sonra başı döner, zıplar; vortex + sink → dönerek küçülür,
      yutulur; stagnation point → durur, espri, zıplar; solid body / duvar arkası → bırakılamaz. Pulses: en
      yakın streamline'a basar, pulse layer'ın kendi zamanlamasıyla her pulse çarpınca düşer, line boyunca
      itilir, kenarda BONK; 16 s'den fazla kalırsa kendisi kaçar
    - Zoom / pan / mod değişimi: Static'te ekrana (cama) sabit; Particles / Pulses'ta veriye sabit (plotla
      birlikte hareket), görünüm dışında kalırsa "you zoomed me out" → eve. Mod değişince: akıştan cama, camdan
      akışa ("Splash!"), akıştan line'a. Yeni / boş sahne → eve. Pencere boyutu değişince yerinde kalır
    - Program olaylarına tepki: hata çıkınca, kaydedince (10 dk'da bir), Run verification sonunda; rafta çift
      tıklayınca "fun fact"; ilk açılışta bir kez kendini tanıtır
    - Kısıtlar / güvenlik: sadece kendi piksellerine tıklanır (maske), tekerlek plota iletilir, seçimi bozmaz,
      export'ta görünmez, View → Beaver ile kapanır (hatırlanır); rafta beklerken zamanlayıcı yavaş (120 ms)
    - Testler: `tests/test_beaver.py` (21 test: sanat, maske, sürükle-bırak, cam + zoom, akış + çıkış, zoom ile
      görünüm dışı, vortex / drain, stagnation, solid body, pulse itmesi, mod değişimi, yeni sahne, aç / kapa,
      export'ta yok, balon, olaylar, tekerlek)
    - Düzeltmeler (28 Ekim, kullanıcı geri bildirimi):
      - Çok yavaş particle: görünümü geçmesi 18 s'den uzun sürecekse "Hmm, this flow is... slow", ~7 s sonra
        sıkılıp eve gider; hiçbir yolculuk 25 s'yi geçmez. Space ile duraklatılırsa "Frozen in time!", 8 s sonra
        yürüyerek eve
      - Çok yavaş pulse (iki pulse arası > 2 s): pulse yetişmeden line boyunca ileri koşup görünümden çıkar,
        konuşarak ("Ha! Catch me if you can!")
      - Çok hızlı akış: hiçbir satır okunmadan kesilmiyor — yazılıp okunacak süre (0.7 s + 0.03 s / harf) dolmadan
        yeni satır gelmez; önemli olaylar (çıkış, BONK, stagnation …) sıraya girer, küçük laflar atlanır; kunduz
        ekrandan çıkınca son sözü olduğu yerde kalır. Görünümü 2.5 s'den kısa sürede geçecekse "Whoa, way too fast!"
      - Diyaloglar: 39 durum, 177 satır (her durumda 2–10 seçenek), son söylenen birkaç satır tekrar seçilmez
      - Testler: yavaş yolculuk, çok hızlı akışta satırların okunabilir kalması, yavaş pulse'tan kaçış, uzun
        duraklatma (toplam 25 test)
    - ✅ Aşama 2 (29 Ekim): tıklama / sürükleme ayrımı (6 px'ten az kıpırdayan basış = tıklama → menü:
      Questions & answers, tour, fun fact; kıpırdarsa eline alınır). Soru–cevap: P (değiştirilebilir kısayol) ya
      da Help → Beaver; 10 soru, 1–9 / 0 / oklar + Enter / tıklama, cevaptan tıklayınca listeye döner.
      Tanıtım turu (`tour.py`, 16 adım): ilk açılışta bir kez sorulur; boş sayfadan başlar, her adımda ilgili
      parça kırmızı piksel çerçeveyle vurgulanır (gerisi hafif karartılır, her şey tıklanabilir kalır), kunduz
      yanına gider; okuma adımları Enter / Space / tıklama, "Your turn!" adımları kullanıcı yapınca geçer
      (uniform ekle, doublet ekle, düzenleme penceresini aç, Move ile taşı, Particles), Enter atlar, Esc bitirir;
      sonunda boş plot. Turda Space / Esc / Enter kısayollar yerine tura gider (ShortcutOverride), yazı alanında
      ya da açık bir pencerede tuşlara karışmaz. Sonraki açılışlarda sormaz; %35 "Welcome back!". Test için:
      `python main.py --first-run` ve Help → Beaver → Next start as a first-time user. Balon: uzun satırlar
      kırılıyor, seçenek satırları + ipucu satırı; testler: toplam 31
    - ☐ Sonra: isim (Psi geçici) ve yan / akış pozlarının rötuşu (kullanıcı: "yan görünüşler hâlâ biraz garip")
    - `CLAUDE.md` baştan yazıldı (29 Ekim): başka bir hesaptaki asistan için projenin özeti, kullanıcının çalışma
      tercihleri, çalıştırma / test, mimari, gün gün yapılanlar, karşılaşılan hatalar ve çözümleri, sıradaki işler
19b. ✅ **Devir sonrası kontrol + küçük düzeltmeler** (29 Ekim, yeni hesaptaki asistan)
    - Kontrol (kod değiştirmeden): temiz ortamda kurulum (Python 3.13, PySide6 6.12, Numba 0.68, pytest 9.2),
      tüm testler 699 / 700, `--verify` 102 / 102, bağımsız fizik karşılaştırması (uniform, source / sink, vortex,
      silindir ± Γ, rastgele duvarlar, 90° köşe, kanal, 4 sector açısı, 60° sector içinde source) 25 / 25, ~1e-16
    - pytest 9 uyumu: `pytest.approx()` artık iç içe listeleri (ok listesi: (x, y, açı)) kabul etmiyor →
      `test_kernel.py` okları dizi olarak karşılaştırıyor (pytest 8 ve 9'da geçiyor; değerler zaten birebir aynıydı,
      fark 0.0). README'nin "Durum" satırı güncellendi
    - Elements paneli: uzun isim / parametreler artık kesilmiyor ("Sector (wed…", "θ_w = …"). Parametreler eski
      sütunda (150 px) duruyor; sığmayan kısım parametre aralarından alt satırlara geçiyor (wall: 2 satır); isim
      sütuna yer bırakmıyorsa (sector) parametreler ismin altında. Kısa satırlar (uniform, source, vortex)
      birebir eskisi gibi, 30 px. Panel genişliği değişince yeniden bölünüyor; açık / koyu tema. Bedeli: 6
      elementli sahnede listede aynı anda 4 yerine 3 satır görünüyor. `app/panels.py` (`ElementRowDelegate`,
      `wrap_summary`), test: `test_elements_list_shows_full_names_and_wraps_parameters`
19c. ✅ **Tanıtım turu: kilit + düzeltmeler** (29 Ekim, kullanıcının Windows'ta turu adım adım denemesinden)
    - Kilit: tur sürerken pencerede tıklama / çift tıklama / tekerlek / sağ tık sadece adımın istediğine gider
      (`Step.allow`, `Tour.allows`, `Beaver._tour_blocks`): okuma adımlarında hiçbir şey, plot adımlarında zoom / pan
      (çift tık ve sağ tık yok), "Your turn!" adımlarında sadece gösterilen şey (UNIFORM / DOUBLET düğmesi, doublet
      satırına çift tık — tik kutusu değil, MOVE düğmesi ya da M, plot'ta doublet'i sürükleme, Density slider'ı,
      PARTICLES). Hover ve tooltip'ler her yerde çalışır; kunduz ve balonu her zaman tıklanır; açık element penceresi
      (ayrı pencere) etkilenmez
    - Tuşlar: Enter / Space = sonraki (eylem adımında atla), Esc = bitir — odak bir yazı kutusundayken de (önceden
      odak Plot settings'teki x / y kutusundaysa Enter oraya gidiyordu: "balona tıklamak gerekiyor" sorunu). Diğer
      tüm tuşlar tur boyunca yutulur (Move adımında M hariç); sağ ok artık "sonraki" değil
    - Balonda tıklanabilir **End tour (Esc)** ve **Next (Enter)** / **Skip (Enter)** düğmeleri; balona / kunduza
      tıklama sadece okuma adımında "sonraki" (eylem adımını yanlışlıkla atlamaz)
    - Alt adımlar: palette'ten sürüklerken plot aydınlanır ("Now let go over the plot"); element penceresi açılınca
      kunduz pencerenin yanındaki boş tarafa geçer, pencere vurgulanır, ne yapılacağını söyler (Apply → devam, Cancel
      → adıma geri); edit'te değişiklik yoksa "Nothing changed!" der ve bekler. Edit adımı artık pencere açılınca
      değil Apply ile geçiyor. MOVE'a basınca yeni adım: "doublet'i sürükle" (plot vurgulu), taşıyınca geçer
    - Plot settings adımından sonra yeni "Your turn!": Density slider'ı (tur bitince eski değerine döner)
    - Balon gösterdiği yerin üstüne binmez (sağ / sol / alt / üst denenir); Elements ve Plot settings adımlarında
      metnin paneli kapatması düzeldi; slider adımında kunduz panelin dışında. Metinlerde "press OK" → Apply
    - Tur 16 → 18 adım; bitişte Select modu. Testler: `test_beaver.py` +5 (kilit, tuşlar, düğmeler, balonun yeri her
      adımda, sürükleme / pencere alt adımları); ayrıca gerçek fare / tuş olaylarıyla 18 adımın baştan sona denemesi
      (43 kontrol) offscreen yapıldı — Windows'ta denenmedi
19d. ✅ **Konuşma balonu yeni görünüm + turun iki hatası** (29 Ekim, kullanıcının taslağı ve Windows'ta ikinci tur)
    - Balon "çizim kartı": kalın mürekkep çerçeve, basamaklı köşeler, gölge; başlıkta isim (PSI, geçici:
      `lines.NAME`) ve sağda etiket (TOUR 3/18, YOUR TURN · 4/18, MENU, QUESTIONS, ANSWER, WELCOME); yazı IBM Plex
      Mono (piksel font yerine); düğmeler sağ altta, asıl düğme başlıktaki ahşap renginde (plank #A98B6D: Next ›,
      Yes, show me around ›, More questions ›), diğerleri kağıt rengi + mürekkep çerçeve; açık / koyu tema. Alt satırdaki
      ipucu yazıları ("Enter / Space / click: next") kalktı — tuşlar aynen çalışıyor
    - Tüm balonlar aynı stilde: tur, menü (+ Close), soru–cevap (+ Close), cevap (Close / More questions ›), ilk açılış
      sorusu (artık düğmeler: No, thanks / Yes, show me around ›; Enter / 1 evet, Esc / 2 hayır), kısa laflar (başlıksız)
    - Hata 1: kunduzun menüsünden ikinci kez "Show me around" → bazen ilk adım hiç başlamıyordu: `bubble.clear()`
      eski satırları tutuyordu, hâlâ "yazılıyor" sanılan bir laf turun ilk adımını durduruyordu → `clear()` her şeyi
      sıfırlıyor, tur başlarken balon temizleniyor
    - Hata 2: Plot settings aşağı kaydırılmışsa Density adımında slider görünmüyordu (vurgu ve kunduz ekran dışı;
      kilit yüzünden kaydırılamıyordu) → tur o adımlarda paneli açıp slider'ı görünür yere kaydırıyor; Plot settings
      adımı paneli başa alıyor; slider'ın bölümü gizliyse adım atlanıyor
    - Testler: +2 (`test_a_second_tour_from_the_menu_shows_a_scrolled_away_slider`,
      `test_bubbles_have_the_name_a_tag_and_buttons`); turun gerçek olaylarla baştan sona denemesi yine 43 / 43
20. ▶ **Optimizasyon (+ Paket E2)**: ölçüm → iyileştirme: açılış ve ilk Numba derleme süresi, sürükleme, zoom /
    pan, animasyon ("Use graphics card (OpenGL)", açılamazsa normal çizim), Solid bodies, Surface pressure, export
    süreleri; ölçümler `scripts/` altında, önce / sonra sayılarıyla
    - ✅ **Baseline (OpenGL'siz, 29 Ekim)**: `python scripts/benchmark.py` (yeni; programı değiştirmez, 1536 × 830
      pencere, kullanıcının ayarlarına dokunmaz). Sonuçlar `benchmarks/2026-10-29_baseline_cloud-2cpu_run1/2.json`
      (bulut sunucusu, 2 CPU, ekran kartı yok, Qt offscreen = CPU ile çizim; iki çalışma arası fark ~%20–30).
      Önemli sayılar (medyan, iki çalışma):
      - Açılış: ilk kez (Numba derliyor) pencere 2.6 s, ilk çizgiler 16.6 s, tüm çekirdekler 18.8 s; sonraki
        açılışlar (önbellek) pencere 1.1 s, ilk çizgiler 1.2 s
      - Hesap (arka planda; pencere donmaz): streamline'lar lifting cylinder 88 ms, Rankine oval 185 ms, kanal 326 ms,
        8 elementli sahne 1.39 s; φ / |V| / Cp bantları 5–40 ms (High 14–90 ms); Solid bodies 34–93 ms; Surface
        pressure 5–10 ms; her şey birden 61 ms – 1.4 s
      - Çizim (plot'un bir kez tamamen çizilmesi, OpenGL'in hızlandıracağı kısım): 4–31 ms; tüm pencere 18–27 ms
      - Pan / zoom (60 fps zamanlayıcı): kare aralığı medyan 15–18 ms (≈ 60 fps), p95 20–29 ms; tüm katmanlar açıkken
        p95 25–40 ms, tek tük 90–130 ms takılma (8 elementli sahne / kanal, renk bantları + Solid bodies açık)
      - Doublet sürükleme: live update açık p95 23–25 ms, kapalı 16.5 ms (tam 60 fps)
      - Tepki süresi: Density slider 114–121 ms, layer açma 66 ms, pencere boyutu 124 ms, undo 260–300 ms, element
        ekleme 466–525 ms (pencere sadece ~35 ms bekliyor, gerisi arka planda hesap: yeni source'un streamline /
        stagnation / dividing'i)
      - Animasyon: Particles 1500 ve 5000 (en yüksek, trail 10), Pulses varsayılan ve en uzun: hepsi 62 fps, bir kare
        1.5–4.8 ms, pencere p95 16.4–17.1 ms (takılma yok)
      - Export: PNG 1× / 2× / 4× 92 / 149 / 318 ms, SVG / PDF 66–68 ms, CSV (hepsi) 237 ms, GIF 2 s 0.96 s, MP4 2 s
        1× 1.1 s, 2× 3.3 s; verification 2.3 s (figürlerle 8.0 s)
      - Sonuç: kullanıcının da gözlemi gibi her şey yeterince hızlı; tek darboğazlar tüm katmanlar açıkken pan /
        zoom'daki tek tük takılmalar (GUI thread'de renk bantları) ve kalabalık sahnelerin arka plan hesap süresi
        (OpenGL'in etkilemeyeceği hesap)
    - Kullanıcının Windows'u (29 Ekim, `benchmarks/windows_before.json`, 16 CPU, RTX 3050 Ti laptop): hesaplar
      %25–45 hızlı, çizim aynı (15–30 ms / kare); pan / zoom normal katmanlarla ~50 fps, tüm katmanlar açıkken
      32–45 fps (p95 31–37 ms) → asıl kazanç çizimde (GPU). Kararlar (kullanıcıyla): ekran kartı modu başlıkta bir
      kutu (ilk açılışta kapalı), açıkken ayrı "Graphics card" paneli (FPS, fps seçimi, genişletilmiş üst sınırlar);
      çok çekirdek her zaman açık; donanım kendiliğinden bulunur; ilk açılışta yükleme ekranı; laptop'ta Intel →
      NVIDIA geçişi program içinden. Dört paket:
    - ✅ **20.1 Yükleme ekranı + donanım tanıma** (29 Ekim): `app/splash.py` (yükleme ekranı: adım, donanım
      satırları, ilerleme; uzun işler thread'de, ekran donmuyor — ölçüldü: derleme sırasında her 0.7 s'de çizildi),
      `app/hardware.py` (işlemci adı / thread sayısı, ekran kartları Windows kayıt defterinden, OpenGL renderer
      **ayrı bir işlemde** sorulur — bu sunucuda OpenGL'siz bir bağlamda glGetString çağrısının işlemi segfault
      ile düşürdüğü görüldü; çökme / takılma (25 s) → "not available", program devam —, ekranlar ve Hz; profil
      QSettings'te, fingerprint (işlemci, çekirdek, kartlar, ekranlar + Hz, program / Numba sürümü) değişince
      yeniden), `app/startup.py` (hafif açılış ayarları: yükleme ekranı 0.3 s'de çıkıyor), Help → **Your
      computer…** (`hardware_dialog.py`, Check again), log'a donanım satırları. `physics/warmup.steps()`: pencere
      açılmadan önce her çekirdek hazır — eskiden pencerenin ilk hesabı `fade_cut` vb. ~3.8 s derliyordu, artık
      pencere açıldıktan sonra hiçbir şey derlenmiyor (Numba compile olayları dinlenerek, boş önbellekle,
      bütün katmanlar + Particles / Pulses + kanal / sector sahneleriyle kontrol edildi: 145 fonksiyon önceden, 0
      sonra). Ölçüm (bu sunucu): ilk açılış pencere 13.0 s / ilk çizgiler 17.1 s (önce 2.6 / 16.6 s ama boş pencere
      + ilk tıklamalarda derleme), sonraki açılışlar 1.2 / 1.3 s. Testler: `tests/test_hardware.py` (12: sahte
      kayıt defteri, laptop Intel / NVIDIA durumu, fingerprint, gerçek alt işlemle OpenGL yokken çökmeme, takılan /
      düşen sorgu, profil hatırlama / yenileme, bozuk profil, yükleme ekranı, açılış, Your computer)
    - ✅ **20.2 Çok çekirdekli hesap** (29 Ekim, her zaman açık, ayar yok): `physics/parallel.py` (iş havuzu: thread
      sayısı − 1, biri pencereye; `PFL_THREADS=1` ile tek çekirdek). (a) Streamline izleme (`level._integrate`,
      zamanın %60–84'ü): 8+ seed'lik gruplar parçalara bölünüp derlenmiş tracer'la (nogil) aynı anda izleniyor;
      birden fazla çekirdekte ileri ve geri yön de aynı anda (`_integrate_both`). (b) Büyük ızgaralar (renk
      bantları, φ, CSV: `field.complex_velocity / complex_potential`, 20 000+ nokta) satır parçalarına bölünüyor.
      Sonuçlar **bit bit aynı**: 21 preset + 25 rastgele sahnede 3457 streamline dizisi, 21 preset × 4 ızgara
      PFL_THREADS=1 ile 4 arasında ve eski koda göre birebir. Ölçüm (bu sunucu: 2 hyper-thread, en fazla ~1.3–1.9×):
      8 elementli sahne 1044 → 734 ms, 600 × 400 ızgara (w + φ) kanal 162 → 93 ms, 8 element 91 → 47 ms. Tahmin
      (her seed'in gerçek süresinden): izleme en uzun streamline'ı beklediği için 4 thread'den sonra doyuyor —
      kullanıcının 16 thread'inde streamline'lar ~1.4–2.5× (kalabalık sahnede en çok), ızgaralar 4–8×; gerçek sayılar
      kullanıcının benchmark'ında. Testler: `tests/test_parallel.py` (9); tüm test suite PFL_THREADS=4 ile de
    - ✅ **20.3 GPU kutusu + OpenGL çizim + Graphics card paneli + Intel → NVIDIA** (29 Ekim): başlıkta **GPU**
      kutusu (+ View → Draw with the graphics card); ilk açılışta kapalı, hatırlanıyor (`gpu/enabled`).
      `PlotCanvas.set_gpu`: plot'un viewport'u çalışırken `PlotGLViewport`'a (QOpenGLWidget, 4× MSAA) ve geri
      değişiyor; öğeler aynı QPainter ile çiziliyor, export'lar etkilenmiyor. Viewport değişince: FullViewportUpdate
      (OpenGL karesi her seferinde baştan çizilir — Minimal'de seçim gibi küçük değişiklikler plot'un geri kalanını
      silerdi), arka plan paleti, `PlotInteraction.viewport_changed` (bırakma, imleç, event filter). Kutu sadece
      OpenGL 2.0+ gerçek karttan geliyorsa açılabilir (`gpu.support`; yazılım OpenGL'de gri + neden). Güvenlik:
      (1) açınca her 1.5 s bakılıyor: OpenGL context yoksa (önce `repaint` denenir) ya da 6 s'de resim
      (`frameSwapped`) gelmezse işlemciye geri dönüş + mesaj; (2) GPU açıkken kilit dosyası
      (`gpu.SessionGuard`, QLockFile): sahibi ölmüş kilit = sürücü çökmesi → sonraki açılış GPU kapalı + mesaj;
      (3) `failed` sinyali kuyruklu (viewport kendi initializeGL'i içinde silinmesin). **Graphics card** paneli
      (sadece GPU açıkken, yüksekliği içeriği kadar): çizen kart (sürücünün kendi söylediği), canlı FPS ve kare
      süresi (`PlotView` → `FrameMeter`), Frame rate: Match screen (QScreen Hz) / 60 / 120 / 144 → animasyon
      timer'ı `gpu.frame_ms` (aşağı yuvarlanır; vsync ekranın Hz'inden fazlasını engeller). GPU kapalıyken 16 ms
      (eski davranış). **Laptop**: kart sürücüsünün söylediği renderer güçlü kart değilse (`hardware.runs_on_weak_card`;
      AMD işlemcinin dahili "Radeon Graphics"i güçlü sayılmıyor, NVIDIA önce) GPU işaretlenince soru: Use NVIDIA and
      restart → HKCU\Software\Microsoft\DirectX\UserGpuPreferences, değer adı = exe (venv'de ayrıca
      `sys._base_executable`), "GpuPreference=2;" (Windows'un diğer girdileri korunuyor), `hardware/reprobe` +
      `gpu/switching` → kapat (kaydet sorusu) → aynı sahne dosyasıyla yeniden başlat → OpenGL yeniden soruluyor →
      kart değişmediyse elle yapma adımları + Open Windows settings (ms-settings:display-advancedgraphics).
      Benchmark: `--gpu`, `--fps-cap`; paint artık iki şekilde ölçülüyor (aynı yol her iki modda): "plot frame"
      (update → boyandı → glFinish) ve "paint (CPU part)". Bu sunucuda OpenGL yazılım (llvmpipe) olduğu için
      karşılaştırma anlamlı değil (kare 6 → 38 ms), ama CPU kısmı her katman açıkken yarıya iniyor (kanal 31.6 →
      16.5 ms): gerçek kartta kazanç bu kısımda. Gerçek sayılar kullanıcının Windows'unda. Testler `tests/test_gpu.py`
      (16): kurallar, sahte kayıt defteri, kilit dosyası, kutu / panel, OpenGL olmayan test platformunda temiz geri
      dönüş, viewport değişiminde fare / bırakma, güçlü kart sorusu + yeniden başlatma sonrası kontrol, kare
      sayacı; Xvfb + Mesa varsa ayrı işlemde gerçek OpenGL resmi normal çizimle piksel piksel (%0.56 fark,
      yumuşatma), seçimden sonra plot'un geri kalanı yerinde.
    - ✅ **20.3b Laptop kartı düzeltmesi** (29 Ekim, kullanıcının ilk Windows denemesinden): Windows ayarında
      `.venv\Scripts\python.exe` "High performance (RTX 3050)" olduğu hâlde OpenGL Intel'de kaldı. Neden: venv'in
      python.exe'si sadece asıl Python'u başlatıyor; asıl Python **Microsoft Store**'dan (WindowsApps), Windows kartı
      işlemin gerçek dosyasına göre seçiyor. Düzeltme: (1) işlemin gerçek dosyası (`hardware.process_image_path`,
      GetModuleFileNameW) da kayıt defterine yazılıyor ve OpenGL sorgusu onu bildiriyor; (2) "Use NVIDIA" seçilince
      ayrıca NVIDIA Optimus'un kendi anahtarı `SHIM_MCCOMPAT=0x800000001` her açılışta grafikten önce ayarlanıyor
      (`gpu.apply_startup_env`, `gpu/optimus`); sorgu işlemi ve yeniden başlatma bunu miras alıyor; (3) Store Python ise
      elle yapma penceresinde not. Hangisinin işe yaradığını bulmak için `scripts/gpu_check.py` (A bugünkü hâl, B
      başlangıçta SHIM, C işlem içinde SHIM, `--write-registry` ile D gerçek dosyaya Windows ayarı). Kullanıcının
      denemesi: terminalde `SHIM_MCCOMPAT=0x800000001` ile açınca panel **NVIDIA GeForce RTX 3050 Laptop GPU** dedi.
      Ayrıca panel "no smoothing" diyordu: `format().samples()` widget'ın frame buffer'ında 0 döndürüyor; gerçek değer
      ilk kareden sonra GL_SAMPLES ile okunuyor (`PlotGLViewport._read_samples`) → 4×.
    - ☐ 20.4 GPU particles / pulses + kalibrasyondan üst sınırlar; aynı script'le karşılaştırma (`--gpu`)
21. ☐ **Kod düzenleme (son sürüm öncesi)**: davranış değişmeden — ölü / tekrar eden kod, isimler, docstring'ler,
    dosya yapısı, uyarılar (pyflakes), çok uzun dosyaların bölünmesi, testlerin süresi, README klasör tablosu.
    Ölçüt: tüm testler + verification aynı sonuç
22. ☐ **Görsel ve metin son kontrolü** (kullanıcı ile): programdaki tüm yazılar (menüler, paneller, dialog'lar,
    tooltip'ler, uyarı mesajları, lejantlar, durum çubuğu) tek bir listede + ekran görüntüsü galerisi; kullanıcı
    beğenmediklerini işaretler / yenisini yazar, ben değiştiririm. Açık kararlar burada: dividing streamline
    rengi, element renkleri, ikonlar, kunduz görünümü
23. ☐ **Kapsamlı rastgele test** (en son kodla): yüzlerce–binlerce rastgele sahne (tüm element tipleri, duvarlar,
    köşeler, kanal, sector flow, uç değerler, üst üste / çok yakın elementler), her biri birkaç zoom / pan'de:
    hata (exception) yok; stagnation point'lerde gerçekten V = 0; streamline'lar boyunca ψ sabit, çizgiler
    kesişmiyor; cisim dolgusu zoom'dan bağımsız; yüzey Cp'si ve kuvvet (Kutta–Joukowski / d'Alembert ile kıyas
    mümkünse); kaydet → aç aynı; figür / CSV export; parçacıklar akışkanda kalıyor. Ayrıca arayüz için rastgele
    kullanıcı işlemleri (ekle, sürükle, sil, undo / redo, katmanlar, tema, preset): çökme yok, undo'dan sonra
    sahne birebir aynı; otomatik kayıttan geri getirme de. Bulunan her hata düzeltilir ve o sahne kalıcı teste
    eklenir; test temiz çıkana kadar baştan
24. ☐ **Faz 5 — Paketleme**: Python gerektirmeyen Windows 10/11 exe (zip içinde klasör), sürüm 1.0, GitHub
    Releases, kurulum dosyası (Inno Setup), Numba önbelleği, .pflow'a çift tıklayınca açılma, (isteğe bağlı)
    komut satırı için konsol exe'si; exe'de Help → Run verification 102 / 102, Python kurulu olmayan temiz bir
    Windows'ta deneme. Yedek plan: kaynak kod + kurulum talimatı / demo kendi bilgisayarından
25. ☐ **Faz 3 — Rapor ve user guide**: 4–6 sayfa rapor (figürler, tablolar, doğrulama Paket V'den; sector
    kuralının açıklaması), user guide (Help → User guide, F1)
26. ☐ **Son kontrol**: ödev metni madde madde, tüm testler, verification, exe tekrar, README, sürüm numarası
27. ☐ **Demo provası**

Belki (askıda — yapılmayacak değil, sıra gelirse / vakit olursa):
- **Dye rake**: çizilen rake'ten pulse'lı boya → streakline; taşınır, döndürülür, kaydedilir
- **Joukowski airfoil**: conformal mapping ile kanat profili, Kutta koşulu → Γ kendiliğinden

Öneriler (28 Ekim, şimdilik alınmadı): ödev metniyle karşılaştırma tablosunun en başta yapılması (26'da yapılacak),
GitHub Actions (Windows'ta testler + otomatik exe), farklı bir bilgisayarda deneme, zip'te SmartScreen notu
(24'te), macOS sürümü.

(Köşeli parantezdeki numaralar 26 Ekim'deki istek listesindeki madde numaralarıdır.)

Bir değişiklik beğenilmezse: her paket ayrı commit → GitHub Desktop → History → commit'e sağ tık →
"Revert changes in commit".
