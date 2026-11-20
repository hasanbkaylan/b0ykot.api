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

    # 6. Ana sayfa şablonunu kopyala
    shutil.copyfile("templates/index.html", "dist/index.html")

    print(f"Başarılı! Boykot: {len(boykot_list)}, Boykot Değil: {len(degil_list)}")


if __name__ == "__main__":
    main()
