hacivat: "kisalink" adında küçük bir URL kısaltma servisi planla.

- Stack: saf Python 3.11 stdlib (`http.server`, `sqlite3`), testler pytest ile. Dış bağımlılık yok.
- Uç noktalar: `POST /api/kisalt` (JSON `{"url": ...}` alır, `{"kod": ..., "kisa_url": ...}` döner),
  `GET /<kod>` (302 ile yönlendirir, tıklama sayar), `GET /api/istatistik/<kod>` (tıklama sayısı, oluşturma zamanı).
- Kurallar: yalnızca http/https URL'leri; kod 7 karakter base62; aynı URL tekrar kısaltılırsa aynı kod döner;
  IP başına dakikada 30 istek sınırı (aşımda 429); SQLite dosyası yolu ortam değişkeninden.
- Kapsam dışı: kullanıcı hesapları, özel alan adları, arayüz.

Brief net — netleştirme sorusu sorma, makul varsayımlarla ilerle. Onayımı bekleme:
planı yazıp kısa bir özet ve devir şablonuyla bitir. Çıktı dizini: ./plan/
