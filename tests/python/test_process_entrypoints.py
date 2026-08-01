import json

from _pytest.capture import CaptureFixture

from apps.scheduler.__main__ import main as scheduler_main
from apps.worker.__main__ import main as worker_main


def test_worker_exits_safely_when_idle(capsys: CaptureFixture[str]) -> None:
    assert worker_main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "service": "lilos-worker",
        "status": "idle",
        "reason": "No job execution is configured in Roadmap Phase 0.",
    }


def test_scheduler_exits_safely_when_idle(capsys: CaptureFixture[str]) -> None:
    assert scheduler_main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "service": "lilos-scheduler",
        "status": "idle",
        "reason": "No schedule dispatch is configured in Roadmap Phase 0.",
    }
