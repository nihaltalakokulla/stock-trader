import pytest

from stock_trader.cli import main


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def train(self):
        self.calls.append(("train",))

    def nightly(self, dry_run=False):
        self.calls.append(("nightly", dry_run))

    def execute(self, key):
        self.calls.append(("execute", key))

    def paper_report(self):
        self.calls.append(("paper-report",))


def test_nightly_dispatches_with_dry_run_flag():
    runtime = FakeRuntime()
    assert main(["nightly", "--dry-run"], runtime=runtime) == 0
    assert runtime.calls == [("nightly", True)]


def test_execute_requires_and_passes_key():
    runtime = FakeRuntime()
    assert main(["execute", "--key", "approval:p1:YES"], runtime=runtime) == 0
    assert runtime.calls == [("execute", "approval:p1:YES")]


def test_execute_without_key_exits():
    with pytest.raises(SystemExit):
        main(["execute"], runtime=FakeRuntime())


def test_train_and_report_dispatch():
    runtime = FakeRuntime()
    main(["train"], runtime=runtime)
    main(["paper-report"], runtime=runtime)
    assert runtime.calls == [("train",), ("paper-report",)]
