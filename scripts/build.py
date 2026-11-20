import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone


def normalize(text: str) -> str:
    """Marka adını aksansız, boşluksuz ve küçük harfli standart anahtara çevirir."""
    text = text.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text)


def load_brands(filename: str) -> dict[str, str]:
    brands: dict[str, str] = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            key = normalize(raw)
            if key and key not in brands:
                brands[key] = raw
    return brands


def generate_variants(name: str) -> list[str]:
    """Tireli, boşluklu, kesme işaretsiz ve aksansız yazım varyasyonları üretir."""
    bases = {
        name,
        name.replace("-", " "),
        name.replace("-", ""),
        name.replace("'", "").replace("’", ""),
        name.replace("-", " ").replace("'", "").replace("’", ""),
        name.replace("-", "").replace("'", "").replace("’", ""),
    }
    variants = set()
    for item in bases:
        variants.add(item)
        # Aksanları kaldır (é -> e, ü -> u vb.)
        no_accent = "".join(
            c
            for c in unicodedata.normalize("NFKD", item)
            if not unicodedata.combining(c)
        )
        no_accent = no_accent.replace("ı", "i").replace("İ", "I")
        variants.add(no_accent)
    return sorted(v for v in variants if v)


def main():
    boykot = load_brands("boykot.txt")
    boykot_degil = load_brands("boykotdegil.txt")

    # Çakışma kontrolü (aynı marka iki listede birden olamaz)
    conflicts = set(boykot.keys()) & set(boykot_degil.keys())
    if conflicts:
        conflict_names = [f"{boykot[k]} / {boykot_degil[k]}" for k in sorted(conflicts)]
        raise ValueError(
            "HATA: Hem boykot.txt hem boykotdegil.txt içinde bulunan markalar var:\n- "
            + "\n- ".join(conflict_names)
        )

    os.makedirs("dist/v1", exist_ok=True)

    # 1. Orijinal txt dosyalarını dokunmadan dist içine kopyala
    shutil.copyfile("boykot.txt", "dist/boykot.txt")
    shutil.copyfile("boykotdegil.txt", "dist/boykotdegil.txt")

    # 2. Temizlenmiş ve sıralanmış listeler
    boykot_list = sorted(boykot.values(), key=lambda s: s.casefold())
    degil_list = sorted(boykot_degil.values(), key=lambda s: s.casefold())

    with open("dist/v1/boykot.json", "w", encoding="utf-8") as f:
        json.dump(boykot_list, f, ensure_ascii=False, indent=2)

    with open("dist/v1/boykotdegil.json", "w", encoding="utf-8") as f:
        json.dump(degil_list, f, ensure_ascii=False, indent=2)

    # 3. Birleşik JSON
    all_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "boykot": len(boykot_list),
            "boykot_degil": len(degil_list),
        },
        "boykot": boykot_list,
        "boykot_degil": degil_list,
    }
    with open("dist/v1/all.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    # 4. Hızlı arama (Lookup) sözlüğü
    lookup = {}
    for key, name in sorted(boykot.items()):
        lookup[key] = {"name": name, "status": "boykot"}
    for key, name in sorted(boykot_degil.items()):
        lookup[key] = {"name": name, "status": "boykot_degil"}

    with open("dist/v1/lookup.json", "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False, indent=2)

    # 5. Otomatik varyasyonlu txt dosyaları
    boykot_variants = sorted(
        {v for name in boykot_list for v in generate_variants(name)},
        key=lambda s: s.casefold(),
    )
    degil_variants = sorted(
        {v for name in degil_list for v in generate_variants(name)},
        key=lambda s: s.casefold(),
    )

    with open("dist/v1/boykot-variants.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(boykot_variants) + "\n")

    with open("dist/v1/boykotdegil-variants.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(degil_variants) + "\n")

    # 6. Ana sayfa (Tarayıcıdan API linkine girilirse 404 çıkmasın)
    index_html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>b0ykot API</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #222; }}
    code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
    li {{ margin: 8px 0; }}
  </style>
</head>
<body>
  <h1>b0ykot API</h1>
  <p>Açık kaynaklı boykot ve alternatif marka listesi API'si. (Boykot: <b>{len(boykot_list)}</b>, Boykot Değil: <b>{len(degil_list)}</b>)</p>
  <h2>Endpointler</h2>
  <ul>
    <li><a href="./v1/all.json"><code>/v1/all.json</code></a> — Tüm listeler (JSON)</li>
    <li><a href="./v1/lookup.json"><code>/v1/lookup.json</code></a> — Normalize edilmiş hızlı sorgu sözlüğü (JSON)</li>
    <li><a href="./v1/boykot.json"><code>/v1/boykot.json</code></a> — Boykot markaları (JSON)</li>
    <li><a href="./v1/boykotdegil.json"><code>/v1/boykotdegil.json</code></a> — Boykot olmayan markalar (JSON)</li>
    <li><a href="./boykot.txt"><code>/boykot.txt</code></a> — Orijinal boykot listesi (TXT)</li>
    <li><a href="./boykotdegil.txt"><code>/boykotdegil.txt</code></a> — Orijinal boykot değil listesi (TXT)</li>
    <li><a href="./v1/boykot-variants.txt"><code>/v1/boykot-variants.txt</code></a> — Yazım varyasyonları üretilmiş boykot listesi (TXT)</li>
  </ul>
</body>
</html>
"""
    with open("dist/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"Başarılı! Boykot: {len(boykot_list)}, Boykot Değil: {len(degil_list)}")


if __name__ == "__main__":
    main()
