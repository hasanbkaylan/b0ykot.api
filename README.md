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
| **TXT** | `https://hasanbkaylan.github.io/b0ykot.api/v1/boykot-variants.txt` | Yazım varyasyonlu boykot listesi |
| **TXT** | `https://hasanbkaylan.github.io/b0ykot.api/v1/boykotdegil-variants.txt` | Yazım varyasyonlu boykot değil listesi |

---

## Yazım Farklılıklarını Yakalama

Market verilerinde marka isimleri bazen Türkçe karakterli/aksanlı (`Nestlé`, `Çaykur`, `Şölen`), bazen tireli (`Burger-King`), bazen bitişik (`BurgerKing`) gelebilir. Bunu çözmek için `/v1/lookup.json` dosyasını kullanabilirsiniz.

### JavaScript / Tarayıcı Örneği
```javascript
const trMap = {
  "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i",
  "I": "i", "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u", "é": "e", "É": "e"
};

const normalize = (text) =>
  text
    .replace(/[çÇğĞıİIöÖşŞüÜéÉ]/g, (ch) => trMap[ch] || ch)
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");

const res = await fetch("https://hasanbkaylan.github.io/b0ykot.api/v1/lookup.json");
const lookup = await res.json();

const marketMarkasi = "NESTLÉ"; // veya "Burger King", "Çaykur", "Şölen"
const sonuc = lookup[normalize(marketMarkasi)];

console.log(sonuc);
// Çıktı: { name: "Nestlé", status: "boykot" }
```

### Python Örneği
```python
import re
import unicodedata
import requests

TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i",
    "I": "i", "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u", "é": "e", "É": "e"
})

def normalize(text: str) -> str:
    text = text.translate(TR_MAP).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text)

lookup = requests.get("https://hasanbkaylan.github.io/b0ykot.api/v1/lookup.json").json()

sonuc = lookup.get(normalize("Çaykur"))
print(sonuc)
# Çıktı: {'name': 'Çaykur', 'status': 'boykot_degil'}
```

---

## Nasıl Katkı Yapılır?

Listeye yeni marka eklemek veya hata bildirmek için [Katkıda Bulunma Rehberi](CONTRIBUTING.md) dosyasını inceleyebilir ya da doğrudan **Issues** sekmesinden marka öneri formunu doldurabilirsiniz.

## Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.
