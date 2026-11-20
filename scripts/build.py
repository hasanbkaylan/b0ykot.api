import json
import os
import re
import shutil
import subprocess
import unicodedata
import urllib.request
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


def parse_lines(lines: list[str]) -> dict[str, list[str]]:
    brands: dict[str, list[str]] = {}
    for line in lines:
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


def load_brands(filename: str) -> dict[str, list[str]]:
    with open(filename, "r", encoding="utf-8") as f:
        return parse_lines(f.readlines())


def pick_preferred_name(names: list[str]) -> str:
    """Aynı markanın birden fazla yazımı varsa en düzgün/aksanlı olanı seçer."""
    return max(
        names,
        key=lambda s: (
            any(ord(c) > 127 for c in s),
            any(c in "-'’ " for c in s),
            len(s),
        ),
    )


def sort_key(name: str) -> tuple[str, str]:
    return (normalize(name), name.casefold())


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
        ascii_item = item.translate(TR_ASCII_MAP)
        ascii_item = "".join(
            c
            for c in unicodedata.normalize("NFKD", ascii_item)
            if not unicodedata.combining(c)
        )
        if ascii_item:
            variants.add(ascii_item)

    return sorted(variants)


def fetch_github_commit_authors() -> dict[str, dict[str, str]]:
    """GitHub API'den commit hash -> {login, avatar_url} haritasını çeker."""
    repo = os.environ.get("GITHUB_REPOSITORY", "hasanbkaylan/b0ykot.api")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{repo}/commits?per_page=100"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "b0ykot-api-builder",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    authors: dict[str, dict[str, str]] = {}
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data:
            sha = item.get("sha")
            author = item.get("author") or item.get("committer")
            if sha and author and author.get("login"):
                authors[sha] = {
                    "login": author["login"],
                    "avatar_url": author.get("avatar_url") or f"https://github.com/{author['login']}.png?size=64",
                }
    except Exception:
        pass
    return authors


def get_commit_meta(commit_ref: str) -> tuple[str, str, str, str] | None:
    try:
        res = subprocess.run(
            ["git", "show", "-s", "--format=%H%x1f%an%x1f%ae%x1f%b", commit_ref],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None
        parts = res.stdout.strip().split("\x1f", 3)
        if len(parts) < 4:
            parts.extend([""] * (4 - len(parts)))
        return parts[0], parts[1], parts[2], parts[3]
    except Exception:
        return None


def resolve_author(
    commit_hash: str,
    subject: str,
    author_name: str,
    author_email: str,
    body: str,
    gh_authors: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Commit veya PR sahibinin kullanıcı adı ve avatar URL'sini bulur."""
    candidates = [(commit_hash, author_name, author_email, body)]

    # Merge commit ise PR'ın asıl commit'ini (^2) önceliklendir
    if subject.startswith("Merge pull request #"):
        pr_meta = get_commit_meta(f"{commit_hash}^2")
        if pr_meta:
            candidates.insert(0, pr_meta)

    for c_hash, c_name, c_email, c_body in candidates:
        # 1. Commit gövdesinde "Öneren: @kullanici" veya "Co-authored-by:" var mı?
        m_oneren = re.search(r"Öneren:\s*@([A-Za-z0-9-]+)", c_body)
        if m_oneren:
            login = m_oneren.group(1)
            return {
                "name": login,
                "login": login,
                "avatar_url": f"https://github.com/{login}.png?size=64",
            }

        m_co = re.search(r"Co-authored-by:\s*([A-Za-z0-9-]+)\s*<", c_body, re.IGNORECASE)
        if m_co and "github-actions" not in m_co.group(1).lower():
            login = m_co.group(1)
            return {
                "name": login,
                "login": login,
                "avatar_url": f"https://github.com/{login}.png?size=64",
            }

        # 2. GitHub API eşleşmesi
        gh = gh_authors.get(c_hash)
        if gh and "github-actions" not in gh["login"].lower():
            return {
                "name": c_name if c_name and "github-actions" not in c_name.lower() else gh["login"],
                "login": gh["login"],
                "avatar_url": gh["avatar_url"],
            }

        # 3. GitHub noreply e-postasından çıkar
        m_noreply = re.match(r"^(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$", c_email.strip(), re.IGNORECASE)
        if m_noreply and "github-actions" not in m_noreply.group(1).lower():
            login = m_noreply.group(1)
            return {
                "name": c_name or login,
                "login": login,
                "avatar_url": f"https://github.com/{login}.png?size=64",
            }

    # 4. Merge commit başlığından ("from kullanici/branch") çıkar
    m_merge = re.search(r"from\s+([A-Za-z0-9-]+)/", subject)
    if m_merge and "github-actions" not in m_merge.group(1).lower():
        login = m_merge.group(1)
        return {
            "name": login,
            "login": login,
            "avatar_url": f"https://github.com/{login}.png?size=64",
        }

    # 5. Varsayılan repo sahibi (yerel/bilinmeyen commitler için)
    fallback_login = "hasanbkaylan"
    clean_name = author_name if author_name and "github-actions" not in author_name.lower() else fallback_login
    return {
        "name": clean_name,
        "login": fallback_login,
        "avatar_url": f"https://github.com/{fallback_login}.png?size=64",
    }


def get_git_brands_at(commit_ref: str, filename: str) -> dict[str, str]:
    try:
        res = subprocess.run(
            ["git", "show", f"{commit_ref}:{filename}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if res.returncode != 0:
            return {}
        parsed = parse_lines(res.stdout.splitlines())
        return {k: pick_preferred_name(v) for k, v in parsed.items()}
    except Exception:
        return {}


def build_history(limit: int = 40) -> list[dict]:
    """Git geçmişinden tarih tarih marka ekleme/çıkarma ve yazar bilgilerini oluşturur."""
    updates: list[dict] = []
    gh_authors = fetch_github_commit_authors()
    try:
        res = subprocess.run(
            [
                "git", "log", f"-n{limit}",
                "--format=%H%x1f%aI%x1f%s%x1f%an%x1f%ae%x1f%b%x1e",
                "--", "boykot.txt", "boykotdegil.txt",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return updates

        for record in res.stdout.split("\x1e"):
            record = record.strip()
            if not record:
                continue
            parts = record.split("\x1f", 5)
            if len(parts) < 5:
                continue
            while len(parts) < 6:
                parts.append("")
            commit_hash, commit_date, message, author_name, author_email, body = parts

            cur_b = get_git_brands_at(commit_hash, "boykot.txt")
            prev_b = get_git_brands_at(f"{commit_hash}^", "boykot.txt")

            cur_d = get_git_brands_at(commit_hash, "boykotdegil.txt")
            prev_d = get_git_brands_at(f"{commit_hash}^", "boykotdegil.txt")

            b_added = sorted((cur_b[k] for k in (set(cur_b) - set(prev_b))), key=sort_key)
            b_removed = sorted((prev_b[k] for k in (set(prev_b) - set(cur_b))), key=sort_key)

            d_added = sorted((cur_d[k] for k in (set(cur_d) - set(prev_d))), key=sort_key)
            d_removed = sorted((prev_d[k] for k in (set(prev_d) - set(cur_d))), key=sort_key)

            if not (b_added or b_removed or d_added or d_removed):
                continue

            author_info = resolve_author(
                commit_hash, message, author_name, author_email, body, gh_authors
            )

            updates.append({
                "hash": commit_hash[:7],
                "date": commit_date,
                "message": message,
                "author": author_info,
                "boykot": {
                    "added": b_added,
                    "removed": b_removed,
                },
                "boykot_degil": {
                    "added": d_added,
                    "removed": d_removed,
                },
            })
    except Exception:
        return []

    return updates


def main():
    boykot_raw = load_brands("boykot.txt")
    degil_raw = load_brands("boykotdegil.txt")

    boykot = {k: pick_preferred_name(v) for k, v in boykot_raw.items()}
    boykot_degil = {k: pick_preferred_name(v) for k, v in degil_raw.items()}

    conflicts = set(boykot.keys()) & set(boykot_degil.keys())
    if conflicts:
        conflict_names = [f"{boykot[k]} / {boykot_degil[k]}" for k in sorted(conflicts)]
        raise ValueError(
            "HATA: Hem boykot.txt hem boykotdegil.txt içinde bulunan markalar var:\n- "
            + "\n- ".join(conflict_names)
        )

    boykot_list = sorted(boykot.values(), key=sort_key)
    degil_list = sorted(boykot_degil.values(), key=sort_key)

    # 1. Kaynak .txt dosyalarını klonlardan temizleyip sıralı şekilde güncelle
    with open("boykot.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(boykot_list) + "\n")

    with open("boykotdegil.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(degil_list) + "\n")

    os.makedirs("dist/v1", exist_ok=True)

    shutil.copyfile("boykot.txt", "dist/boykot.txt")
    shutil.copyfile("boykotdegil.txt", "dist/boykotdegil.txt")

    # 2. JSON listeleri
    with open("dist/v1/boykot.json", "w", encoding="utf-8") as f:
        json.dump(boykot_list, f, ensure_ascii=False, indent=2)

    with open("dist/v1/boykotdegil.json", "w", encoding="utf-8") as f:
        json.dump(degil_list, f, ensure_ascii=False, indent=2)

    now_iso = datetime.now(timezone.utc).isoformat()

    # 3. Birleşik JSON
    all_data = {
        "updated_at": now_iso,
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
        {v for names in boykot_raw.values() for name in names for v in generate_variants(name)},
        key=sort_key,
    )
    degil_variants = sorted(
        {v for names in degil_raw.values() for name in names for v in generate_variants(name)},
        key=sort_key,
    )

    with open("dist/v1/boykot-variants.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(boykot_variants) + "\n")

    with open("dist/v1/boykotdegil-variants.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(degil_variants) + "\n")

    # 6. Güncelleme geçmişi (History JSON)
    history_data = {
        "updated_at": now_iso,
        "updates": build_history(),
    }
    with open("dist/v1/history.json", "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    # 7. Web arayüzünü kopyala
    shutil.copyfile("templates/index.html", "dist/index.html")

    print(
        f"Başarılı! Boykot: {len(boykot_list)} ({len(boykot_variants)} varyasyon), "
        f"Boykot Değil: {len(degil_list)} ({len(degil_variants)} varyasyon), "
        f"Geçmiş kaydı: {len(history_data['updates'])}"
    )


if __name__ == "__main__":
    main()
