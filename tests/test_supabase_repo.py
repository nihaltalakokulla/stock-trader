import httpx

from stock_trader.db.supabase_repo import SupabaseRepository


def make_repo(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return SupabaseRepository("https://demo.supabase.co", "service-key", client=client)


def test_insert_signal_returns_row_and_sends_key():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["apikey"] = request.headers.get("apikey")
        seen["prefer"] = request.headers.get("prefer")
        return httpx.Response(201, json=[{"id": "s1", "symbol": "AAPL"}])

    repo = make_repo(handler)
    row = repo.insert_signal({"symbol": "AAPL", "probability": 0.8, "rationale": "x"})
    assert row["id"] == "s1"
    assert seen["path"] == "/rest/v1/signals"
    assert seen["apikey"] == "service-key"
    assert seen["prefer"] == "return=representation"


def test_get_approval_queries_by_idempotency_key():
    seen = {}

    def handler(request):
        seen["query"] = request.url.query.decode()
        return httpx.Response(200, json=[{"decision": "YES"}])

    repo = make_repo(handler)
    assert repo.get_approval("approval:p1:YES") == {"decision": "YES"}
    assert "idempotency_key=eq.approval%3Ap1%3AYES" in seen["query"]


def test_set_setting_upserts():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["prefer"] = request.headers.get("prefer")
        seen["body"] = request.content.decode()
        return httpx.Response(201, json=[])

    repo = make_repo(handler)
    repo.set_setting("trading_paused", True)
    assert seen["method"] == "POST"
    assert seen["prefer"] == "resolution=merge-duplicates,return=representation"
    assert '"trading_paused"' in seen["body"]
