import platform
import socket
import time
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

import psutil

WARN_PERCENT = 85
BAD_PERCENT = 95


@dataclass
class Finding:
    check: str                  # which check produced this
    severity: str               # "ok", "warn" or "bad"
    summary: str                # one readable line
    evidence: dict = field(default_factory=dict)   # the raw numbers behind it


# ---------- rules: plain functions, easy to test ----------

def judge_usage(percent: float) -> str:
    if percent >= BAD_PERCENT:
        return "bad"
    if percent >= WARN_PERCENT:
        return "warn"
    return "ok"


def judge_network(adapter_up: bool, internet_ok: bool, dns_ok: bool) -> tuple[str, str]:
    if not adapter_up:
        return "bad", "No active network adapter (Wi-Fi or Ethernet is off or disconnected)"
    if not internet_ok and not dns_ok:
        return "bad", "Adapter is up but there is no internet access"
    if internet_ok and not dns_ok:
        return "bad", "Internet works but DNS lookups fail (DNS problem)"
    if not internet_ok:
        return "bad", "DNS works but the internet is unreachable"
    return "ok", "Network is healthy"


# ---------- checks: look at the real machine ----------

def check_system() -> Finding:
    uptime_days = round((time.time() - psutil.boot_time()) / 86400, 1)
    return Finding(
        "system",
        "warn" if uptime_days > 14 else "ok",
        f"{platform.system()} {platform.release()}, up {uptime_days} days",
        {"os": platform.platform(), "cpu_cores": psutil.cpu_count(),
         "ram_gb": round(psutil.virtual_memory().total / 1e9, 1),
         "uptime_days": uptime_days},
    )


def check_cpu() -> Finding:
    percent = psutil.cpu_percent(interval=1)
    return Finding("cpu", judge_usage(percent), f"CPU at {percent}%", {"percent": percent})


def check_memory() -> Finding:
    mem = psutil.virtual_memory()
    return Finding("memory", judge_usage(mem.percent), f"Memory at {mem.percent}%",
                   {"percent": mem.percent, "free_gb": round(mem.available / 1e9, 1)})


def check_disks() -> list[Finding]:
    findings = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue                      # empty card readers, optical drives
        findings.append(Finding(
            "disk", judge_usage(usage.percent),
            f"{part.mountpoint} is {usage.percent}% full",
            {"mount": part.mountpoint, "percent": usage.percent,
             "free_gb": round(usage.free / 1e9, 1)},
        ))
    return findings


def check_network() -> Finding:
    stats = psutil.net_if_stats()
    active = [n for n, s in stats.items()
              if s.isup and n != "lo" and "loopback" not in n.lower()]

    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3).close()
        internet_ok = True
    except OSError:
        internet_ok = False

    try:
        socket.gethostbyname("example.com")
        dns_ok = True
    except OSError:
        dns_ok = False

    severity, summary = judge_network(bool(active), internet_ok, dns_ok)
    return Finding("network", severity, summary,
                   {"active_adapters": active, "internet_ok": internet_ok, "dns_ok": dns_ok})

def check_top_processes(n: int = 5) -> Finding:
    totals = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            mem = p.info["memory_info"]
            if mem:
                name = p.info["name"] or "unknown"
                totals[name] = totals.get(name, 0) + mem.rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    top = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:n]
    top_list = [{"name": name, "memory_gb": round(rss / 1e9, 2)} for name, rss in top]
    summary = (f"Biggest memory user: {top_list[0]['name']} ({top_list[0]['memory_gb']} GB)"
               if top_list else "No process data available")
    return Finding("processes", "ok", summary, {"top_memory": top_list})

CHECKS_BY_CATEGORY = {
    "network":     [check_network],
    "storage":     [check_disks],
    "performance": [check_cpu, check_memory, check_disks, check_system],
    "general":     [check_system, check_cpu, check_memory, check_disks],
    "performance": [check_cpu, check_memory, check_top_processes, check_disks, check_system],
}


def run_for(category: str) -> list[Finding]:
    checks = CHECKS_BY_CATEGORY.get(category, CHECKS_BY_CATEGORY["general"])
    findings = []
    with ThreadPoolExecutor() as pool:
        for result in pool.map(lambda check: check(), checks):
            findings.extend(result if isinstance(result, list) else [result])
    return findings


if __name__ == "__main__":
    import sys
    category = sys.argv[1] if len(sys.argv) > 1 else "general"
    for f in run_for(category):
        print(f"[{f.severity.upper():4}] {f.check:8} {f.summary}")
        print("        evidence:", f.evidence)
