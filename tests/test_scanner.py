from src.scanner.checks import judge_usage, judge_network
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