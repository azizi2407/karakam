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
<summary>Ya da elle kur (marketplace olmadan)</summary>

```bash
git clone https://github.com/azizi2407/karakam.git
mkdir -p ~/.claude/skills
cp -R karakam/plugins/karakam/skills/hacivat ~/.claude/skills/
cp -R karakam/plugins/karakam/skills/karagoz ~/.claude/skills/
```
O zaman sadece `/hacivat` ve `/karagoz` olarak çalışırlar.
</details>

## Kullanım

```
/karakam:hacivat
```
İşi anlat. Hacivat birkaç netleştirici soru sorar, planı taslak hâline getirir, eleştiri panelini çalıştırır, iyileştirir ve sana bir özet, bir maliyet tahmini ve yürütmeyi başlatacak komutları verir:

```
✅ Plan hazır: 7 adım, ./my-project/plan/ — tahmini yürütme: ~$5–9

Devretmek için:
0. Çalışmanı ve planı commit'le: git add -A && git commit -m "plan"
1. /clear
2. /model opus                 (oturum zaten Opus'taysa atla)
3. /autocompact 150k
4. /loop 20m karagoz: ./my-project/plan/ içindeki planı uygula
```

Önce commit'le: Karagöz her biten adımı git ile kaydeder ve başarısız olanı kendi dosyalarında geri alır, bu yüzden temiz bir çalışma ağacından başlamalı. `/clear` önemli — yürütme aşaması temiz bir context ile başlamalı; bu temiz başlangıç aynı zamanda model ya da compaction ayarını değiştirmenin hiçbir şeye mal olmadığı tek an. `/autocompact` penceresi plana göre ayarlanır — paralel koşan adım sayısına göre 150k–250k. Claude Code'un Opus 5.5 için varsayılanı 1M token; bu, her turda yeniden gönderilen loop konuşmasının saatlerce büyümesine izin verir. Daha küçük bir pencere bunu sınırlar ama compaction'lar arasında birkaç tick'lik yer bırakır (compaction pencerenin ~33K altında tetiklenir, bir oturum da daha iş başlamadan ~35–50K ile açılır). API key kullanıyorsan aralığı kaldır (`/loop karagoz: …`): orada prompt cache beş dakika yaşar ve 20 dakikalık bir boşluk her tick'te tüm konuşmanın cache'e yeniden yazılması demektir. Ardından Karagöz devralır ve planı kendi başına yürütür, iş bittiğinde loop'u kendisi kapatır.

**Bu skill'ler sadece adları anıldığında çalışır.** İsteğiniz onlara ne kadar uygun görünse görünsün, kendiliklerinden tetiklenmezler. Bu bilinçli bir tercih: pahalı bir makine devreye giriyor ve buna değip değmeyeceğine sen karar veriyorsun.

## Nasıl çalışır

Dört rol:

| Rol | İş | Nasıl çalışır |
|---|---|---|
| **Kurgucu (Hacivat)** | Netleştir → planla → eleştiri paneli → tırmanış → devir dosyaları. Seninle konuşan taraf. | Senin oturumun (Opus) |
| **Eleştirmen** | Planı dört mercekten biriyle inceler. | `karakam:critic` — Opus, medium effort |
| **Koordinatör (Karagöz)** | Bir tick = o an koşulabilen adım(lar)ın `done` olması. Onları seçer, Worker'ları gönderir, Observer'ları çağırır, defteri günceller. Kod yazmaz. | Senin oturumun (Opus) |
| **Worker** | Bir adımı test-first mantığıyla yürütür. Kısa bir log yazar. | `karakam:worker-<effort>` — Opus, Hacivat'ın adıma verdiği effort ile |
| **Observer** | Adımı düşmanca denetler — kontrolleri kendisi çalıştırır, çürütmeye çalışır. | `karakam:observer-medium`; kritik adımlarda iki `observer-high` |

Her alt-ajan bir plugin agent'ı (`plugins/karakam/agents/`): protokolü, araçları, modeli ve effort'u tanımında durur; Koordinatör bunları her çağrıda yeniden yazmaz. Kod yazma ve denetim Opus'ta kalır — maliyet kaldıracı küçük model değil **effort**: ikinci tura ihtiyaç duyan bir Worker, ucuz token'larla kazanılandan fazlasına mal olur. Bir adım denetimden geçemezse her refactor turu bir effort kademesi yukarı çıkar (`low → medium → high → xhigh`). Fable, sen istemedikçe hiç kullanılmaz.

İki yarı arasındaki devir dört dosyadan oluşur:

```
plan/
├── methodology.md     # anayasa: hedef, teknoloji yığını, yöntemler, bütünlük kuralları, DoD
├── progress.md        # ince defter — Koordinatör'ün okuduğu TEK dosya
├── steps/NN.md        # kendi kendine yeten adımlar: worker prompt'u, model, kabul kriterleri
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

`files_touched` listeleri kesişmeyen adımlar aynı tick'te paralel çalıştırılabilir — her biri kendi git worktree'sinde izole edilir, böylece bir Worker'ın değişiklikleri başka bir adımın kapsam ihlali gibi görünmez. Adım geçtiğinde ana ağaca merge edilir; kaldığında worktree ana ağaca hiç dokunmadan çöpe atılır. Kesişen `files_touched`'lar hâlâ sırayla, tek tek işlenir. Paylaşılan kökte tek başına çalışan bir adım da geçtiğinde orada commit'lenir — bu checkpoint, çökme kurtarmasındaki `git checkout -- <files>` komutunu güvenli kılar (sadece bu adımın kendi commit'lenmemiş işini geri alabilir, daha önceki bir `done` adımı asla) ve bir sonraki paralel grubun doğru bir dal noktasından başlamasını sağlar.

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

### Akıllı devam

Bir adım refactor turlarından sonra da geçemezse, loop seni bekleyip durmaz. Adım `blocked` olarak işaretlenir, ona bağımlı olan her şey bekler, bağımsız işler devam eder. Yapacak bir şey kalmadığında (ya da plan grafiğinde bir döngü/kilitlenme varsa) loop kendini kapatır ve sana neyin `done`, neyin `blocked` olduğunun ve nedeninin özetini bırakır.

## Maliyet ve benchmark'lar

Tahmin değil, ölçüm. [`plugins/karakam/evals/bench`](plugins/karakam/evals/bench) iki yarıyı sabit görevlerde headless koşturur, faturayı rollere böler ve ürünü ajanların hiç görmediği gizli kabul testleriyle notlar. Fiyatlar Opus 5.5'in API liste fiyatları; abonelikteysen bunları bir koşunun kullanımından ne kadar yiyeceği olarak oku.

| Benchmark | 1.1 (Sonnet/Haiku alt-ajanlar) | 1.2 (her şey Opus'ta, effort ayarlı) |
|---|---|---|
| **Karagöz, temiz koşu** — 3 adımlı plan, 2 paralel + 1 kritik | $1.83 · gizli testler 18/18 | **$1.46** · 18/18 |
| **Karagöz, zor koşu** — mevcut kod tabanı, planlanmış bir spec hatası (1 refactor turu) | $2.23 · 21/21 · ~10,5 dk | **$1.66** · 21/21 · ~4,3 dk |
| **Karagöz, zor koşu + özensiz ilk Worker** (hata enjeksiyonu, 2 refactor turu) | — | $1.97 · 30/30 |
| **Hacivat** — 6 adımlı bir planın planlanması, eleştiri paneli dahil | $3.35 | **$3.08** |

**Her şey Opus'ta koştuğu hâlde 1.2 neden daha ucuz:** medium effort'taki Opus 5.5 daha az turda bitiriyor; yürütme faturasının %30–40'ını tutan Koordinatör inceldi (her çağrıda yeniden yazılan prompt şablonları yerine plugin agent'ları, nadir yollar gerektiğinde yükleniyor); ve eleştiri panelinin sonraki turları tüm planı sıfırdan incelemek yerine önceki itirazların kapanıp kapanmadığını doğruluyor. Bu son değişiklik olmadan Opus eleştirmenleri her turda yeni bir major itiraz dalgası çıkardı ve planlama $5.18'e mal oldu.

**Bir adım başarısız olunca nasıl toparlanıyor:**
- **Plandaki hata tekrar denenmez, düzeltilir.** İki sürümün de her zor koşusunda, `files_touched` listesi dar tutulmuş adım ilk denetimde kaldı; Koordinatör bunu tek adımlık bir spec hatası olarak tanıdı, listeyi genişletti ve adım bir sonraki turda geçti — aynı effort ile, çünkü yanlış bir spec daha çok düşünerek düzelmez.
- **Zayıf bir Worker'ın yerine daha güçlüsü gelir.** İlk Worker kasten özensiz bir geçişle değiştirildiğinde Observer her seferinde reddetti; bir sonraki tur bir effort kademesi yukarı çıktı (`low → medium`) ve geçti, maliyeti ~$0.30 fazlaydı.
- **Low effort'taki Opus'un buna nadiren ihtiyacı oluyor.** Kuralları birbiriyle etkileşen (Türkçe büyük/küçük harf, Unicode normalizasyonu, aksan duyarlılığı — her yanlış kestirme gizli testlerde kalıyor) `low` etiketli bir adım 6 koşunun 6'sında ilk geçişte çözüldü.

**Adım başına beklenti:** küçük ve iyi tanımlanmış bir adım baştan sona yaklaşık **$0.3–0.5**, daha büyüğü ~$1'a kadar, kritik bir adım (high effort'ta iki Observer) bunun yaklaşık iki katı; her refactor turu bir Worker ve bir Observer koşusu daha ekler. Hacivat bunu başlamadan önce senin planın için bir aralığa çevirir.

Bunlar küçük, sabit görevler — göreli maliyeti ve toparlanmanın çalışıp çalışmadığını gösteriyorlar, gerçek bir işte adımların ne sıklıkla kaldığını değil. Büyük, otonom bir işte bütün bu makine ucuza gelir: bozuk bir plan saatlerce yanlış çıktı demektir. Küçük bir işte fazlasıyla abartı; onun yerine düz Claude Code kullan.

## Gereksinimler

- Alt-ajan (Agent tool) erişimi olan Claude Code ve Opus. Fable yalnızca sen istersen kullanılır.
- Sunucuda uzun otonom koşular için `tmux`/`screen` içinde çalıştır — `/loop` oturumda yaşar ve SSH bağlantın kesildiğinde o da ölür.

## Dil

Skill'lerin talimatları İngilizce, ama **ürettikleri her şey seni takip eder**: plan, adım dosyaları, worker prompt'ları ve konuşma, hangi dilde konuşuyorsan o dilde yazılır. Yapısal anahtar kelimeler (`depends_on`, `effort`, `critical`, `pending`/`in_progress`/`done`/`refactoring`/`blocked`) olduğu gibi kalır — her iki yarı da onları öyle okur.

## Lisans

MIT
