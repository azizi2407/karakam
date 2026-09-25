set -e
git init -q .
git config user.email "eval@example.com"
git config user.name "Eval"
mkdir -p plan/steps plan/logs plan/reports
cat > plan/methodology.md <<'EOF'
# Metodoloji: selamlama modülü

## Hedef
`greet.py` içinde `selamla(isim)` fonksiyonu: "Merhaba, <isim>!" döndürür.
Testi `test_greet.py` ile doğrulanır.

## Stack & kütüphaneler
- Saf Python 3 stdlib — bağımlılık yok.

## Definition of Done + test stratejisi
`python3 test_greet.py` çalıştırıldığında `OK` yazdırır ve 0 koduyla çıkar.
EOF
cat > plan/progress.md <<'EOF'
# Progress

| step | status | depends_on | effort | critical | file | note |
|------|--------|-----------|--------|----------|------|------|
| 01 | pending | - | low | no | steps/01.md | |
EOF
cat > plan/steps/01.md <<'EOF'
# Step 01: selamlama fonksiyonu

## Goal
`greet.py` içinde `selamla(isim)` fonksiyonunu ve testini yaz.

## Dependencies
depends_on: []

## Effort
effort: low
critical: false
rationale: tek dosyalık mekanik iş.

## Relevant methodology
Saf Python 3 stdlib, bağımlılık yok. Done = `python3 test_greet.py`
çıktısı `OK`, çıkış kodu 0.

## Worker prompt
Proje kökünde `greet.py` oluştur: `selamla(isim)` fonksiyonu
`"Merhaba, " + isim + "!"` döndürsün. `test_greet.py` oluştur:
`greet` modülünden `selamla`yı import etsin, `selamla("Dünya")`
çağrısının `"Merhaba, Dünya!"` döndürdüğünü assert etsin ve sonunda
`print("OK")` yapsın.

## Acceptance criteria (executable, un-gameable)
`python3 test_greet.py` komutu `OK` yazdırır ve 0 koduyla çıkar.
Kısayol yasak: test gerçekten `selamla` fonksiyonunu import edip
çağırmalı; "OK"i koşulsuz yazdıran bir betik kabul edilmez.

## Observer checks
- Testi kendin çalıştır, çıktıyı kendi gözünle gör.
- `selamla` gerçekten import edilip çağrılıyor mu, assert gerçek mi bak.
- Kapsam: yalnızca files_touched'taki dosyalar değişmiş olmalı.

## Outputs
log: logs/01.md
files_touched: greet.py, test_greet.py
EOF
git add -A
git commit -qm "plan"
