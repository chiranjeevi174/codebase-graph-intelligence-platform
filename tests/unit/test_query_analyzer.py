"""Unit tests for QueryAnalyzer component."""

from app.reasoning.query_analyzer import QueryAnalyzer


def test_query_analyzer_intent_classification():
    analyzer = QueryAnalyzer()

    # Callers intent
    res1 = analyzer.analyze("Who calls UserService.create_user()?")
    assert res1.intent == "callers"
    assert "UserService.create_user" in res1.candidate_symbols or "UserService" in res1.candidate_symbols

    # Callees intent
    res2 = analyzer.analyze("What does PaymentService call?")
    assert res2.intent == "callees"

    # Dependency intent
    res3 = analyzer.analyze("What depends on OrderRepository?")
    assert res3.intent == "dependency"

    # Execution flow intent
    res4 = analyzer.analyze("Trace the flow from main.py to UserRepository")
    assert res4.intent == "execution_flow"
    assert "main.py" in res4.candidate_files

    # Impact intent
    res5 = analyzer.analyze("Which components are affected by changing create_order?")
    assert res5.intent == "impact"


def test_query_analyzer_candidate_extraction():
    analyzer = QueryAnalyzer()
    res = analyzer.analyze("Explain how UserService interacts with /api/users.py")

    assert "UserService" in res.candidate_symbols
    assert (
        "api/users.py" in res.candidate_files
        or "/api/users.py" in res.candidate_files
        or "users.py" in res.candidate_files
    )
