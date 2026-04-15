"""IBKR TWS / IB Gateway broker adapter."""

from __future__ import annotations

from dataclasses import dataclass

from brokerage.brokers.base import BrokerAdapter
from brokerage.config import BrokerageSettings
from brokerage.models import BrokerSubmissionResult, TradeIntent

try:
    from ib_insync import IB, LimitOrder, MarketOrder, Stock
except Exception:  # pragma: no cover - exercised via mocked methods in tests
    IB = None

    class MarketOrder:  # type: ignore[no-redef]
        def __init__(self, action, totalQuantity):
            self.action = action
            self.totalQuantity = totalQuantity
            self.orderType = "MKT"

    class LimitOrder:  # type: ignore[no-redef]
        def __init__(self, action, totalQuantity, lmtPrice):
            self.action = action
            self.totalQuantity = totalQuantity
            self.orderType = "LMT"
            self.lmtPrice = lmtPrice

    class Stock:  # type: ignore[no-redef]
        def __init__(self, symbol, exchange, currency):
            self.symbol = symbol
            self.exchange = exchange
            self.currency = currency


@dataclass
class _OrderContractBundle:
    contract: object
    order: object


class IBKRTwsBrokerAdapter(BrokerAdapter):
    """Minimal IBKR adapter using ib_insync."""

    def __init__(self, settings: BrokerageSettings, *, host: str = "127.0.0.1"):
        self.settings = settings
        self.host = host
        self._ib = None

    def _select_port(self, account_mode: str) -> int:
        return 4002 if account_mode == "paper" else 4001

    def _ensure_ib(self):
        if IB is None:
            raise RuntimeError("ib_insync is not installed")
        if self._ib is None:
            self._ib = IB()
        return self._ib

    def _connect(self, account_mode: str) -> None:
        ib = self._ensure_ib()
        port = self._select_port(account_mode)
        ib.connect(self.host, port, clientId=0)

    def _build_contract(self, intent: TradeIntent):
        if intent.asset_class != "stock":
            raise ValueError(f"Unsupported asset class: {intent.asset_class}")
        return Stock(intent.symbol, "SMART", "USD")

    def _build_order(self, intent: TradeIntent):
        if intent.order_type == "MARKET":
            return MarketOrder(intent.side, intent.quantity)
        if intent.order_type == "LIMIT":
            return LimitOrder(intent.side, intent.quantity, intent.limit_price)
        raise ValueError(f"Unsupported order type: {intent.order_type}")

    def _qualify_contract(self, contract):
        ib = self._ensure_ib()
        qualified = ib.qualifyContracts(contract)
        return qualified[0] if qualified else contract

    def submit_order(self, intent: TradeIntent) -> BrokerSubmissionResult:
        if intent.asset_class != "stock":
            raise ValueError(f"Unsupported asset class: {intent.asset_class}")

        self._connect(intent.account_mode)
        contract = self._qualify_contract(self._build_contract(intent))
        order = self._build_order(intent)
        trade = self._ib.placeOrder(contract, order)
        order_id = getattr(getattr(trade, "order", None), "orderId", None)
        status = getattr(getattr(trade, "orderStatus", None), "status", None)
        return BrokerSubmissionResult(
            accepted=True,
            broker_order_id=str(order_id) if order_id is not None else None,
            broker_status=status,
        )

    def get_order_status(self, order_id: str):
        raise NotImplementedError("get_order_status not implemented yet")

    def cancel_order(self, order_id: str):
        raise NotImplementedError("cancel_order not implemented yet")
