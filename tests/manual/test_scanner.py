from src.scanner.checks import judge_usage, judge_network


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