from urllib.parse import parse_qs

import httpx

from stock_trader.notifications.twilio import TwilioSender


def test_send_posts_message_with_basic_auth():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization", "")
        seen["form"] = parse_qs(request.content.decode())
        return httpx.Response(201, json={"sid": "SM123"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    sender = TwilioSender("AC123", "token", "+15550001111", client=client)
    sid = sender.send("+15550002222", "hello")
    assert sid == "SM123"
    assert seen["path"].endswith("/Accounts/AC123/Messages.json")
    assert seen["auth"].startswith("Basic ")
    assert seen["form"]["To"] == ["+15550002222"]
    assert seen["form"]["From"] == ["+15550001111"]
    assert seen["form"]["Body"] == ["hello"]
