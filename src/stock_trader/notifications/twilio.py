import httpx


class TwilioSender:
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._sid = account_sid
        self._token = auth_token
        self._from = from_number
        self._client = client or httpx.Client(timeout=20)

    def send(self, to: str, body: str) -> str:
        response = self._client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json",
            data={"To": to, "From": self._from, "Body": body},
            auth=(self._sid, self._token),
        )
        response.raise_for_status()
        return response.json()["sid"]
