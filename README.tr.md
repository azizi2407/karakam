[English](README.md) · **Türkçe**

# Hacivat & Karagöz

Claude Code için otonom bir **planla ve inşa et** ikilisi.

Türk gölge oyununda Hacivat ve Karagöz aynı oyunun iki yarısıdır: **Hacivat okumuş olandır — kurar, kelimelere döker. Karagöz ise sahada asıl işi yapandır.** Bu iki skill de aynı şekilde ayrışıyor.

- **`hacivat`** büyük bir işi, eleştiriden geçmiş bir plana dönüştürür — brifi netleştirir, taslak üzerinde **dört mercekli bir eleştiri paneli** çalıştırır, itirazlar bitene kadar tırmanır, her adımın Worker'ının ne kadar derin düşüneceğini belirler ve devir dosyalarını yazar.
- **`karagoz`** bu planı bir `/loop` içinde yürütür — her tick'te bir (veya bağımsızsa birden çok) adım, her biri bir **Worker** alt-ajanına verilir ve düşmanca bir **Observer** tarafından denetlenir; durum bir defterde tutulur.

Amaç, insansız saatlerce sürebilen ve context'i patlatmayan bir iş akışı.

## Kurulum

```
/plugin marketplace add azizi2407/karakam
/plugin install karakam@kara-skills
```

Skill'ler eklentiye göre isimlendirilir: `/karakam:hacivat` ve `/karakam:karagoz`.

<details>
<summary>Ya da bir klondan çalıştır</summary>

```bash
git clone https://github.com/azizi2407/karakam.git
claude --plugin-dir karakam/plugins/karakam      # tek oturum için
```
Ya da klondan kalıcı olarak kur: `/plugin marketplace add ./karakam`, ardından `/plugin install karakam@kara-skills`. Sadece skill klasörlerini `~/.claude/skills/` altına kopyalamak işe yaramaz: skill'ler eklentinin `karakam:` alt-ajanlarını çağırır ve bunlar yalnızca karakam bir eklenti olarak yüklendiğinde vardır.
</details>

## Kullanım

```
/karakam:hacivat
```
İşi anlat. Hacivat birkaç netleştirici soru sorar, planı taslak hâline getirir, eleştiri panelini çalıştırır, iyileştirir ve sana bir özet, bir maliyet tahmini ve yürütmeyi başlatacak komutları verir:

```
✅ Plan hazır: 7 adım, ./my-project/plan/ — tahmini yürütme: ~$5–9

Devretmek için:
0. Önce kendi çalışmanı, sonra planı commit'le: git add ./my-project/plan && git commit -m "plan"
1. /clear
2. /model opus                 (oturum zaten Opus'taysa atla)
3. /effort medium
4. /autocompact 150k
5. /loop 20m karagoz: ./my-project/plan/ içindeki planı uygula
```

Önce commit'le (git projesindeysen): Karagöz her biten adımı git ile kaydeder ve başarısız olanı kendi dosyalarında geri alır, bu yüzden temiz bir çalışma ağacından başlamalı — kendi değişikliklerini, başıboş dosyaları da süpürecek toptan bir `git add -A` yerine kendin commit'le. `/clear` önemli — yürütme aşaması temiz bir context ile başlamalı; bu temiz başlangıç aynı zamanda model, effort ya da compaction ayarını değiştirmenin hiçbir şeye mal olmadığı tek an. `/effort medium`, Koordinatörü — yani senin oturumunu, yürütme faturasının %30–40'ı — ölçüldüğü effort'a sabitler; yoksa oturum en son ayarladığın effort'la devam eder ve başka bir iş için bırakılmış bir `xhigh`, her turda mekanik defter işine derin düşünme parası öder. Alt-ajanların effort'u kendi tanımlarında durur. `/autocompact` penceresi plana göre ayarlanır — paralel koşan adım sayısına göre 150k–250k. Claude Code'un Opus 5.5 için varsayılanı 1M token; bu, her turda yeniden gönderilen loop konuşmasının saatlerce büyümesine izin verir. Daha küçük bir pencere bunu sınırlar ama compaction'lar arasında birkaç tick'lik yer bırakır (compaction pencerenin ~33K altında tetiklenir, bir oturum da daha iş başlamadan ~35–50K ile açılır). API key kullanıyorsan aralığı kaldır (`/loop karagoz: …`): orada prompt cache beş dakika yaşar ve 20 dakikalık bir boşluk her tick'te tüm konuşmanın cache'e yeniden yazılması demektir. Ardından Karagöz devralır ve planı kendi başına yürütür, iş bittiğinde loop'u kendisi kapatır.

**Bu skill'ler sadece adları anıldığında çalışır.** İsteğiniz onlara ne kadar uygun görünse görünsün, kendiliklerinden tetiklenmezler. Bu bilinçli bir tercih: pahalı bir makine devreye giriyor ve buna değip değmeyeceğine sen karar veriyorsun.

## Nasıl çalışır

Dört rol:

| Rol | İş | Nasıl çalışır |
|---|---|---|
| **Kurgucu (Hacivat)** | Netleştir → planla → eleştiri paneli → tırmanış → devir dosyaları. Seninle konuşan taraf. | Senin oturumun (Opus) |
| **Eleştirmen** | Planı dört mercekten biriyle inceler. | `karakam:critic` — Opus, medium effort |
| **Koordinatör (Karagöz)** | Bir tick = o an koşulabilen adım(lar)ın `done` olması. Onları seçer, Worker'ları gönderir, Observer'ları çağırır, defteri günceller. Kod yazmaz. | Senin oturumun (Opus, medium effort) |
| **Worker** | Bir adımı test-first mantığıyla yürütür. Kısa bir log yazar. | `karakam:worker-<effort>` — Sonnet 5.5, Hacivat'ın adıma verdiği effort ile (varsayılan `high`); refactor turları: önce `worker-opus-high`, sonra `worker-opus-xhigh` |
| **Observer** | Adımı düşmanca denetler — kontrolleri kendisi çalıştırır, çürütmeye çalışır. | `karakam:observer-medium`; kritik adımlarda iki `observer-high` |

Her alt-ajan bir plugin agent'ı (`plugins/karakam/agents/`): protokolü, araçları, modeli ve effort'u tanımında durur; Koordinatör bunları her çağrıda yeniden yazmaz. Worker'lar kodu Sonnet 5.5'te, adım mekanik değilse `high` effort'ta yazar; onları denetleyen Observer'lar, eleştirmenler ve Koordinatör Opus'ta koşar. Bir adım denetimden geçemezse tekrar deneme yalnızca daha çok düşünmekle kalmaz, daha güçlü bir modele gider: önce `high`'da, sonra `xhigh`'da bir Opus Worker. Fable, sen istemedikçe hiç kullanılmaz.

İki yarı arasındaki devir dört dosyadan oluşur:

```
plan/
├── methodology.md     # anayasa: hedef, teknoloji yığını, yöntemler, bütünlük kuralları, DoD
├── progress.md        # ince defter — Koordinatör'ün okuduğu TEK dosya
├── steps/NN.md        # kendi kendine yeten adımlar: worker prompt'u, effort, kabul kriterleri
├── logs/  reports/    # Worker logları ve uzun Observer raporları
```

### Context ekonomisi

Koordinatör **ince** kalır, geri kalan her şey bundan gelir:

- **İçerik değil, yol (path) taşı.** "`steps/03.md`'yi oku" der — 03.md'yi kendisi asla okumaz. Worker onu kendi izole context'inde açar.
- **Tek durum kaynağı defterdir.** Her tick, gerçeği `progress.md`'den taze okur; bu yüzden loop konuşmasının compact edilmesi hiçbir şey kaybettirmez. Tek ara yazım, Worker'ı göndermeden hemen önce yazılan `in_progress` işaretidir; o da yarım kalan bir tick'in bir sonraki tick'te toparlanabilmesi için var.
- **Nadir yollar gerektiğinde yüklenir.** Çökme kurtarma, worktree mekaniği ve hata yönetimi, Koordinatör'ün yalnızca o durum ortaya çıkınca açtığı referans dosyalarında durur; her tick'te yüklenen skill gövdesi küçük kalır, çünkü her tick onu sonraki her turda yeniden gönderilen konuşmaya ekler.
- **Kısa raporlar.** Worker'lar ve Observer'lar 2-3 satır döner; uzun raporlar bir dosyaya yazılır, geri sadece yol döner.

Loop'un birkaç tick sonra çökmek yerine saatlerce dönebilmesini sağlayan şey bu.

### Bağımsız adımlarda paralellik

`files_touched` listeleri kesişmeyen adımlar aynı tick'te paralel çalıştırılabilir — her biri kendi git worktree'sinde izole edilir, böylece bir Worker'ın değişiklikleri başka bir adımın kapsam ihlali gibi görünmez. Adım geçtiğinde kendi worktree'sinde commit'lenir ve ana ağaca merge edilir; kaldığında worktree ana ağaca hiç dokunmadan çöpe atılır. Kesişen `files_touched`'lar hâlâ sırayla, tek tek işlenir. Paylaşılan kökte tek başına çalışan bir adım da geçtiğinde, defter onu `done` saymadan önce orada commit'lenir. Bu checkpoint, başarısız ya da yarım kalmış bir adımı geri almayı güvenli kılar — geri alma yalnızca o adımın kendi commit'lenmemiş işine ulaşır, daha önceki bir `done` adımına asla — ve bir sonraki paralel grubun doğru bir dal noktasından başlamasını sağlar. Bu commit ve geri almalar, bir adımın yarattığı ya da sildiği dosyaları da doğru işleyen küçük bir script'ten (`skills/karagoz/scripts/stepgit.sh`) geçer; bir dosya listesi üzerinde düz `git add` / `git checkout` bunları sessizce yanlış yapar.

### Derinlemesine savunma — insan gerekmeden

Kalite, hiçbiri sana bir şey sormadan duran üç otonom katmanla korunur:

1. **Test-first Worker'lar** — bir adımın "bitti" olması, Worker'ın kendi iddiasına değil, çalışan bir kontrole bağlıdır.
2. **Düşmanca Observer'lar** — Observer, Worker'ın raporuna güvenmez. Testleri kendisi çalıştırır, Worker'ın *test kodundan* da şüphelenir (bir test, kanıtlaması gereken durumu kendisi hazırlayarak kendini kandırabilir).
3. **Kritik adımlarda çift Observer** — biri davranışa, biri bütünlüğe bakan iki mercek. **Herhangi biri veto edebilir.**

O üçüncü katman hakkını veriyor. Bu ikilinin ilk gerçek koşusunda, kritik bir adımda:

- Worker *"35/35 test geçti"* dedi — ama testlerden biri kanıtlaması gereken durumu kendisi önceden hazırlamıştı, gerçek yol hiç çalışmamıştı.
- **Observer-B (bütünlük)** adımı onayladı: kod spec'e birebir uyuyordu. Haklıydı da.
- **Observer-A (davranış)** akışı bizzat çalıştırdı ve reddetti: bir rate limiter, ancak başarılı bir gönderimden *sonra* devreye giriyordu — yani mail sunucusu çöktüğünde tam da korumaya ihtiyaç duyulan anda hiçbir koruma sağlamıyordu; her biri 10 saniyelik timeout'a sabitlenmiş sınırsız istek.
- Spec'in kendisi yanlıştı. Worker ona sadakatle uymuştu.

Tek bir Observer — **ikisinden hangisi olursa olsun** — bunun geçmesine izin verirdi.

### İlerleme paneli

Karagöz başladığında sağ üst köşede küçük bir panel açılır — tam ekran transkriptin sağına sabitlenmiş dar bir sütun (ana ekranda prompt'un üstünde). Adımlar sırayla bitmez — Karagöz bağımlılık grafiğinin izin verdiği adımı yürütür — bu yüzden panel her adıma bir hücre ayıran bir harita, her durumdan kaç adım olduğunu ve şu an çalışan her alt-ajanı — adı, üzerinde çalıştığı adım ve ne zamandır çalıştığıyla — gösterir:

```
01 ✓✓○·✓·✓↻·✗
✓4 ↻1 ○1 ·3 ✗1
▶ 03 observer-medium 41s
▶ 08 worker-opus-high · r… 2m 5s
✗ 10 blocked
details
```

`✓` bitti, `▶` çalışıyor, `↻` refactor'da, `✗` bloklandı, `○` hazır (tüm bağımlılıkları bitti, hemen başlayabilir), `·` bekliyor. `d`'ye (ya da `details`'e) basınca tam liste açılır: her adım, bekleyenlerin neyi beklediği ve her adımın altında mikro-adımları olurken — her Worker ve Observer koşusu (ajanı, Observer'ın bakış açısı, sonuç, süre, çalıştığı model ve harcadığı token), Opus'taki refactor turları ve git checkpoint'i:

```
· 06 waiting · high · waits on 08
↻ 08 refactoring · high · critical — refactor 1/3 @opus-high
  ├ ✓ worker-high · sonnet 1m 12s · sonnet-5.5 · 45.8k tokens (3.2k out)
  ├ ✗ observer-high · behavior FAIL 30s · opus-5.5 · 61.0k tokens (2.1k out)
  └ … worker-opus-high · refactor · opus-5.5
```

Bir Claude Code mod'u (`plugins/karakam/hooks/progress.tsx`): yalnızca izler — skill'ler onsuz da aynı çalışır. Kendiliğinden açıldığında panel en az 144 sütunluk bir terminal ister; `/karakam-progress` her genişlikte açar.

### İsteğe bağlı Jev yargıcı

Bazı kararlar düzyazı değil, kalibre edilmiş bir evet, hayır ya da seçim ister. `TYPESAFE_API_KEY` tanımlıysa karakam beş noktada TypeSafe'in [Jev](https://docs.typesafe.ai) modeline sorar — tipli sorulara olasılıkla cevap veren, kuruşun altında maliyetli bir model. Anahtar yoksa Worker stop guard Haiku ile çalışır, diğer dördü atlanır; `KARAKAM_JUDGE=off` hepsini kapatır.

- **Worker stop guard.** Bir Worker nihai rapor yerine bir ara özetle ("sıradaki adımda CLI'yı bağlayacağım…") durursa, guard onu bir kez geri gönderir ve işi aynı context içinde bitirtir; adımın denetimden kalmasına ya da Koordinatörün onu sürdürmek için tur harcamasına izin vermez. Jev anahtarı yoksa kendi oturumun üzerinden Haiku ile yargılar; karar başına yaklaşık $0.0001.
- **Effort için ikinci görüş.** Hacivat planı yazdıktan sonra `jev.py effort` çalıştırır: low ya da medium verdiği ama Jev'in büyük olasılıkla `high` gördüğü adım yükseltilir; Jev'in daha basit olduğundan neredeyse emin olduğu kritik olmayan bir `high` adım düşürülebilir.
- **Critic lensleri.** İlk panel turundan önce `jev.py lenses`, stack/library ve adım sırası lenslerinin bu planda yargılayacak bir şeyi olup olmadığına bakar; bakacak bir şeyi olmayan lens 1. turda yer almaz.
- **Hata ayrımı.** Bir Observer FAIL'i Worker'ın da spec'in de hatası olabiliyorsa, Koordinatör bir tur harcamadan önce `jev.py triage` ikinci görüş verir.
- **Bench puanlaması.** Bench'in hacivat modunda `jev.py rubric` her planı kontrata göre puanlar (kendi kendine yeten adımlar, çalıştırılabilir kriterler, seeding kestirmesi olmaması, çağıran üzerinden geçen kontroller, ayrık paralel dosyalar, dürüst sınırlar).

Jev yalnızca metin okur ve hiçbir şey çalıştırmaz, bu yüzden bir Observer'ın yerini asla almaz: skill'in tarttığı bir tavsiyedir ve ona ulaşılamazsa koşu onsuz devam eder.

### Akıllı devam

Bir adım refactor turlarından sonra da geçemezse, loop seni bekleyip durmaz. Adım `blocked` olarak işaretlenir, ona bağımlı olan her şey bekler, bağımsız işler devam eder. Yapacak bir şey kalmadığında (ya da plan grafiğinde bir döngü/kilitlenme varsa) loop kendini kapatır ve sana neyin `done`, neyin `blocked` olduğunun ve nedeninin özetini bırakır.

## Maliyet ve benchmark'lar

Tahmin değil, ölçüm. [`plugins/karakam/evals/bench`](plugins/karakam/evals/bench) iki yarıyı sabit görevlerde headless koşturur, faturayı rollere böler ve ürünü ajanların hiç görmediği gizli kabul testleriyle notlar. Fiyatlar Opus 5.5'in API liste fiyatları; abonelikteysen bunları bir koşunun kullanımından ne kadar yiyeceği olarak oku.

| Benchmark | 1.1 (Sonnet/Haiku alt-ajanlar) | 1.2 (her şey Opus'ta, effort ayarlı) | 1.3 (adımlar `low`'dan başlar) | 1.4 (Sonnet 5.5 Worker'lar `high`'da) |
|---|---|---|---|---|
| **Karagöz, temiz koşu** — 3 adımlı plan, 2 paralel + 1 kritik | $1.83 · gizli testler 18/18 | $1.46 · 18/18 | $1.24 · 18/18 | **$1.11** · 18/18 |
| **Karagöz, zor koşu** — mevcut kod tabanı, planlanmış bir spec hatası (1 refactor turu) | $2.23 · 21/21 · ~10,5 dk | $1.66 · 21/21 · ~4,3 dk | $1.47 · 30/30 · ~3,7 dk | **$1.39** · 30/30 · ~3,7 dk |
| **Karagöz, zor koşu + özensiz ilk Worker** (hata enjeksiyonu, 2 refactor turu) | — | $1.97 · 30/30 | $1.85 · 30/30 | **$1.54** · 30/30 |
| **Karagöz, büyük koşu** — FIFO stok maliyetlendirmesinin 6 adımı, 2'si kritik | — | — | $3.32–5.32 · 57/57 | **$2.89–3.28** · 57/57 |
| **Hacivat** — 6 adımlı bir planın planlanması, eleştiri paneli dahil | $3.35 | $3.08 | $2.71 | **$2.62** |

**Her şey Opus'ta koştuğu hâlde 1.2 neden daha ucuz:** medium effort'taki Opus 5.5 daha az turda bitiriyor; yürütme faturasının %30–40'ını tutan Koordinatör inceldi (her çağrıda yeniden yazılan prompt şablonları yerine plugin agent'ları, nadir yollar gerektiğinde yükleniyor); ve eleştiri panelinin sonraki turları tüm planı sıfırdan incelemek yerine önceki itirazların kapanıp kapanmadığını doğruluyor. Bu son değişiklik olmadan Opus eleştirmenleri her turda yeni bir major itiraz dalgası çıkardı ve planlama $5.18'e mal oldu.

**1.3 neden yine daha ucuz:** her adım 1.2'dekinden bir effort kademesi aşağıda koşuyor — iyi tanımlanmış iş, kritik adım dahil, `low`'da — ve gizli testler aynı çıktı, fazladan refactor turu olmadı; Worker harcaması yaklaşık üçte bir düştü. Devir şablonu da Koordinatörü, bu sayıların hepsinin ölçüldüğü `medium` effort'a sabitliyor.

**1.4 neden daha da ucuz:** Worker'lar, token'ı Opus'un yarı fiyatı olan Sonnet 5.5'te koşuyor — `high` effort'ta bile `low`/`medium`'daki Opus Worker'lardan az harcadılar ve üç plandaki 6 koşunun hepsinde gizli testlerin tamamını fazladan refactor turu olmadan geçtiler. Faturanın çoğu artık Opus tarafında: Observer'lar ve Koordinatör.

**Bir adım başarısız olunca nasıl toparlanıyor:**
- **Plandaki hata tekrar denenmez, düzeltilir.** İki sürümün de her zor koşusunda, `files_touched` listesi dar tutulmuş adım ilk denetimde kaldı; Koordinatör bunu tek adımlık bir spec hatası olarak tanıdı, listeyi genişletti ve adım bir sonraki turda geçti — aynı effort ile, çünkü yanlış bir spec daha çok düşünerek düzelmez.
- **Zayıf bir Worker'ın yerine daha güçlüsü gelir.** İlk Worker kasten özensiz bir geçişle değiştirildiğinde Observer her seferinde reddetti ve sonraki Worker geçti. 1.2 onu bir kademe yukarı gönderiyordu (`low → medium`, ~$0.30 fazla); 1.3 doğrudan `high`'a çıkıyor (`low → high`) ve toparlanma ~$0.20 tuttu. 1.4'te tekrar deneme Opus'a gidiyor (`high → opus-high`).
- **Low effort'taki Opus'un buna nadiren ihtiyacı oluyor.** Kuralları birbiriyle etkileşen (Türkçe büyük/küçük harf, Unicode normalizasyonu, aksan duyarlılığı — her yanlış kestirme gizli testlerde kalıyor) `low` etiketli bir adım 6 koşunun 6'sında ilk geçişte çözüldü.
- **Sonnet 5.5 Worker'lar da geçti, daha ucuza.** Tüm Worker'lar Sonnet 5.5'e alındığında (Observer'lar hâlâ Opus'ta) zor koşu iki koşuda da 30/30 geçti; Opus Worker'larla $1.66'ya karşı $1.28. Daha büyük bir planda — FIFO stok maliyetlendirmesinin altı adımı; her kuralın, 57 gizli testin yakaladığı cazip bir kestirmesi var — Sonnet Worker'lar 3 koşunun 3'ünde 57/57 geçti, $2.63–3.40'a; Opus Worker'lar da 57/57, $3.32–5.32'ye. Refactor turu artmadı; Worker harcaması $1.12–1.69'a karşı $0.40–0.52. 1.4 ile Sonnet 5.5 varsayılan Worker oldu; bench'in `--worker-model opus` seçeneği karşılaştırmayı yeniden koşar.
- **Yarıda duran Worker kovalanmıyor, geri gönderiliyor.** Her Worker kodu yazdıktan sonra bir ara özetle duracak şekilde ayarlandığında, Koordinatör bunu her seferinde fark edip Worker'ı kendisi sürdürdü: 3 devam ettirme, yaklaşık iki kat Koordinatör turu, $1.31–1.45. 1.6'nın stop guard'ıyla Worker'lar Koordinatör görmeden geri gönderildi: Haiku yargıcıyla $1.09–1.15, Jev ile $1.19–1.27; temiz koşular $1.07–1.18. İki yargıç da yarım kalan her Worker'ı yakaladı ve 12 temiz duruşun hiçbirini geri göndermedi; kararların kendisi kuruşun yüzde biri mertebesinde. Her koşu 18/18 geçti.
- **Başarısız bir checkpoint artık işi kaybettirmiyor.** Büyük koşulardan birinde bir adım denetimden geçti ama commit'i imza zaman aşımına düştü; Koordinatörün elle zincirlediği commit–merge–temizlik komutları worktree'yi yine de sildi. 1.3 paralel adımları `stepgit.sh land` ile indiriyor: başarısız commit ya da merge'ü bir kez yeniden deniyor, worktree'yi ancak merge başarılı olduktan sonra siliyor.

**Adım başına beklenti:** küçük ve iyi tanımlanmış bir adım baştan sona yaklaşık **$0.3–0.5**, daha büyüğü ~$1'a kadar, kritik bir adım (high effort'ta iki Observer) bunun yaklaşık iki katı; her refactor turu bir Worker ve bir Observer koşusu daha ekler. Hacivat bunu başlamadan önce senin planın için bir aralığa çevirir.

Bunlar küçük, sabit görevler — göreli maliyeti ve toparlanmanın çalışıp çalışmadığını gösteriyorlar, gerçek bir işte adımların ne sıklıkla kaldığını değil. Büyük, otonom bir işte bütün bu makine ucuza gelir: bozuk bir plan saatlerce yanlış çıktı demektir. Küçük bir işte fazlasıyla abartı; onun yerine düz Claude Code kullan.

## Gereksinimler

- Alt-ajan (Agent tool) erişimi olan Claude Code, Opus ve Sonnet. Fable yalnızca sen istersen kullanılır.
- İlerleme paneli ve Worker stop guard için: function hook (mod) destekleyen bir Claude Code sürümü.
- İsteğe bağlı: Jev yargıcı için bir TypeSafe API anahtarı (`TYPESAFE_API_KEY`).
- Sunucuda uzun otonom koşular için `tmux`/`screen` içinde çalıştır — `/loop` oturumda yaşar ve SSH bağlantın kesildiğinde o da ölür.

## Dil

Skill'lerin talimatları İngilizce, ama **ürettikleri her şey seni takip eder**: plan, adım dosyaları, worker prompt'ları ve konuşma, hangi dilde konuşuyorsan o dilde yazılır. Yapısal anahtar kelimeler (`depends_on`, `effort`, `critical`, `pending`/`in_progress`/`done`/`refactoring`/`blocked`) olduğu gibi kalır — her iki yarı da onları öyle okur.

## Lisans

MIT
