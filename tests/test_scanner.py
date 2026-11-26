from src.scanner import checks, fixes
from src.scanner.checks import judge_usage, judge_network, parse_device_problems
import pytest
from src.scanner.fixes import suggest_fixes, run_fix, clean_temp


def test_usage_levels():
    assert judge_usage(50) == "ok"
    assert judge_usage(90) == "warn"
    assert judge_usage(97) == "bad"


def test_no_adapter():
    assert judge_network(False, False, False)[0] == "bad"


def test_dns_only_failure():
    severity, summary = judge_network(True, True, False)
    assert severity == "bad" and "DNS" in summary


def test_no_internet():
    severity, summary = judge_network(True, False, False)
    assert severity == "bad" and "no internet" in summary.lower()


def test_healthy_network():
    assert judge_network(True, True, True)[0] == "ok"

def finding(check, severity, summary="x", **evidence):
    return {"check": check, "severity": severity, "summary": summary, "evidence": evidence}


def test_full_system_drive_suggests_clean_temp():
    findings = [finding("disk", "warn", "C:\\ is 93% full", mount="C:\\", percent=93)]
    assert suggest_fixes(findings)[0]["id"] == "clean_temp"


def test_dns_failure_suggests_flush():
    findings = [finding("network", "bad", internet_ok=True, dns_ok=False)]
    assert suggest_fixes(findings)[0]["id"] == "flush_dns"


def test_memory_pressure_gives_manual_advice_naming_the_app():
    findings = [finding("memory", "bad", "Memory at 94%"),
                finding("processes", "ok", top_memory=[{"name": "brave.exe", "memory_gb": 6.5}])]
    fix = suggest_fixes(findings)[0]
    assert fix["id"] == "close_app"
    assert fix["automatic"] is False
    assert "brave.exe" in fix["title"]


def test_healthy_machine_suggests_nothing():
    assert suggest_fixes([finding("disk", "ok", mount="C:\\"), finding("memory", "ok")]) == []


def test_never_more_than_two_suggestions():
    findings = [
        finding("disk", "warn", mount="C:\\"),
        finding("network", "bad", internet_ok=True, dns_ok=False),
        finding("memory", "bad"),
        finding("processes", "ok", top_memory=[{"name": "a.exe", "memory_gb": 1}]),
    ]
    assert len(suggest_fixes(findings)) == 2


def test_unknown_fix_is_rejected():
    with pytest.raises(ValueError):
        run_fix("format_disk")


def test_dry_run_deletes_nothing():
    assert clean_temp(dry_run=True)["dry_run"] is True

def test_compare_findings_detects_improvement():
    from src.scanner.fixes import compare_findings
    before = [{"check": "disk", "severity": "bad", "summary": "C:\\ is 96% full",
               "evidence": {"mount": "C:\\"}},
              {"check": "cpu", "severity": "ok", "summary": "CPU at 10%", "evidence": {}}]
    after = [{"check": "disk", "severity": "ok", "summary": "C:\\ is 70% full",
              "evidence": {"mount": "C:\\"}}]
    rows = compare_findings(before, after)
    assert len(rows) == 1                 # cpu was not re-run, so it is skipped
    assert rows[0]["result"] == "improved"


def test_runbook_lookup_never_raises(monkeypatch):
    import backend.rag.service as svc
    def boom(*a, **k): raise RuntimeError("ollama down")
    monkeypatch.setattr(svc, "retrieve", boom)
    from src.orchestrator.knowledge import get_runbook_chunks
    assert isinstance(get_runbook_chunks("vpn error 691"), list)   # falls back, never raises


def test_rag_node_without_runbooks_asks_for_a_ticket(monkeypatch):
    from src.orchestrator import knowledge
    monkeypatch.setattr(knowledge, "get_runbook_chunks", lambda *a, **k: [])
    out = knowledge.rag_node({"user_message": "anything"})
    assert "ticket" in out["response"].lower()

def test_internet_ok_when_only_port_443_is_reachable(monkeypatch):
    from types import SimpleNamespace
    from src.scanner import checks
    monkeypatch.setattr(checks.psutil, "net_if_stats",
                        lambda: {"Wi-Fi": SimpleNamespace(isup=True)})
    monkeypatch.setattr(checks, "_can_connect", lambda host, port, timeout=3: port == 443)
    monkeypatch.setattr(checks, "_https_ok", lambda: False)
    monkeypatch.setattr(checks.socket, "gethostbyname", lambda host: "93.184.216.34")
    assert checks.check_network().severity == "ok"


# ---------- devices ----------

BLUETOOTH_OFF = {"FriendlyName": "Intel Wireless Bluetooth", "Class": "Bluetooth",
                 "InstanceId": "USB\\VID_8087", "Problem": "CM_PROB_DISABLED"}


def test_harmless_nvidia_and_amd_entries_are_ignored():
    rows = [
        {"FriendlyName": "NVIDIA Platform Controllers and Framework", "Class": "SoftwareDevice",
         "Problem": "CM_PROB_FAILED_ADD"},
        {"FriendlyName": "AMD LOG", "Class": "System", "Problem": "CM_PROB_NONE"},
    ]
    assert parse_device_problems(rows) == []


def test_disabled_bluetooth_is_found_from_name_or_numeric_code():
    assert parse_device_problems([BLUETOOTH_OFF])[0]["reason"] == "disabled"
    as_number = {**BLUETOOTH_OFF, "Problem": 22}
    assert parse_device_problems(as_number)[0]["reason"] == "disabled"   # single object, not a list


def test_unreadable_device_list_is_a_warning_not_a_crash(monkeypatch):
    monkeypatch.setattr(checks.platform, "system", lambda: "Windows")
    def boom(): raise OSError("no powershell")
    monkeypatch.setattr(checks, "read_device_problems", boom)
    assert checks.check_devices().severity == "warn"


def test_device_check_skips_non_windows(monkeypatch):
    monkeypatch.setattr(checks.platform, "system", lambda: "Linux")
    assert checks.check_devices().severity == "ok"


def test_disabled_device_suggests_enable_with_name_and_admin_note():
    problems = parse_device_problems([BLUETOOTH_OFF])
    fix = suggest_fixes([finding("devices", "bad", problems=problems)])[0]
    assert fix["id"] == "enable_devices" and fix["automatic"] is True
    assert "Intel Wireless Bluetooth" in fix["title"] and "administrator" in fix["title"]


def test_driverless_device_gets_advice_only():
    rows = [{**BLUETOOTH_OFF, "Problem": "CM_PROB_FAILED_INSTALL"}]
    fix = suggest_fixes([finding("devices", "bad", problems=parse_device_problems(rows))])[0]
    assert fix["id"] == "install_driver" and fix["automatic"] is False


def test_enable_devices_dry_run_changes_nothing(monkeypatch):
    monkeypatch.setattr(fixes, "read_device_problems", lambda: parse_device_problems([BLUETOOTH_OFF]))
    def no_run(*a, **k): raise AssertionError("must not run a command in a dry run")
    monkeypatch.setattr(fixes.subprocess, "run", no_run)
    assert run_fix("enable_devices")["would_enable"] == ["Intel Wireless Bluetooth"]


def test_enable_devices_needs_admin(monkeypatch):
    monkeypatch.setattr(fixes, "read_device_problems", lambda: parse_device_problems([BLUETOOTH_OFF]))
    monkeypatch.setattr(fixes, "_is_admin", lambda: False)
    with pytest.raises(PermissionError):
        run_fix("enable_devices", dry_run=False)


def test_enable_devices_only_touches_disabled_ones(monkeypatch):
    rows = [BLUETOOTH_OFF, {**BLUETOOTH_OFF, "FriendlyName": "No driver cam", "Class": "Camera",
                            "InstanceId": "X", "Problem": "CM_PROB_FAILED_INSTALL"}]
    monkeypatch.setattr(fixes, "read_device_problems", lambda: parse_device_problems(rows))
    monkeypatch.setattr(fixes, "_is_admin", lambda: True)
    calls = []
    class Done: returncode = 0
    monkeypatch.setattr(fixes.subprocess, "run", lambda cmd, **k: calls.append(k["env"]["PNP_ID"]) or Done())
    result = run_fix("enable_devices", dry_run=False)
    assert result["enabled"] == ["Intel Wireless Bluetooth"] and len(calls) == 1