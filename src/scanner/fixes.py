import os
import subprocess
import tempfile
import time
from pathlib import Path


# ---------- the fixes themselves ----------

def _old_temp_files(older_than_days: int = 1):
    root = Path(tempfile.gettempdir())
    if not any(s in str(root).lower() for s in ("temp", "tmp")):
        raise RuntimeError(f"refusing to clean unexpected folder: {root}")
    cutoff = time.time() - older_than_days * 86400
    for path in root.rglob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                yield path, path.stat().st_size
        except OSError:
            continue


def clean_temp(dry_run: bool = True) -> dict:
    files = freed = 0
    for path, size in _old_temp_files():
        if not dry_run:
            try:
                path.unlink()
            except OSError:
                continue            # in use or protected: skip it
        files += 1
        freed += size
    return {"files": files, "freed_mb": round(freed / 1e6, 1), "dry_run": dry_run}


def flush_dns() -> dict:
    out = subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                         text=True, timeout=15)
    return {"returncode": out.returncode, "output": out.stdout.strip()}


FIXES = {"clean_temp", "flush_dns"}      # the allowlist


def run_fix(fix_id: str, dry_run: bool = True) -> dict:
    if fix_id not in FIXES:
        raise ValueError(f"unknown fix '{fix_id}'")
    if fix_id == "clean_temp":
        return clean_temp(dry_run=dry_run)
    if dry_run:
        return {"fix": fix_id, "dry_run": True}
    return flush_dns()


# ---------- choosing which fixes to suggest ----------

def _rank(finding: dict) -> int:
    return 0 if finding["severity"] == "bad" else 1


def suggest_fixes(findings: list[dict], limit: int = 2) -> list[dict]:
    system_drive = (os.environ.get("SystemDrive", "C:") + "\\").upper()
    top_apps = next((f["evidence"].get("top_memory", [])
                     for f in findings if f["check"] == "processes"), [])
    candidates = []

    for f in findings:
        problem = f["severity"] in ("warn", "bad")

        if f["check"] == "disk" and problem and \
                f["evidence"].get("mount", "").upper() == system_drive:
            candidates.append((_rank(f), {
                "id": "clean_temp", "automatic": True, "risk": "low",
                "title": "Delete temporary files older than 1 day",
                "why": f["summary"]}))

        if f["check"] == "network" and f["evidence"].get("internet_ok") \
                and not f["evidence"].get("dns_ok"):
            candidates.append((_rank(f), {
                "id": "flush_dns", "automatic": True, "risk": "low",
                "title": "Flush the DNS cache",
                "why": f["summary"]}))

        if f["check"] == "memory" and problem and top_apps:
            app = top_apps[0]
            candidates.append((_rank(f), {
                "id": "close_app", "automatic": False, "risk": "medium",
                "title": f"Close {app['name']} (using {app['memory_gb']} GB). "
                         "Save your work first.",
                "why": f["summary"]}))

    candidates.sort(key=lambda c: c[0])
    seen, result = set(), []
    for _, fix in candidates:
        if fix["id"] not in seen:
            seen.add(fix["id"])
            result.append(fix)
    return result[:limit]


FIX_CHECK = {"clean_temp": "storage", "flush_dns": "network"}

_SEVERITY_RANK = {"ok": 0, "warn": 1, "bad": 2}


def _key(finding: dict) -> tuple:
    
    return (finding["check"], finding["evidence"].get("mount", ""))


def compare_findings(before: list[dict], after: list[dict]) -> list[dict]:
    after_by_key = {_key(f): f for f in after}
    rows = []
    for old in before:
        new = after_by_key.get(_key(old))
        if new is None:
            continue                  
        change = _SEVERITY_RANK[new["severity"]] - _SEVERITY_RANK[old["severity"]]
        rows.append({
            "check": old["check"],
            "before": old["summary"],
            "after": new["summary"],
            "result": "improved" if change < 0 else "worse" if change > 0 else "same",
        })
    return rows