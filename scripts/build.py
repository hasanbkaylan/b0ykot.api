import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone

TR_ASCII_MAP = str.maketrans({
    "ç": "c", "Ç": "C",
    "ğ": "g", "Ğ": "G",
    "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O",
    "ş": "s", "Ş": "S",
    "ü": "u", "Ü": "U",
    "é": "e", "É": "E",
})


def normalize(text: str) -> str:
    """Marka adını aksansız, boşluksuz ve küçük harfli standart anahtara çevirir."""
    text = text.translate(TR_ASCII_MAP).replace("I", "i").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text)


def load_brands(filename: str) -> dict[str, list[str]]:
    """Aynı markanın dosyadaki tüm farklı yazımlarını kaybetmeden toplar."""
    brands: dict[str, list[str]] = {}
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            key = normalize(raw)
            if not key:
                continue
            if key not in brands:
                brands[key] = []
            if raw not in brands[key]:
                brands[key].append(raw)
    return brands


def pick_preferred_name(names: list[str]) -> str:
    """Aynı markanın birden fazla yazımı varsa en düzgün/aksanlı olanı ana isim seçer."""
    return max(
        names,
        key=lambda s: (
            any(ord(c) > 127 for c in s),
            any(c in "-'’ " for c in s),
            len(s),
        ),
    )


def generate_variants(name: str) -> list[str]:
    """Türkçe karakterli, aksansız, tireli, boşluklu ve kesme işaretsiz varyasyonlar üretir."""
    normalized_quote = name.replace("’", "'")
    bases = {
        name,
        normalized_quote,
        name.replace("-", " "),
        name.replace("-", ""),
        normalized_quote.replace("'", ""),
        normalized_quote.replace("-", " ").replace("'", ""),
        normalized_quote.replace("-", "").replace("'", ""),
    }

    variants = set()
    for item in bases:
        if not item:
            continue
        variants.add(item)
        # Türkçe karakterleri ve aksanları temizle (ç->c, ş->s, ğ->g, ü->u, ö->o, ı->i, é->e)
        ascii_item = item.translate(TR_ASCII_MAP)
        ascii_item = "".join(
            c
            for c in unicodedata.normalize("NFKD", ascii_item)
            if not unicodedata.combining(c)
        )
        if ascii_item:
            variants.add(ascii_item)

    return sorted(variants)


def main():
    boykot_raw = load_brands("boykot.txt")
    degil_raw = load_brands("boykotdegil.txt")

    boykot = {k: pick_preferred_name(v) for k, v in boykot_raw.items()}
    boykot_degil = {k: pick_preferred_name(v) for k, v in degil_raw.items()}

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

    # 5. Otomatik varyasyonlu txt dosyaları (Dosyadaki tüm yazımları da kapsar)
    boykot_variants = sorted(
        {v for names in boykot_raw.values() for name in names for v in generate_variants(name)},
        key=lambda s: s.casefold(),
    )
    degil_variants = sorted(
        {v for names in degil_raw.values() for name in names for v in generate_variants(name)},
        key=lambda s: s.casefold(),
    )

    with open("dist/v1/boykot-variants.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(boykot_variants) + "\n")

    with open("dist/v1/boykotdegil-variants.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(degil_variants) + "\n")

    # 6. Ana sayfa şablonunu kopyala
    shutil.copyfile("templates/index.html", "dist/index.html")

    print(
        f"Başarılı! Boykot: {len(boykot_list)} ({len(boykot_variants)} varyasyon), "
        f"Boykot Değil: {len(degil_list)} ({len(degil_variants)} varyasyon)"
    )


if __name__ == "__main__":
    main()
