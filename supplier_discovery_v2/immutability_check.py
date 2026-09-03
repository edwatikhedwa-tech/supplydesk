from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def protected_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for name in (".env", ".env.example", ".env.local", ".env.production.local", "stop_domains.txt"):
        candidate = root / name
        if candidate.is_file():
            paths.append(candidate)
    for name in ("serp_parser.py", "supplier_app.py", "collect_inn.py"):
        candidate = root / name
        if candidate.is_file():
            paths.append(candidate)
    # Moved out of the flat root package by TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902.
    checko_client = root / "backend" / "integrations" / "registry" / "checko_client.py"
    if checko_client.is_file():
        paths.append(checko_client)
    # Moved out of the flat root package by TASK-BOUNDED-ROOT-REFACTOR-SUPPLIER-IDENTITY-20260902.
    # inn_resolver.py deliberately stays unprotected — it was never in the
    # protected set before this move, and moving beside these three files is
    # not itself evidence for adding it.
    for name in ("email_extractor.py", "inn_extractor.py", "verify.py"):
        candidate = root / "backend" / "domain" / "supplier_identity" / name
        if candidate.is_file():
            paths.append(candidate)
    # Moved out of the flat root package by TASK-BOUNDED-ROOT-REFACTOR-SEARCH-INTEGRATIONS-20260903.
    for name in ("web_lookup.py", "xmlriver_client.py"):
        candidate = root / "backend" / "integrations" / "search" / name
        if candidate.is_file():
            paths.append(candidate)
    # Moved out of the flat root package by
    # TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-CONTACT-CRAWLER-20260903.
    contact_crawler = root / "backend" / "domain" / "supplier_enrichment" / "contact_crawler.py"
    if contact_crawler.is_file():
        paths.append(contact_crawler)
    # Extracted from collect_inn.py's protected content (the deterministic
    # ИНН/ОГРН parsing logic) by
    # TASK-BOUNDED-ROOT-REFACTOR-ENRICHMENT-COLLECT-INN-SPLIT-20260903;
    # collect_inn.py itself stays protected at root as the thinned CLI.
    pipeline = root / "backend" / "domain" / "supplier_enrichment" / "pipeline.py"
    if pipeline.is_file():
        paths.append(pipeline)
    repository = root / "mail" / "repository.py"
    if repository.is_file():
        paths.append(repository)
    migration_dir = root / "migrations"
    if migration_dir.is_dir():
        paths.extend(sorted(migration_dir.glob("*.sql")))
    return sorted(set(paths))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root: Path) -> dict[str, object]:
    files = {str(path.relative_to(root)).replace("\\", "/"): _sha256(path) for path in protected_paths(root)}
    return {"files": files}


def write_baseline(root: Path, manifest: Path) -> None:
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), **snapshot(root)}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify(root: Path, manifest: Path) -> list[str]:
    expected = json.loads(manifest.read_text(encoding="utf-8")).get("files", {})
    actual = snapshot(root).get("files", {})
    changed: list[str] = []
    for name in sorted(set(expected) | set(actual)):
        if expected.get(name) != actual.get(name):
            changed.append(name)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that current parser/config files were not changed.")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parent / "protected_manifest.json")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.write_baseline:
        write_baseline(root, args.manifest)
        print(f"baseline_written={args.manifest}")
        return 0
    if not args.manifest.exists():
        print("baseline_missing")
        return 2
    changed = verify(root, args.manifest)
    if changed:
        print("protected_files_changed=" + ",".join(changed))
        return 1
    print(f"protected_files_unchanged={len(snapshot(root)['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
