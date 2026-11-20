import os
import subprocess
import sys
import time
from pathlib import Path

# build.py içindeki yardımcı fonksiyonları kullan
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import load_brands, normalize, pick_preferred_name, sort_key


def parse_issue_sections(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_header = None
    for line in body.replace("\r\n", "\n").splitlines():
        if line.startswith("### "):
            current_header = line[4:].strip()
            sections[current_header] = []
        elif current_header is not None:
            sections[current_header].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def run_cmd(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def comment_on_issue(issue_number: str, message: str):
    run_cmd(["gh", "issue", "comment", issue_number, "--body", message], check=False)


def main():
    issue_number = os.environ.get("ISSUE_NUMBER", "").strip()
    issue_author = os.environ.get("ISSUE_AUTHOR", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    default_branch = os.environ.get("DEFAULT_BRANCH", "main").strip() or "main"

    if not issue_number or not issue_body:
        print("Issue bilgisi bulunamadı.")
        return

    sections = parse_issue_sections(issue_body)
    target_file = sections.get("Hedef Liste", "").strip().lower()
    if target_file in ("boykot", "boykotdegil"):
        target_file += ".txt"

    brands_raw = sections.get("Eklenecek Markalar", "")
    source_note = sections.get("Kaynak / Açıklama", "").strip()

    if target_file not in ("boykot.txt", "boykotdegil.txt"):
        comment_on_issue(
            issue_number,
            "Hedef liste `boykot.txt` veya `boykotdegil.txt` olmalıdır.",
        )
        return

    other_file = "boykotdegil.txt" if target_file == "boykot.txt" else "boykot.txt"

    target_map = {k: pick_preferred_name(v) for k, v in load_brands(target_file).items()}
    other_map = {k: pick_preferred_name(v) for k, v in load_brands(other_file).items()}

    added = []
    skipped_existing = []
    skipped_conflict = []
    seen_new = set()

    for line in brands_raw.splitlines():
        brand = line.strip()
        if not brand or brand.startswith("```") or brand == "_No response_":
            continue
        key = normalize(brand)
        if not key or key in seen_new:
            continue
        seen_new.add(key)

        if key in target_map:
            skipped_existing.append(brand)
        elif key in other_map:
            skipped_conflict.append(f"{brand} (karşı listede: {other_map[key]})")
        else:
            target_map[key] = brand
            added.append(brand)

    if not added:
        lines = ["Otomatik PR oluşturulmadı çünkü eklenecek yeni bir marka bulunamadı."]
        if skipped_existing:
            lines.append(f"- Zaten listede olanlar: {', '.join(skipped_existing[:15])}")
        if skipped_conflict:
            lines.append(f"- Karşı listeyle çakışanlar: {', '.join(skipped_conflict[:15])}")
        comment_on_issue(issue_number, "\n".join(lines))
        return

    updated_list = sorted(target_map.values(), key=sort_key)
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("\n".join(updated_list) + "\n")

    branch_name = f"toplu-oneri-{issue_number}-{int(time.time())}"
    run_cmd(["git", "config", "user.name", "github-actions[bot]"])
    run_cmd(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    run_cmd(["git", "checkout", "-b", branch_name])
    run_cmd(["git", "add", target_file])

    commit_title = f"feat: #{issue_number} toplu marka önerisi ({len(added)} marka)"
    commit_cmd = ["git", "commit", "-m", commit_title]
    if issue_author:
        commit_body = (
            f"Öneren: @{issue_author}\n\n"
            f"Co-authored-by: {issue_author} <{issue_author}@users.noreply.github.com>"
        )
        commit_cmd.extend(["-m", commit_body])
    run_cmd(commit_cmd)
    run_cmd(["git", "push", "-u", "origin", branch_name])

    pr_lines = [
        f"Closes #{issue_number}",
        "",
        f"**Öneren:** @{issue_author}",
        f"**Hedef Liste:** `{target_file}`",
        f"**Eklenen Marka Sayısı:** {len(added)}",
        "",
        "### Eklenen Markalar",
        *[f"- {b}" for b in added],
    ]
    if source_note and source_note != "_No response_":
        pr_lines.extend(["", "### Kaynak / Açıklama", source_note])
    if skipped_conflict:
        pr_lines.extend(["", "### Çakışma Nedeniyle Atlananlar", *[f"- {c}" for c in skipped_conflict]])

    pr_body_path = Path("/tmp/pr_body.md")
    pr_body_path.write_text("\n".join(pr_lines), encoding="utf-8")

    pr_res = run_cmd([
        "gh", "pr", "create",
        "--base", default_branch,
        "--head", branch_name,
        "--title", f"feat({target_file}): {len(added)} yeni marka (#{issue_number})",
        "--body-file", str(pr_body_path),
    ])
    pr_url = pr_res.stdout.strip()
    comment_on_issue(
        issue_number,
        f"✅ **{len(added)} marka** için otomatik Pull Request oluşturuldu: {pr_url}",
    )


if __name__ == "__main__":
    main()
