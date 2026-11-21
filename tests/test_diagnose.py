from diagnose import PendingActivity, hints_for


def test_completed_workflow_has_nothing_running():
    assert hints_for("COMPLETED", [], True) == ["Workflow is COMPLETED; nothing is running."]


def test_failed_workflow_points_to_history():
    assert "FAILED" in hints_for("FAILED", [], True)[0]


def test_retrying_activity_shows_attempt_and_failure():
    hints = hints_for("RUNNING", [PendingActivity("suspend_okta_user", 3, "HTTP 429")], True)
    assert "attempt 3" in hints[0] and "HTTP 429" in hints[0]


def test_unanswered_query_points_at_the_worker():
    hints = hints_for("RUNNING", [], query_answered=False)
    assert any("worker is probably not running" in h for h in hints)


def test_idle_running_workflow_is_waiting_on_timer_or_signal():
    hints = hints_for("RUNNING", [], query_answered=True)
    assert any("timer or on an approval signal" in h for h in hints)
