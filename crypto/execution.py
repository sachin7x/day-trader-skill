"""Paper-only execution boundary. Live order submission is intentionally absent."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import uuid4
from .models import D, Instrument


class ExecutionMode(str, Enum):
    RESEARCH = "research"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class PaperOrder:
    client_order_id: str
    symbol: str
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Decimal = None
    status: str = "accepted"


class KillSwitch:
    """In-process emergency gate. Live execution remains separately disabled."""
    def __init__(self):
        self.active = False
        self.reason = None

    def activate(self, reason):
        self.reason = str(reason or "manual emergency stop")
        self.active = True

    def reset(self, confirmed=False):
        if not confirmed:
            raise RuntimeError("kill switch reset requires explicit confirmation")
        self.active = False
        self.reason = None

    def assert_permitted(self):
        if self.active:
            raise RuntimeError("kill switch active: %s" % self.reason)


class PaperBroker:
    """Deterministic paper order ledger. Does not contact an exchange."""
    def __init__(self, kill_switch=None):
        self.orders = {}
        self.fills = []
        self.kill_switch = kill_switch or KillSwitch()

    def submit(self, instrument, side, quantity, order_type="market", limit_price=None,
               client_order_id=None):
        self.kill_switch.assert_permitted()
        if not isinstance(instrument, Instrument):
            raise TypeError("instrument must be an Instrument")
        if side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        qty = D(quantity)
        if qty < instrument.min_quantity or qty % instrument.quantity_step != 0:
            raise ValueError("quantity violates instrument minimum or step")
        if order_type not in ("market", "limit"):
            raise ValueError("paper broker supports market and limit orders only")
        if order_type == "limit" and (limit_price is None or D(limit_price) <= 0):
            raise ValueError("limit order needs a positive limit_price")
        cid = client_order_id or str(uuid4())
        if cid in self.orders:
            return self.orders[cid]
        order = PaperOrder(cid, instrument.symbol, side, qty, order_type,
                           D(limit_price) if limit_price is not None else None)
        self.orders[cid] = order
        return order

    def fill(self, client_order_id, quantity, price, fee=0):
        order = self.orders.get(client_order_id)
        if order is None:
            raise KeyError("unknown client_order_id")
        if order.status in ("filled", "cancelled"):
            raise ValueError("order is already terminal")
        qty, px = D(quantity), D(price)
        if qty <= 0 or px <= 0:
            raise ValueError("fill quantity and price must be positive")
        already = sum((f["quantity"] for f in self.fills
                       if f["client_order_id"] == client_order_id), D("0"))
        if already + qty > order.quantity:
            raise ValueError("fill exceeds remaining quantity")
        self.fills.append({"client_order_id": client_order_id, "symbol": order.symbol,
                           "side": order.side, "quantity": qty, "price": px, "fee": D(fee)})
        order.status = "filled" if already + qty == order.quantity else "partially_filled"
        return order

    def cancel_all(self):
        """Cancel every non-terminal paper order and return cancelled IDs."""
        cancelled = []
        for client_order_id, order in list(self.orders.items()):
            if order.status not in ("filled", "cancelled"):
                self.cancel(client_order_id)
                cancelled.append(client_order_id)
        return cancelled

    def cancel(self, client_order_id):
        order = self.orders.get(client_order_id)
        if order is None:
            raise KeyError("unknown client_order_id")
        if order.status == "filled":
            raise ValueError("cannot cancel a filled order")
        order.status = "cancelled"
        return order


def submit_live_order(*args, **kwargs):
    raise RuntimeError(
        "Live trading is not implemented. No live exchange order can be submitted by this package."
    )
