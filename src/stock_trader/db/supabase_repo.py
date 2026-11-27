from typing import Any
from urllib.parse import quote

import httpx

from stock_trader.domain.proposals import Proposal
from stock_trader.domain.state import TradeState


class SupabaseRepository:
    def __init__(
        self,
        url: str,
        service_key: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._key = service_key
        self._client = client or httpx.Client(timeout=20)

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._key,
            "authorization": f"Bearer {self._key}",
            "content-type": "application/json",
        }
        if prefer:
            headers["prefer"] = prefer
        return headers

    def _get(self, path: str, params: dict[str, str] | None = None) -> list[dict]:
        response = self._client.get(
            f"{self._url}/rest/v1/{path}",
            params=params,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def _insert(
        self,
        table: str,
        row: dict[str, Any],
        prefer: str = "return=representation",
    ) -> dict:
        response = self._client.post(
            f"{self._url}/rest/v1/{table}",
            json=row,
            headers=self._headers(prefer),
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if rows else {}

    def insert_signal(self, data: dict[str, Any]) -> dict:
        return self._insert("signals", data)

    def insert_proposal(self, proposal: Proposal) -> dict:
        return self._insert(
            "proposals",
            {
                "id": proposal.id,
                "created_at": proposal.created_at.isoformat(),
                "expires_at": proposal.expires_at.isoformat(),
                "symbol": proposal.symbol,
                "qty": proposal.qty,
                "entry_price": proposal.entry_price,
                "stop_price": proposal.stop_price,
                "confidence": proposal.confidence,
                "rationale": proposal.rationale,
                "state": TradeState.PROPOSED.value,
            },
        )

    def get_proposal(self, proposal_id: str) -> dict | None:
        rows = self._get(
            "proposals", {"select": "*", "id": f"eq.{proposal_id}"}
        )
        return rows[0] if rows else None

    def save_approval(self, key: str, data: dict[str, Any]) -> dict:
        row = dict(data)
        row["idempotency_key"] = key
        return self._insert(
            "approvals",
            row,
            prefer="resolution=ignore-duplicates,return=representation",
        )

    def get_approval(self, key: str) -> dict | None:
        rows = self._get(
            f"approvals?select=*&idempotency_key=eq.{quote(key, safe='')}"
        )
        return rows[0] if rows else None

    def set_trade_state(self, trade_id: str, state: TradeState) -> None:
        response = self._client.patch(
            f"{self._url}/rest/v1/proposals",
            params={"id": f"eq.{trade_id}"},
            json={"state": state.value},
            headers=self._headers("return=minimal"),
        )
        response.raise_for_status()

    def insert_order(self, data: dict[str, Any]) -> dict:
        return self._insert("orders", data)

    def upsert_position(self, data: dict[str, Any]) -> dict:
        return self._insert(
            "positions",
            data,
            prefer="resolution=merge-duplicates,return=representation",
        )

    def get_trade_state(self, trade_id: str) -> TradeState | None:
        proposal = self.get_proposal(trade_id)
        return TradeState(proposal["state"]) if proposal else None

    def pending_proposal_count(self) -> int:
        rows = self._get(
            "proposals", {"select": "id", "state": "eq.PROPOSED"}
        )
        return len(rows)

    def expire_stale_proposals(self, now) -> None:
        response = self._client.patch(
            f"{self._url}/rest/v1/proposals",
            params={
                "state": "eq.PROPOSED",
                "expires_at": f"lt.{now.isoformat()}",
            },
            json={"state": "EXPIRED"},
            headers=self._headers("return=minimal"),
        )
        response.raise_for_status()

    def open_position_symbols(self) -> set[str]:
        rows = self._get("positions", {"select": "symbol", "qty": "gt.0"})
        return {row["symbol"] for row in rows}

    def open_positions(self) -> list[dict]:
        return self._get("positions", {"select": "*", "qty": "gt.0"})

    def remove_position(self, symbol: str) -> None:
        response = self._client.delete(
            f"{self._url}/rest/v1/positions",
            params={"symbol": f"eq.{symbol}"},
            headers=self._headers("return=minimal"),
        )
        response.raise_for_status()

    def get_setting(self, key: str) -> Any:
        rows = self._get("settings", {"select": "value", "key": f"eq.{key}"})
        return rows[0]["value"] if rows else None

    def set_setting(self, key: str, value: Any) -> None:
        self._insert(
            "settings",
            {"key": key, "value": value},
            prefer="resolution=merge-duplicates,return=representation",
        )

    def has_order(self, client_id: str) -> bool:
        rows = self._get(
            "orders", {"select": "id", "client_id": f"eq.{client_id}"}
        )
        return bool(rows)

    def list_yes_approvals(self) -> list[dict]:
        return self._get(
            "approvals",
            {"select": "idempotency_key,proposal_id", "decision": "eq.YES"},
        )
