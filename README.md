# b0ykot.api

Türkiye'deki market ve e-ticaret ürünlerinde kullanılan markalar için topluluk destekli, açık kaynaklı **boykot / alternatif marka** veri tabanı ve ücretsiz Statik JSON API'si.

Verilerin ana kaynağı kök dizindeki sade `boykot.txt` ve `boykotdegil.txt` dosyalarıdır. Her güncellemede GitHub Actions tarafından otomatik olarak doğrulanır, yazım varyasyonları üretilir ve JSON API olarak yayınlanır.

## API Uç Noktaları (Endpoints)

CORS dostudur; tarayıcı eklentilerinden, mobil uygulamalardan ve backend servislerinden limitsiz ve API anahtarı (API Key) olmadan doğrudan çekilebilir.

| Format | Adres | Açıklama |
| :--- | :--- | :--- |
| **JSON** | `https://hasanbkaylan.github.io/b0ykot.api/v1/all.json` | Tüm markalar ve güncelleme tarihi |
| **JSON** | `https://hasanbkaylan.github.io/b0ykot.api/v1/lookup.json` | Hızlı arama sözlüğü (normalize edilmiş anahtarlar) |
| **JSON** | `https://hasanbkaylan.github.io/b0ykot.api/v1/boykot.json` | Sadece boykot markaları |
| **JSON** | `https://hasanbkaylan.github.io/b0ykot.api/v1/boykotdegil.json` | Sadece boykot olmayan markalar |
| **TXT** | `https://hasanbkaylan.github.io/b0ykot.api/boykot.txt` | Ham boykot listesi |
| **TXT** | `https://hasanbkaylan.github.io/b0ykot.api/boykotdegil.txt` | Ham boykot değil listesi |
| **TXT** | `https://hasanbkaylan.github.io/b0ykot.api/v1/boykot-variants.txt` | Otomatik üretilmiş yazım varyasyonlu liste |

---

## Yazım Farklılıklarını Yakalama

Market verilerinde marka isimleri bazen aksanlı (`Nestlé`), bazen tireli (`Burger-King`), bazen bitişik (`BurgerKing`) gelebilir. Bunu çözmek için `/v1/lookup.json` dosyasını kullanabilirsiniz.

### JavaScript / Tarayıcı Örneği
```javascript
const normalize = (text) =>
  text
    .replace(/İ/g, "i")
    .replace(/I/g, "i")
    .replace(/ı/g, "i")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");

const res = await fetch("https://hasanbkaylan.github.io/b0ykot.api/v1/lookup.json");
const lookup = await res.json();

const marketMarkasi = "NESTLÉ"; // veya "Burger King", "Domino’s"
const sonuc = lookup[normalize(marketMarkasi)];

console.log(sonuc);
// Çıktı: { name: "Nestlé", status: "boykot" }
```

### Python Örneği
```python
import re
import unicodedata
import requests

def normalize(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text)

lookup = requests.get("https://hasanbkaylan.github.io/b0ykot.api/v1/lookup.json").json()

sonuc = lookup.get(normalize("Burger King"))
print(sonuc)
# Çıktı: {'name': 'Burger-King', 'status': 'boykot'}
```

---

## Nasıl Katkı Yapılır?

Listeye yeni marka eklemek veya hata bildirmek için [Katkıda Bulunma Rehberi](CONTRIBUTING.md) dosyasını inceleyebilir ya da doğrudan **Issues** sekmesinden marka öneri formunu doldurabilirsiniz.

## Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.
