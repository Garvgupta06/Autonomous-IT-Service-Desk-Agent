import ctypes
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from src.scanner.checks import (read_device_problems, read_driver_updates, run_powershell,
                                DRIVER_SEARCH, MAX_DRIVER_INSTALLS)


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


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):     # not Windows
        return False


def enable_devices(dry_run: bool = True) -> dict:
    """Enable devices that are disabled. Only the classes listed in
    checks.DEVICE_CLASSES are ever touched. Driverless devices are left alone."""
    targets = [d for d in read_device_problems() if d["reason"] == "disabled"]
    if dry_run:
        return {"would_enable": [d["name"] for d in targets], "dry_run": True}
    if not _is_admin():
        raise PermissionError("Enabling a device needs administrator rights. "
                              "Restart the backend from an administrator terminal.")
    enabled, failed = [], []
    for d in targets:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Enable-PnpDevice -InstanceId $env:PNP_ID -Confirm:$false -ErrorAction Stop"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PNP_ID": d["id"]})     # id from Windows, never from the user
        (enabled if out.returncode == 0 else failed).append(d["name"])
    return {"enabled": enabled, "failed": failed, "dry_run": False}


_PS_INSTALL_DRIVERS = """
$ErrorActionPreference = 'Stop'
$s = New-Object -ComObject Microsoft.Update.Session
$found = $s.CreateUpdateSearcher().Search("__SEARCH__").Updates
$todo = New-Object -ComObject Microsoft.Update.UpdateColl
foreach ($u in $found) {
  if ($todo.Count -ge __MAX__) { break }
  if ($u.EulaAccepted -and $u.DriverClass -ne 'Firmware') { [void]$todo.Add($u) }
}
$names = @(); $reboot = $false
if ($todo.Count -gt 0) {
  $d = $s.CreateUpdateDownloader(); $d.Updates = $todo; [void]$d.Download()
  $i = $s.CreateUpdateInstaller(); $i.Updates = $todo; $res = $i.Install()
  $reboot = [bool]$res.RebootRequired
  for ($k = 0; $k -lt $todo.Count; $k++) {
    if ($res.GetUpdateResult($k).ResultCode -eq 2) { $names += $todo.Item($k).Title }
  }
}
@{ installed = $names; reboot = $reboot } | ConvertTo-Json -Compress
""".replace("__SEARCH__", DRIVER_SEARCH).replace("__MAX__", str(MAX_DRIVER_INSTALLS))


def update_drivers(dry_run: bool = True) -> dict:
    """Install driver updates offered by Windows Update (at most MAX_DRIVER_INSTALLS
    per run). Never accepts licence terms. Needs administrator rights."""
    titles = [u["title"] for u in read_driver_updates()
              if u["class"] != "Firmware"][:MAX_DRIVER_INSTALLS]     # firmware is never installed
    if dry_run:
        return {"would_install": titles, "dry_run": True}
    if not _is_admin():
        raise PermissionError("Installing drivers needs administrator rights. "
                              "Restart the backend from an administrator terminal.")
    out = run_powershell(_PS_INSTALL_DRIVERS, timeout=1800)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:200] or "driver install failed")
    lines = out.stdout.strip().splitlines()
    data = json.loads(lines[-1]) if lines else {}
    installed = data.get("installed") or []
    if isinstance(installed, str):
        installed = [installed]
    return {"installed": installed, "reboot_required": bool(data.get("reboot")),
            "dry_run": False}


FIXES = {"clean_temp", "flush_dns", "enable_devices", "update_drivers"}      # the allowlist


def run_fix(fix_id: str, dry_run: bool = True) -> dict:
    if fix_id not in FIXES:
        raise ValueError(f"unknown fix '{fix_id}'")
    if fix_id == "clean_temp":
        return clean_temp(dry_run=dry_run)
    if fix_id == "enable_devices":
        return enable_devices(dry_run=dry_run)
    if fix_id == "update_drivers":
        return update_drivers(dry_run=dry_run)
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

        if f["check"] == "devices" and f["evidence"].get("problems"):
            disabled = [p["name"] for p in f["evidence"]["problems"]
                        if p["reason"] == "disabled"]
            no_driver = [p["name"] for p in f["evidence"]["problems"]
                         if p["reason"] != "disabled"]
            if disabled:
                candidates.append((_rank(f), {
                    "id": "enable_devices", "automatic": True, "risk": "low",
                    "title": "Enable the disabled device: " + ", ".join(disabled)
                             + " (needs administrator rights)",
                    "why": f["summary"]}))
            if no_driver:
                candidates.append((_rank(f), {
                    "id": "install_driver", "automatic": False, "risk": "medium",
                    "title": "Reinstall the driver for " + ", ".join(no_driver)
                             + " from Windows Update or the manufacturer",
                    "why": f["summary"]}))

        if f["check"] == "drivers" and f["evidence"].get("updates"):
            ups = f["evidence"]["updates"]
            installable = [u for u in ups if u["class"] != "Firmware"]
            firmware = [u["title"] for u in ups if u["class"] == "Firmware"]
            if installable:
                n = min(len(installable), MAX_DRIVER_INSTALLS)
                candidates.append((_rank(f), {
                    "id": "update_drivers", "automatic": True, "risk": "medium",
                    "title": f"Install {n} driver update(s) from Windows Update "
                             "(needs administrator rights, can take several minutes, "
                             "may need a restart)",
                    "why": f["summary"]}))
            if firmware:
                candidates.append((_rank(f), {
                    "id": "firmware_update", "automatic": False, "risk": "high",
                    "title": "Firmware update available (" + ", ".join(firmware)
                             + "). Install it with the manufacturer's own tool while "
                             "plugged in to power. The agent never installs firmware.",
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


FIX_CHECK = {"clean_temp": "storage", "flush_dns": "network", "enable_devices": "device",
             "update_drivers": "drivers"}

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