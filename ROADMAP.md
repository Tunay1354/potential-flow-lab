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
    - ✅ **20.3c Animasyon 23 fps → ekranın hızı** (29 Ekim, kullanıcının Windows ölçümü): kendi ekranında φ çizgileri
      + |V| bantları + yoğun streamline'larla Particles / Pulses 22–23 fps, panel "a frame takes 26–29 ms". Kök
      neden: animasyonda her plot öğesi bir resim olarak saklanıyor (DeviceCoordinateCache), resimler Qt'nin
      QPixmapCache'inde — varsayılan sınır **10 MB**; plot boyunda bir resim 4–12 MB → birkaç katmanla sığmıyor, Qt
      onları atıp **her karede her şeyi yeniden çiziyordu** (GPU'da da, işlemcide de). Düzeltme: animasyon
      başlarken sınır en büyük ekranın 40 plot resmi kadar (128 MB – 1 GB arası; sadece tavan, bellek resimler kadar
      kullanılıyor; `canvas.ensure_pixmap_cache`). Bu sunucuda aynı sahne: plot karesi 21–24 → 4–5 ms (raster),
      27–29 → 4 ms (OpenGL'in CPU kısmı); fps 34–37 → 62 (60 sınırında). Benchmark anim'e kullanıcının görünümü
      eklendi ("lifting cylinder + φ, |V|, dense") ve artık plot'un gerçekten gösterdiği kare sayısı + bir karenin
      çizim süresi yazılıyor (önce timer tik'leri sayılıyordu: gerçek kareleri göstermiyordu).
      Kullanıcının ilk Windows ölçümü (`windows_after_cpu` / `windows_after_gpu`, 16 thread, RTX 3050, 144 Hz):
      plot karesi (her katman) lifting 15.2 → 10.1 ms, kanal 32.5 → 8.3, 8 element 21.4 → 10.7 (CPU kısmı kanal
      30.3 → 5.6); her katmanla zoom kanal 31.0 → 17.4, 8 element 33.3 → 20.6 ms (STUTTER → ok); animasyon
      varsayılan katmanlarla ikisinde de 62 fps (60 sınırı), 8 elementte GPU 48 fps — aynı önbellek taşması.
    - ✅ **20.3d Pulses yavaş + "saçmalayan" streamline'lar** (29 Ekim, kullanıcının ekran görüntüleri): (1) Pulses'ta
      element sürükleyince eski konumun çizgileri ekranda kalıyordu. Yeniden üretildi (sahnenin %3'ü): animasyonda
      resim olarak saklanan bir streamline öğesi yeni veride güncellenmiyordu (Qt'nin kendi geçersiz kılması yetmedi;
      önceden önbellek taşması bunu gizliyordu). Düzeltme: veri değişince (sigPlotChanged / sigImageChanged) öğenin
      resmi atılıyor (`layer.drop_picture`) → fark %0. (2) Pulses 144 sınırında 27 fps, 60'ta 61: timer 6 ms'de bir
      yeni kare çiziyordu, önceki kare daha ekrana çıkmadan; pencere boyamaya zaman bulamıyordu. Kare temposu:
      son kare boyanmadıysa yeni kare çizilmiyor (`TrailItem.shown`, en çok 6 tik bekleme; akış hızı gerçek zamandan
      hesaplandığı için değişmiyor). (3) Pulses / particles çizimi (`kernel.draw_segments`, bir pulse karesinin
      %90'ı: yoğun görünümde 8 ms) tüm çekirdeklerde: resim satır bantlarına bölünüyor (`draw_segments_rows`, nogil),
      sonuç tek çekirdekle bit bit aynı (test). Bu sunucu 4 thread: 8.0 → 4.3 ms; 16 thread'de ~1 ms bekleniyor.
      (4) `parallel.run`: hiçbir çekirdeğin başlamadığı işi çağıran kendisi yapıyor (arka plan hesabı varken animasyon
      karesi kuyrukta beklemiyor). Kullanıcının görünümünü taklit (125 %, 180 streamline, 144 sınır, 4 thread):
      pulses 65 → 77 fps, particles 77 → 101 fps.
      Arkadaşının projesi (laurance18/potential-flow-lab, C++20 + OpenGL 3.3 + Dear ImGui) incelendi: hızı her şeyi
      GPU'nun çizmesinden — particles GPU'da nokta (shader), iz soluklaşması FBO'da bir shader geçişi, dye rake
      ve streamline'lar her karede ImGui polyline (üçgenleri GPU dolduruyor); CPU sadece köşe noktalarını
      hazırlıyor, piksel piksel hiçbir şey çizmiyor. Bizde particles / pulses resmi CPU'da piksel piksel çiziliyor ve
      her karede dokuya yükleniyor. Ayrıca dye rake'te ~9 kaynak var, bizim Pulses'ta görünümdeki tüm streamline'lar
      (~100) yanıyor. Sonuç → 20.4: particles / pulses'ı GPU'da çizmek (VBO + shader, iz için FBO).
    - ✅ **20.4 Particles / Pulses ekran kartında + kalibrasyonlu üst sınır** (29 Ekim; dye rake istenmedi):
      GPU açıkken animasyon resmi işlemcide piksel piksel çizilmiyor: işlemci sadece çizgi parçalarının
      yerini veriyor (`GLFrame` kayıt adımları: clear / fade / segs / pulses), kart çiziyor (`app/canvas/
      gl_animation.py`: her parça bir dikdörtgen, yuvarlak ve yumuşak kenar shader'da `draw_segments` ile aynı
      formülle; instanced çizim, kendi VAO'su; resim bir frame buffer'da, plot'un kendi boyamasında
      `beginNativePainting` ile üstüne). Particles: iz soluklaşması kartta (× keep, sonra 1/255 eksik: soluk
      pikseller gerçekten 0'a iniyor), pan / zoom'da eski resim taşınıyor. Pulses: parçalar karta bir kez gidiyor
      (çizgiler ya da görünüm değişince), her karede sadece zaman; hangi parçanın yandığına shader karar veriyor
      (fract(t − faz) < L, aynı kural). Ölçüm (bu sunucu, işlemci kısmı): pulses karesi 2–8 ms → 0.1 ms,
      particles 1500: 2.1 → 0.7 ms. Doğruluk: gerçek OpenGL'de (Mesa) aynı andaki pulses karesi kartta ve
      işlemcide piksel piksel aynı (renkli piksel sayısı birebir, %0.008 piksel 10/255'ten fazla farklı).
      Kart yapamazsa (OpenGL < 3.3, shader reddi, bir hata) o katman bir sonraki kareden işlemciyle çizer
      (`gpu_broken`); GPU kutusu yeniden açılınca tekrar denenir. Export'lar hep işlemci yolu.
      **Particles → Count üst sınırı**: GPU kapalı 5000; açıkken bu bilgisayarın bir karede ~4 ms'de
      hareket ettirebildiği kadar (`physics.particles.step_ms(20 000)` bir kez ölçülüyor, bilgisayar değişince
      tekrar; 5000'in katı, en çok 100 000; bu sunucu 40 000). Graphics card panelinde yazıyor. Çok particle
      (≥ 10 000) tüm çekirdeklerde hareket ediyor (yeniden doğmayanlar tek çekirdekle birebir aynı; test).
      Kart kapatılınca / daha azına izin veren bilgisayarda açılan sahnede sayı sınıra iniyor.
      Testler (`tests/test_gpu.py`, +5): kayıt adımları ve geri dönüş, sınır + ölçümün hatırlanması, sahne
      açılırken sınır, çok çekirdekte particles, Xvfb'de gerçek OpenGL ile pulses kart = işlemci.
    - ✅ **20.4b Kartın resmi yanlış yerde (125 %)** (29 Ekim, kullanıcının ekran görüntüsü: hız 135 fps ama
      pulses / particles 1.25× büyük, sağ alta kaymış, eksenlerin üstüne taşıyor). Neden: resmin plot'taki yeri
      boyacının dönüşümünden (`combinedTransform`) hesaplanıyordu; ekran kartı boyacısında o dönüşüm ekran ölçeğini
      zaten içeriyor, üstüne bir kez daha çarpılıyordu. Düzeltme: köşeler veri → sahne → viewport (görünümün kendi
      `viewportTransform`'u, mantıksal piksel) yoluyla. Xvfb'de QT_SCALE_FACTOR=1.25 ile yeniden üretildi (%4.85
      piksel farklı → %0.002); 1, 1.25, 1.5'te kart = işlemci. Test artık 1 ve 1.25'te çalışıyor (eski kodda 1.25 düşüyor).
    - ✅ **20.5 Benchmark: sınırlar + tek komut** (29 Ekim, kullanıcının isteği: "daha kapsamlı, sınırları zorlayan,
      çok uzatmadan"): yeni bölüm `limits` — 16 elementli sahne (`stress_scene`: her tür element, açılı akış), en
      yoğun streamline'lar, tüm katmanlar: hesap (streamlines, her şey birden), pan / zoom / element sürükleme,
      slider'ın izin verdiği en çok particle ve en uzun / sık pulses (kartla: ekranın Hz'inde), PNG 4× ve MP4 2×.
      `--full`: her şey bir kez işlemciyle, sonra çizim / etkileşim / animasyon / sınırlar bir kez daha kartla;
      tek JSON (bölümler "[GPU]" ekli), raporda bu bilgisayarın özeti. Programın kendisi değişmedi.
    - ✅ **20.5b Laptop'ta NVIDIA'yı garanti etmek** (29 Ekim, `windows_full.json`: [GPU] bölümü Intel UHD ile koştu,
      oysa aynı bilgisayarın OpenGL sorgusu RTX 3050 diyordu). Neden: NVIDIA Optimus anahtarı (SHIM_MCCOMPAT)
      ancak işlem BAŞLARKEN ortamda varsa işe yarıyor; program içinde sonradan koymak (20.3b) yetmedi. Düzeltme:
      `gpu.relaunch_on_strong_card` — Windows'ta NVIDIA kartı varsa ve kullanıcı "Use NVIDIA" dediyse (benchmark
      --gpu / --full'da her zaman, `--integrated` hariç) program kendini bir kez daha bu anahtarla başlatıp
      bekliyor (çıkış kodu aynen; `PFL_STRONG_CARD` ile asla iki kez). Benchmark çizen kart güçlü kart değilse
      uyarı yazıyor. Test: relaunch kuralları (sahte Windows / kart listesi).
    - ✅ **20.6 Kullanıcının tam ölçümü, gerçek RTX 3050 ile** (30 Ekim 00:09, `benchmarks/windows_full_nvidia.json`;
      i7-11800H 16 thread, Intel UHD + RTX 3050 Laptop, 144 Hz, 125 %). 20.5b doğrulandı: [GPU] kısmı NVIDIA'da
      (4.6.0 NVIDIA 591.44, 4× smoothing). Sayılar (işlemci → NVIDIA; parantezde aynı ölçüm Intel UHD'de):
      plot karesi her katmanla: lifting 15.7 → 9.3 ms, kanal 34.0 → 8.2 (20.8), 8 element 22.1 → 11.7; varsayılan
      katmanla lifting 17.3 → 5.1. 16 elementli sahnede (en yoğun, tüm katmanlar) pan p95 116 → 67 ms, zoom
      304 → 71, sürükleme 62 → 35. Animasyon (60 sınırı) her durumda 62 fps; işlemci kısmı pulses 2.1–3.6 → 0.1 ms,
      particles 2.3–3.3 → 0.5–1.3 ms; 50 000 particle 62 fps. Sınırda (ekranın Hz'i): pulses 52 → **139 fps**,
      50 000 particle 65 fps. Hesap (çok çekirdek): 8 element streamlines 795 → 535 ms (ölçüm öncesine göre).
      Kalan zayıf noktalar (sonraki optimizasyon adayları): (1) ağır sahnenin MP4 2× export'u 30.7 s, PNG 4× 2.4 s;
      (2) açılış: soğuk 13.8 → 18.2 s, sıcak 2.1 → 3.0 s (her şeyin pencereden önce hazırlanmasının bedeli);
      (3) ağır sahnede pan / zoom p95 ~70 ms (NVIDIA); (4) element eklemeye tepki ~380 ms; (5) 16 element en yoğun
      streamline hesabı 0.64 s, her şey birden 1.2 s.
20.7 ▶ **Kullanıcının 21 maddelik listesi** (30 Ekim 01:12; üç pakette, her biri ayrı commit):
    - ✅ **20.7A Tur + kunduz** (madde 3, 4, 5, 6, 7, 8, 18, 19): sağ ok = ileri, sol ok / ‹ Back = geri (ilk
      adımın temizliği tekrarlanmaz; yapılmış iş "Done already" + Next); uniform'a açı verildiyse doublet
      penceresindeki uyarıyı kunduz açıklıyor (δ = α, ters μ'de α + 180°), düzenlemede uyarı yeniden çıkarsa kısa
      hatırlatma (`validation.doublet_misalignment`, uyarıyla aynı test); Add / Edit pencereleri turda sadece
      kendi adımlarında açılıyor (palette tıklaması, drop, menü, klavye — `tour.may_add / may_edit`); Density
      adımı slider bırakılınca geçiyor; plotta element varken tur önce soruyor (Save first / Clear and start /
      Cancel; eskiden Qt'nin "Unsaved changes" kutusunda Cancel denince tur dolu plotta devam ediyordu); Help'ten
      sonra GPU kutusu adımı (19 adım); P artık çalışıyor (aynı kısayol Edit ve Help menüsündeki iki ayrı
      action'daydı → Qt "ambiguous" deyip hiçbirini çalıştırmıyordu) ve kunduzun menüsünü açıyor / kapatıyor;
      "Nothing, thanks" → "I'm here if you need me". Testler: oklar ve geri, slider bırakma, palette kilidi,
      uyarı ipucu, GPU adımı, tur öncesi soru, P.
    - ✅ **20.7B Açılış, düzen, ızgara, Surface pressure paneli, User guide, Sign conventions** (madde 1, 2, 14, 15,
      16, 20, 21): ilk açılış notu artık ilerleme çubuğunun hemen üstünde vurgulu bir kutu (geçen saniyeyle) ve
      sadece ilk açılışta (`startup.is_first_start`: program sürümü + Python + `physics/` dosyalarının imzası
      değiştiyse ya da donanım profili yoksa; ısınma bitince `mark_prepared`). Program boş plotla açılıyor;
      varsayılan düzende Elements 260 px (Qt'nin `resizeDocks`'u payı kendi dağıttığı için "iste, bak, düzelt":
      `_resize_dock`), düzen sürümü 2 (eski kayıtlı düzen bir kez yeni varsayılana döner); Reset layout sahneye
      dokunmuyor. Layers → Background grid (hatırlanıyor, export'lar da öyle). Surface pressure paneli solda 330 px
      açılıyor, son genişliği hatırlanıyor (240 px – pencerenin %45'i dışı = varsayılan), Reset layout varsayılana
      döndürüyor (panel kapalıyken de), katmanın tiki kalkınca kapanıyor. Help → User guide (F1): 14 bölüm, arama,
      kısayol tablosu canlı, "Open in browser" (tek sayfa HTML). Help → Sign conventions: her element için çizimli
      kart (α, m, Γ, δ, β / θ₁ / θ₂, θw ve akışkan tarafı), üstte temel tanımlar, altta Cp ve kuvvetler.
      Testler `MainWindow.START_SCENE` ile eskisi gibi lifting cylinder'la başlıyor (conftest); gerçek açılış
      ayrı testte. Yeni testler: boş açılış + Elements yüksekliği, panel genişliği / reset / tik, ızgara, F1 + arama,
      Sign conventions kartları, ilk açılış imzası.
    - ✅ **20.7C GPU** (madde 9 cevap, 10, 11, 12, 13, 17): GPU kutusu iki yönde de programı yeniden başlatıyor
      ("Restart now / Cancel"; `app/restart.py`: sahne dosyası + durum JSON'u veri klasörüne, yeni program
      `--resume` ile açıp siliyor; dosya adı, kaydedilmemiş değişiklik, görünüm, ayarlar, katmanlar, mod, seçim, açık
      panel aynen; kaydet sorusu yok; yeni program başlatılamazsa hiçbir şey değişmiyor). Kaldırınca "bir şey
      değişmiyordu" çünkü OpenGL bir kez giren pencere öyle kalıyor ve NVIDIA ortamı süreçte kalıyordu; artık temiz
      bir işlemci süreci. NVIDIA laptop'ta kutu işaretliyse her açılışta NVIDIA anahtarıyla yeniden başlama ("Use
      NVIDIA" sorusu kalktı; yine Intel'deyse bir kez elle nasıl yapılacağı). Graphics card dock'u kaldırıldı: başlıktaki
      okla açılan, sağ tarafın üstüne binen panel (`GpuPanel`, CPU'da da: FPS, frame rate — mod başına ayrı, işlemcide
      60), "WITH THE GRAPHICS CARD" bölümü GPU kapalıyken gri. GPU + Higher limits: Density 10 → 15 (2 → 3), Particles
      ölçülen (≤ 100 000), Speed 10 → 13, Trail 10 → 14, Pulse speed 13, length 14, spacing 14 (`gpu.GPU_LIMITS`);
      `LimitSlider` işlemci sınırında kısa çizgi; GPU kapalıyken değerler sınıra iniyor (`_limit_sliders`, açılan
      sahnelerde de). Madde 17 (GPU'da eklenen elementin sembolü görünmüyordu, yeniden başlatınca düzeldi): bu sunucuda
      (Mesa, 100 % / 125 %, Static / Particles / Pulses, açılışta / sonradan açılan GPU) tekrar edilemedi; muhtemel
      neden çalışırken OpenGL'e geçen pencere (şimdi GPU hep açılışta başlıyor = onun "yeniden başlatınca düzeldi"
      durumu) + güvenlik ağı: sahne her değişince GPU'da tüm plot yeniden çiziliyor (`gpu_redraw`). Windows'ta
      kontrol edilecek. Düzen sürümü 3 (dock_gpu yok). Testler: yeniden başlatma (iptal, başlatılamama, her şeyin geri
      gelmesi), kaldırınca da yeniden başlatma, panel (taşınmış panellerde de sağda), sınırlar + çizgi + açılan
      sahnede indirme, `--resume` ayrıştırma.
    - ✅ **20.7D Windows denemesinden düzeltmeler** (30 Ekim 02:12, ekran görüntüleriyle): (1) Surface pressure paneli
      taşınamıyordu: Qt sürüklerken paneli gizleyip gösteriyor, 20.7B'nin "açılınca genişliğini ayarla / yasak yerde
      ise sola koy" kodu her seferinde onu sola geri koyuyordu → sürüklenirken (yüzer / sol tuş basılı) hiçbir şey
      yapılmıyor, genişlik sadece gerçek açılışta (test: başlıktan sağa sürükle, kapat-aç, sonraki açılış). (2) Turda
      geri gidince o adımda yapılan geri alınıyor (adım başındaki undo noktasına kadar undo, Move → Select,
      Particles → Static, slider eski değerine); adım yeniden "your turn". (3) Doublet uyarı ipucu: açılar yuvarlak
      (1.029e-07 → 0), "Orientation δ" alan adıyla, anlaşılır cümle; tekrarında kısa ("pick any angle you like and go
      on. With δ = 0° it goes away"). (4) GPU kutusu soru sormadan yeniden başlatıyor. (5) Slider sınır çizgisi: 3 px
      (ekran pikseline oturtulmuş: hepsi aynı kalınlık), 14 px boy, ceviz rengi (tema `logo_dot`), tutamacın altında.
      (6) Graphics card paneli okun altından sarkan kart: çentik oku gösteriyor, mürekkep çerçeve + sert gölge
      (kunduz balonu / çizim kartı görünümü), plank'ın kenarına değiyor.
    - ✅ **20.7E Kunduz ve User guide** (30 Ekim 02:36): doublet uyarısının açıklaması bir kez çıktıysa silinmiyor (açı
      düzelince sonuna "That's it: the warning is gone." ekleniyor, yalnız yeni kelimeler yazılıyor); düzenleme adımında
      değiştirmeden Apply da ilerletiyor; User guide aramasında Enter artık "Open in browser"ı tetiklemiyor (butonlar
      autoDefault değil) ve o buton "Save as web page…" oldu (dosyayı kullanıcının seçtiği yere yazıp açıyor: Microsoft
      Store Python'unda programın veri klasörü tarayıcıya kapalı — "açılmayan sayfa" bundandı; verification raporunun
      "Open full report"u da aynı klasörü kullanıyor: exe'de sorun olmaz, 24'te kontrol); kunduz için güvenlik ağı:
      plotta (glass / flow / bored / pulse / run / vanish / gone) 15 s'den uzun kalırsa "rescue" cümlesi + rafına zıplama.
    - ✅ **20.7F Kunduzun konuşmaları** (30 Ekim 02:49, kullanıcının onayıyla): sohbette önerilen tüm cümleler eklendi
      (78 durum, ~570 cümle; tekrar önleme: son söylenenlerin yarısı); yeni durumlar `Beaver.remark` ile — sadece
      rafındayken, konuşmuyorken, en çok 20 s'de bir ve olasılıkla (undo / redo %12, silme %20, ekleme %35, silindir
      %80 …: `lines.REMARK_CHANCE`), ciddi çalışmayı bölmesin diye. Pencere bildiriyor: element_added (sink ayrı),
      deleted, cleared, undo, redo, preset, exported (figure / animation / data), theme, gpu (yeniden başlatmadan
      sonra), scene (`scene_shape`: cylinder / lifting, 8+ element crowded); saat başı long_session; açılışta bazen
      günün saatine göre selam. Testler: sayılar, tekrar önleme, olasılık + 20 s aralık, sessiz undo, şekiller.
    - ✅ **20.7G Adı Flowy + zoom sorunları + zoom sınırları** (31 Ekim, kullanıcının iki ekran görüntüsü ve isteğiyle):
      - **İsim**: pencere başlığı, header (FLOWY + altında "POTENTIAL FLOW LAB", REV sağda), açılış ekranı, About,
        export başlıkları, rapor, user guide, tur, scene dosyası hata metni, exe adı → **Flowy**
        (`app_info.APP_NAME`). Ayarlar / veri klasörü eski adla kalır (`APP_ID = "Potential Flow Lab"`): ayarlar,
        son dosyalar, otomatik kayıtlar kaybolmaz.
      - **Çok uzak zoom'da çizgilerin kesilmesi**: streamline önbelleği "bu kadar yavaşsa stagnation point" eşiğini
        (`v_min`) ilk görünümden alıp her zoom seviyesinde kullanıyordu; uzakta akış daha yavaş → her çizgi hemen
        bitiyordu. Artık her seviye kendi eşiğini ilk bölgesinden bulur (`streamlines/cache.py`). Vortex + source,
        4 → 4·10⁵ → 4·10⁻⁴ yarı genişlik: çizgiler her seferinde görünümün tamamını kaplıyor.
      - **GPU'da çok yakın zoom'da kalın çizgiler**: Qt'nin OpenGL çizicisi bir öğenin kendi koordinatlarını
        ~10⁴ px / birimden fazla büyütünce kalemi kalınlaştırıyor (işlemcide yok). Çizgiler artık görünüm
        boyutunda yerel koordinatlarda (`app/canvas/scaled_curve.py`, `ScaledCurve`: x' = (x − cx) / s, 1 birim ≈
        1 px; zoom 16× değişince yeniden), ızgara ekran pikselinde (`grid_item.PaperGridItem`). Xvfb + Mesa: yarı
        genişlik 10⁻³'te GPU ile normal çizim farkı %82.6 → %0 (test: `test_opengl_lines_stay_thin_far_zoomed_in`).
      - **Zoom sınırları**: kullanıcının tekerlek / sürüklemesi Fit genişliğinin 10⁴ katı yakın / uzak ile sınırlı
        (`canvas.ZOOM_RANGE`, pyqtgraph `setLimits`, aspect lock korunur); sınırlar sahneyle değişir. Program /
        dosya / View range ile verilen görünüm kesilmez (sınırlar onu kapsayacak kadar genişler). Sınıra her
        varışta bir kez `zoom_limit` → status bar + kunduz (`zoom_limit_in` / `zoom_limit_out`, 12'şer espri, %50,
        20 s kuralı geçerli).
      - **View range kutuları**: ±10 000 ve 2 ondalık yerine ±10¹²; ondalık sayısı görünüm genişliğine göre
        (binde biri görünür, 2–8), çok büyük / küçükte `1.5e-05` biçimi, yazarken de (virgül de olur)
        (`panels.ViewSpinBox`). Testler: `tests/test_zoom.py` (10 test).
      - Full test sırasında bulunan eski bir hata: Newton'un bir başlangıç noktası tam bir vortex'in merkezine düşünce (merkeze simetrik görünüm) derlenmiş kernel sıfıra bölüyordu → tekil noktadaki başlangıç noktası atlanır (`kernel._at_singularity`; test: `test_stagnation`).
    - ✅ **20.7H Uzak / yakın zoom'da fanlar, çizilmeyen çizgiler, sınırda kayma, Fit** (1 Kasım, kullanıcının
      raporu: hızlı zoom'da sınıra gelince fanlar çalışıyor, çizgiler çok geç geliyor; GPU'da daha kötü; sınırda
      tekerlek ekranı kaydırıyor; sınırdan Fit'e basınca yine yavaş). Ölçüm (`lifting cylinder`, hızlı tekerlek,
      bu 2 çekirdekli sunucu) dört ayrı kök neden gösterdi:
      - **Kök neden 1 — uzak zoom'da tek hesap 18–66 s**: stagnation point'in cisim içinde mi olduğunu anlamak için
        etrafına atılan test çizgileri kendi küçük adımıyla, görünümün 3 katı kutuda (8 000 genişlikte 24 000)
        izleniyordu → milyonlarca adım. Artık bu kutu görünüm sahneden çok büyükse sahnenin (tekil noktalar,
        stagnation point'ler, cisim kutuları) 20 katıyla sınırlı (`stagnation._probe_region`,
        `PROBE_REGION_SCENES`); normal görünümlerde hiçbir şey değişmiyor. 8 000 genişlik 18.2 → 0.5 s, 20 000
        23.5 → 0.5 s. Tüm preset'lerde 15 zoom adımı dışa / içe: en kötü tek hesap 1.6 s (önce 66 s).
      - **Kök neden 2 — sınırda kayma**: sınırdayken tekerlek hâlâ zoom istiyordu; pyqtgraph aralığı istenen
        aralığın ortasına göre (fareye doğru kaymış) kesiyordu → her tık görünümü yana itip yeni hesap başlatıyordu.
        `PlotViewBox.scaleBy` artık katsayıyı sınıra tam varacak kadar kesiyor (farenin altındaki nokta yerinde),
        sınırda bir tık hiçbir şey yapmıyor. 30 fazla tık: kayma 1.25 görünüm → 0, hesap 27 → 0.
      - **Kök neden 3 — hızlı zoom'da geç çizgiler**: arka plandaki hesap sadece sahne değişince iptal oluyordu;
        artık bakılmayan bir aralık seviyesinin hesabı, en yeni görünüm başka seviye isteyince bırakılıyor
        (`StreamlineLayer._job_level / _wanted_level`; yarım kalan alan `extend` içinde geri alınıyor, ilk
        tohumlar da). Zoom in'de iş sayısı 72 → 17, hızlı zoom bitince çizgiler hemen orada.
      - **Kök neden 4 — tüm katmanlar açıkken arayüz 1–3.6 s donuyordu** (Solid bodies, GUI thread'inde):
        (a) yakın zoom'da sahnenin dividing streamline'larının binlerce hücre uzunluğundaki parçaları hücre hücre
        örnekleniyordu (11 milyon örnek) → artık sadece ızgaranın içine düşen kısım, birebir aynı hücreler
        (`bodies._clip_segments`, Liang–Barsky; 3000 rastgele denemede fark 0; uzun çizgi 8.7 s → 2 ms);
        (b) yakın zoom'da akışkanın nereden geldiği görünümün küçücük adımıyla tüm cismin kutusunda izleniyordu →
        aşamalı izleme (`stagnation._trace_staged`: 3× bölge, sonra her aşama 8× kutu ve 8× adım; "çok yavaş"
        eşiği tek izlemedeki gibi tüm kutudan). Normal görünümlerde tek aşama = eskisi. Kontrol: 21 preset +
        25 rastgele sahnede 30×, 300×, 3000× yakın 276 görünümde cisim haritası eskisiyle **birebir aynı**,
        süre 60.5 → 1.9 s.
      - Sonuç (her katman açık, hızlı tekerlekle sınıra kadar): zoom out 21.0 → 7.4 s, en uzun donma 2.4 → 0.5 s;
        zoom in 18.9 → 7.1 s, 3.6 → 0.4 s; sınırdan Fit 4.1 → 0.8 s. Varsayılan katmanlarla Fit 0.1–0.2 s.
        GPU modu (bu sunucuda yazılım OpenGL) aynı davranış. Kalan: φ / |V| / Solid bodies hâlâ GUI thread'inde
        hesaplanıyor (bu sunucuda ~0.3–0.5 s bir adım) → istenirse arka plana alınabilir.
      - Testler (`tests/test_zoom.py`, +8): sınırda tekerlek görünümü kıpırdatmıyor, sınıra fare etrafında tam
        varış, uzak görünümde stagnation point'ler hızlı ve aynı, probe bölgesi kuralı, aşamalı izleme = tek
        izleme (bilinen her noktada), bariyer örneklemesi = eskisi, seviye değişince iş bırakma.
        Ayrıca: `test_he_reacts_to_saving_and_verification` bazen düşüyordu (source eklemek %35 ihtimalle kunduzun
        "A source!" yorumunu çıkarıyor, "Saved!" onun arkasında bekliyordu) → balon eklemeden sonra temizleniyor.
21. ▶ **Kod düzenleme (son sürüm öncesi)**: davranış değişmeden — ölü / tekrar eden kod, isimler, docstring'ler,
    dosya yapısı, uyarılar (pyflakes), çok uzun dosyaların bölünmesi, testlerin süresi, README klasör tablosu.
    Ölçüt: tüm testler + verification aynı sonuç. Her dosya tek tek, 13 pakette (her biri ayrı commit, arada
    kullanıcı dener); her şey exe'li son hal düşünülerek:
    1 kök ve yapı · 2 fizik çekirdeği (kitap / defter / proje dosyasıyla karşılaştırma) · 3 hesap motoru · 4 fizik
    analiz · 5 doğrulama ve model · 6 plot 1 · 7 plot 2 · 8 ana pencere · 9 paneller ve görünüm · 10 export ve
    araçlar · 11 sistem · 12 kunduz · 13 son tur (scripts, conftest, README / CLAUDE.md inceltme, pyflakes).
    Not edilen hatalar (sırası gelince): GPU + Pulses + uç zoom → Fit = çökme (7); GPU'da plotun sağ kenarında
    çift çizgi (9); Store Python'da Help → Open log folder açılmıyor, GPU çökmesi log'a not düşmüyor (11).
    - ✅ **21.1 Kök ve yapı** (1 Kasım): programın adı artık sadece `app_info.py`'de (pencere, header, yükleme
      ekranı, About, kayıtlı dosya, raporlar, user guide, tur, exe, ayar klasörü — kodda elle yazılmış ~15 "Flowy"
      `APP_NAME`'e bağlandı); "Potential Flow Lab" her yerden kalktı: ayar / veri klasörü `IZTECH/Flowy` (eski
      ayarlar bir kez sıfırdan: düzen, donanım profili, tur sorusu), alt başlık "2D POTENTIAL FLOW", log
      `flowy.log`. Dosya etiketi program adından bağımsız `"pflow-scene"` (eski etiketli dosyalar açılıyor; test),
      21 preset yeni etiketle yeniden yazıldı (içerik birebir aynı). Exe spec'i `packaging/build_exe.spec` (exe adı
      `APP_NAME`'den). Kullanılmayan Pixelify Sans fontu ve yerini son tam ölçümün aldığı 6 benchmark dosyası
      silindi (sayıları bu dosyada). `main.py` sadeleşti (`run_window`, `detect_hardware`), davranış aynı.
    - ✅ **21.2 Fizik çekirdeği** (1 Kasım; `physics/base, registry, elements/*, field, images, validation,
      diagnostics` + testleri, satır satır): bütün formüller defterle (ve kitapla) karşılaştırıldı — uniform
      `F = V∞ e^{−iα} z`, source `(m/2π) log z`, vortex `−i(Γ/2π) log z` (Γ > 0 ccw), doublet `μ/z` (μ = mε/π, silindir
      a = √(μ/V∞)), sector `V zⁿ` (n = π/β; Vr, Vθ), image kuralları (source aynı m, vortex −Γ, doublet δ* = 2θw − δ),
      kanal satırları (cot / csc²): hepsi doğru, fizik değişmedi. Defterde bir işaret farkı bulundu: vortex tanımında
      Γ > 0 ccw (F = −iΓ/2π log z), dönen silindir örneğinde ise + iΓ/2π log z (Anderson gibi Γ > 0 clockwise) → program
      tek kural kullanıyor (ccw, ödevdeki "signed circulation"); Sign conventions'a "Rotating cylinder" satırı eklendi
      (sin θs = Γ/4πV∞a burada, notlarda −Γ/4πV∞a, L′ = ρV∞Γ). Vortex kartında u_θ → V_θ (defterdeki gibi). User guide'a
      ödevin istediği açıklama eklendi: duvarlar (image, 180°/k, kanal) ve sector flow'un sınırlarının diğer
      elementlerle ilişkisi. Ölü kod silindi: `scene_is_valid`, `element_from_dict` / `from_dict`, `with_defaults`,
      `ImageSystem.levels`, kullanılmayan import; testler programın gerçek yolunu kullanıyor (sahne dosyası kaydet →
      aç) ve sınıf varsayılanlarının PARAMS varsayılanlarıyla aynı olduğunu da kontrol ediyor.
    - ✅ **21.3 Hesap motoru** (1 Kasım; `kernel, warmup, parallel, streamlines/*`, satır satır): 26 Ekim'den beri
      kapalı duran "kaba seviyenin çizgilerini ince seviyede tutma" özelliği (`COARSE_LEVELS`, `set_base`,
      `_yield_to_fresh_base`, `_refine`, ~110 satır, kaynaklı sahnelerde boşluk bıraktığı için hiç açılmadı) ve sadece
      testlerin kullandığı `fade_pieces` / `fade_piece_lists` silindi; `streamlines/__init__` sadece kullanılan şeyleri
      dışarı veriyor; eski dosya adlarına atıflar, Numba önbelleğinin yeri (exe'de %LOCALAPPDATA%\numba) açıklamada.
      Kontrol: değişiklikten önce / sonra 21 preset + 12 rastgele sahne × 5 görünüm (kaydırma, yakın, uzak, çok yakın)
      = 186 görüntüde çizgiler, uç solmaları, oklar, stagnation point'ler, dividing streamline'lar **birebir aynı**
      (tek çekirdek, 3 çekirdek; Numba'sız yol 42 görüntüde aynı). Süre aynı (~25–29 s, ölçüm farkı içinde).
      Hızlandırma fırsatı aranmadı / gerek görülmedi: motor derlenmiş ve çok çekirdekli.
    - ✅ **21.4 Fizik analiz** (1 Kasım; `stagnation, bodies, surface, particles`, satır satır): `stagnation.py` (810
      satır) ikiye ayrıldı — stagnation point'ler + dividing streamline'lar `stagnation.py`'de (450), "akışkan nereden
      geliyor" (= cismin tanımı: `trace_origin` / `trace_ends`, aşamalı izleme, `open_elements`, `body_size`,
      `bodies_box`, `doublet_alignment`) yeni `physics/origin.py`'de (380). Ölü kod: programda hiç kullanılmayan
      `find_bodies` / `Body` / `_chain` / `body_mask` (Surface pressure'ın `body_surfaces`'ı yerini almıştı; testler
      ona geçti, kontroller aynı), `scene_reference_speed`, `_first_x`, ikinci `_runs` kopyası; "Paket S" gibi Türkçe
      kalıntılar. Formüller defterle karşılaştırıldı: silindir Cp = 1 − (2 sin θ − Γ/2πaV∞)² (Γ = 0: 1 − 4 sin²θ),
      basınç integrali F′ = −∮ p n ds, Kutta–Joukowski −ρV∞Γ (ccw Γ; defterde clockwise Γ ile ρV∞Γ), d'Alembert 0 —
      doğru. Kontrol: önce / sonra 21 preset + 14 rastgele sahne × 5 görünüm (normal, yakın, uzak, 50× yakın, 300× uzak)
      = 1155 kalem (stagnation point'ler, dividing / inner çizgiler, cisim haritaları, duvar ve cisim yüzeyleri, Cp,
      kuvvetler, particles, pulse süreleri) **birebir aynı**; streamline motorunun 186 görüntüsü de aynı.
    - ✅ **21.5 Doğrulama + model** (1 Kasım; `verification, program_checks, diagnostics, model/*`): ödevin 5 minimum
      verification case'i tek tek ödev metniyle karşılaştırıldı — hepsi var (α = 0° / 45° uniform, source / sink /
      vortex işaretleri, silindir + lifting cylinder, duvarda V·n = 0, kaydet → aç = aynı liste ve aynı streamline'lar).
      İşaret dili tek: programda Γ > 0 ccw; dersin örneği clockwise Γ_cw ile yazıldığı için tablo artık "L′ = ρ V∞ Γ_cw"
      ve "sin θ = −Γ_cw/(4πV∞a)" diyor (önce "Γ" yazıyordu, ccw Γ ile karışıyordu); L' → L′, "U + doublet" → "uniform
      + doublet". Hata: `program_checks._cylinder_rows` eksenini akışa çevirmemiş bir doublet'te (δ ≠ α) kapalı cisim
      bulamayınca ValueError atıyordu → böyle sahneler "silindir değil" sayılıyor (yeni test). Temizlik: "Paket V",
      "Phase 2c", "2b" kalıntıları, tekrarlanan duvar normal-hız kodu tek fonksiyonda (`_largest_vn`), anlamsız
      değişken adları (a_, b_, hh, s_), `scene_file`'daki gereksiz yeniden atama. Kontrol: tablonun 75 sayısı (analitik,
      sayısal, tolerans) önce / sonra **birebir aynı**.
    - ✅ **21.6 Plot 1** (1 Kasım; `app/canvas/` canvas, layer, interaction, bar, settings, legend, grid, scaled_curve,
      arrows, streamline / stagnation / field / element layer'ları, contours; `geometry.py`, `scene.py`): kullanılmayan
      `CanvasBar.message` sinyali, `ArrowsItem.count()`, sadece testlerin kullandığı `PlotCanvas.set_animated`
      (testler `set_view_mode("particles")`) silindi; zoom sınırı hesabı tek yerde (`scene_zoom_limits`); palette →
      plot sürükleme formatındaki eski isim ("potential-flow") → "application/x-pflow-element"; yanlış / eski
      açıklamalar (dosya listesi, "ileride surface renkleri", "açılıştaki sahne", "his report of …" gibi tarih
      notları — fizik dosyalarındakiler de) düzeltildi. Kontrol: 21 preset × 3 katman seti (varsayılan; φ + |V| +
      dividing; Cp + Solid bodies + Surface pressure) × açık / koyu tema = 126 plot görüntüsü önce / sonra
      **piksel piksel aynı** (scratchpad check/plot_snapshot.py).
    - ✅ **21.7 Plot 2** (1 Kasım; `animation_layer, particle_layer, pulse_layer, gl_animation, gl_viewport, body_layer,
      surface_layer`): **Hata (onun bildirdiği çökme): Pulses + aşırı zoom in / out + Fit → program çöküyordu.**
      Sebep (burada yeniden üretildi): Pulses çizilen streamline'ları ~2 piksellik parçalara böler; Fit'ten hemen
      sonra çizilen çizgiler hâlâ uzak görünüşündü ve yeni görünüşün piksel boyuyla bölününce 279 milyon parça
      (onlarca GB) çıktı. GPU'ya özel değil (GPU'da log'da traceback yoktu). Düzeltme: sadece görünüşün yakınından
      (görünüş + her yanda bir görünüş boyu) geçen çizgiler bölünüyor; yine de MAX_PIECES (3 milyon; normalde
      ≤ ~300 000) aşılırsa o çizgiler başka bir zoom'undur — yenileri gelene kadar pulse çizilmez (kesirli bir an).
      Yeni test. Kontrol: 21 preset × 3 görünüşte pulse parçaları önce / sonra **birebir aynı**; çökme senaryosu
      (hızlı tekerle iki sınıra, sonra Fit; GPU'lu ve GPU'suz) artık en çok ~85 000 parça, ~500 MB. Temizlik: iki
      kopya arka plan iş sınıfı → `layer.BackgroundJob`; `body_layer`'da sınıfın altındaki sabit yukarı, başlatılmamış
      `_result`; tarih notları; `logging` içeriden başa. 126 plot görüntüsü yine piksel piksel aynı.
    - ✅ **21.8 Ana pencere** (1 Kasım; `main_window.py`, `app/window/*`, `restart.py`, `recovery.py`, `shortcuts.py`,
      `recent_files.py`): **Hata:** çökme sonrası "Restore" ile gelen sahnede slider sınırı uygulanmıyordu (GPU'yla
      kaydedilmiş 50 000 particle, GPU'suz modda da 50 000 kalıyordu; dosya açarken yapılıyordu) → görünüş + ayarlar
      tek fonksiyonda (`_apply_view_and_settings`), ikisi de sınırı uyguluyor (yeni test; eski kodda başarısız).
      Restart'ın exe'de doğru çalıştığı kontrol edildi (exe kendini, kaynak `python main.py`'yi başlatır). Temizlik:
      eski ad `_limit_particles` → `_limit_sliders` (ve gereksiz çift koşul), `main_window`'daki
      `setup_application` yeniden dışa verme kalktı (herkes `app.startup`'tan alıyor), çelişen / eski yorumlar
      ("ileride kunduz", "no floating" + "nested"), tarih notu, tekrarlanan logger, fonksiyon içi import'lar,
      import sırası, ayar yolunun eski hali (`IZTECH` → `IZTECH\<APP_NAME>`).
    - ✅ **21.9 Paneller / theme / chrome** (1 Kasım; `panels, theme, chrome/*, surface_panel, gpu_panel,
      conventions_dialog, dialogs, element_specs, icons`): **Hata (onun bildirdiği): GPU açıkken plot'un sağ
      kenarında kalın bir iç çizgi.** Muhtemel sebep: bir OpenGL karesi öncekinden hiçbir şey tutmaz ve 125 %'te
      sahnenin arka planı (mantıksal piksel) son cihaz piksel sütununu boş bırakabilir; yumuşatma onu orada ne varsa
      onunla karıştırır → çerçevenin yanında koyu bir sütun (işlemci görünümünde aynı şey `autoFillBackground` ile
      çözülmüştü). Düzeltme: `PlotView.drawBackground` GPU'dayken önce bütün kareyi plot rengiyle doldurur. Burada
      (Xvfb + yazılımsal OpenGL, QT_SCALE_FACTOR 1.25, birkaç pencere genişliği) çizgi zaten görünmüyordu → Windows'ta
      onun denemesi gerek. Temizlik: "Paket S", "kunduz ileride" gibi eski notlar, kullanılmayan renk `plot_grid`,
      7 dosyada fonksiyon içi import'lar başa (chrome → canvas importu bilerek içeride: chrome açılış ekranında
      yüklenir, açılış ekranı hâlâ pyqtgraph / physics / numba yüklemeden açılıyor — kontrol edildi), sınıfın
      altındaki sabit, boş satırlar. Kontrol: pencerenin tamamı açık / koyu temada önce / sonra aynı (sadece durum
      çubuğundaki ms sayısı farklı), 126 plot görüntüsü piksel piksel aynı.
    - ✅ **21.10 Export / cli / verification dialog** (1 Kasım; `app/export/*`, `app/cli/*`, `verification_dialog.py`;
      `paths.py`'ye iki yardımcı): **Hata (onun bildirdiği): Microsoft Store Python'da "Open full report" / "Open
      folder" (ve Help → Open log folder) açılmıyordu.** Store Python paketli bir uygulama gibi çalışır: %LOCALAPPDATA%
      altına yazdığı her şey aslında %LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.x_…\LocalCache\Local\…
      altına gider; o yolu sadece program görür, tarayıcı / Gezgin göremez. Düzeltme: `paths.outside_path` dosyayı
      açmadan önce gerçek yolu bulur (Store paketinin adı `sys.base_prefix`'ten; başka Python / exe / başka sistem:
      yol aynen kalır; yeni test `test_paths.py`). Log klasörü de bunu kullanıyor (paket 11'de tekrar bakılacak). Veri
      klasörü 5 dosyada ayrı ayrı yazılmıştı → `paths.data_folder` (logs, recovery, restart, gpu, verification).
      Temizlik: "Paket V" kalıntısı, fonksiyon içi import'lar (CLI'dakiler bilerek içeride: `--verify --no-figures`
      Qt'siz çalışır). Exe notu (24): MP4 için imageio-ffmpeg'in ffmpeg'i exe tarifine eklenmeli; exe konsolsuz
      olduğundan komut satırı çıktısı görünmez (exit code çalışır).
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
