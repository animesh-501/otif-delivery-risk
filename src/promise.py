"""What OTIF would be if each shipping mode promised what the network actually delivers.

Transit times are taken as observed. Only the promise changes, so this shows how much of the
OTIF gap is a promise-setting problem rather than a transit problem.
"""
import pandas as pd

from config import MODE_ORDER


NOON_CUTOFF = "0 days if ordered before 12:00, else 1"


def _promised(orders, promise):
    p = orders.shipping_mode.map(lambda m: promise.get(m) if isinstance(promise.get(m), int) else None)
    p = p.astype(float).fillna(orders.promised_days)
    for mode, rule in promise.items():
        if rule == NOON_CUTOFF:
            is_mode = orders.shipping_mode == mode
            p[is_mode] = (orders.order_ts[is_mode].dt.hour >= 12).astype(int)
    return p


def otif_if(orders, promise):
    """OTIF with a different promise per mode. Cancelled orders still fail."""
    p = _promised(orders, promise)
    otif = (orders.actual_days <= p) & ~orders.cancelled
    return otif.mean(), p.mean()


def promise_curve(orders):
    """On-time rate for each mode at every possible promise, from shipped orders."""
    shipped = orders[~orders.cancelled]
    rows = []
    for mode in MODE_ORDER:
        s = shipped[shipped.shipping_mode == mode]
        for d in range(0, 7):
            rows.append({"shipping_mode": mode, "promised_days": d,
                         "current_promise": int(s.promised_days.iloc[0]) == d,
                         "on_time_rate": (s.actual_days <= d).mean()})
    return pd.DataFrame(rows)


def scenarios(orders):
    current = orders.groupby("shipping_mode").promised_days.first().to_dict()
    steps = [
        ("Today", {}),
        ("First Class: promise 2 days, not 1", {"First Class": 2}),
        ("Same Day: state the 12:00 cutoff (afternoon orders = next day)", {"Same Day": NOON_CUTOFF}),
        ("Standard Class: promise 5 days, not 4", {"Standard Class": 5}),
        ("Second Class: promise 5 days (same transit as Standard)", {"Second Class": 5}),
        ("Promise the slowest observed transit for every mode",
         {"First Class": 2, "Same Day": NOON_CUTOFF, "Second Class": 6, "Standard Class": 6}),
    ]
    rows, promise = [], dict(current)
    for i, (label, change) in enumerate(steps):
        promise = dict(current, **change) if i == len(steps) - 1 else dict(promise, **change)
        otif, avg_days = otif_if(orders, promise)
        rows.append({"scenario": label, "cumulative": i not in (0, len(steps) - 1),
                     "otif_rate": otif, "avg_promised_days": avg_days,
                     **{f"promise_{m.split()[0].lower()}": ("cutoff" if promise[m] == NOON_CUTOFF else promise[m])
                        for m in MODE_ORDER}})
    return pd.DataFrame(rows)
