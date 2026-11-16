"""Cheapest way to reach any OTIF target by changing promises only.

Each shipping mode can keep today's promise or lengthen it, up to 6 days (the slowest observed
transit). Same Day can also use the 12:00 cutoff rule. Two business rules apply:
  * no promise gets shorter than today's. Shortening only lowers the average by giving up
    on-time orders, which no business would choose.
  * a faster tier never promises longer than a slower one
    (Same Day <= First Class <= Second Class <= Standard Class).

That leaves a few hundred promise combinations. For each one, OTIF and the average days
promised follow directly from the observed transit distribution, so every combination is
scored exactly and the efficient frontier is read off: the most OTIF for a given average
promise. Transit is held as observed; cancelled orders still fail.

Works from the committed outputs, so it runs without the raw data:
    python promise_frontier.py

Writes:
  outputs/promise_frontier.csv         every frontier point with its promise per mode
  outputs/promise_frontier_steps.csv   the frontier's corner points and OTIF bought per extra day
  outputs/promise_frontier_targets.csv cheapest promises for 60-95% OTIF, after the two quick wins
  charts/06_promise_frontier.png
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd  # noqa: E402

import charts  # noqa: E402
from config import CHART_DIR, MODE_ORDER, OUT_DIR  # noqa: E402

CUTOFF = "cutoff"   # Same Day: 0 days if ordered before 12:00, else 1
DAYS = range(0, 7)
TARGETS = [0.60, 0.70, 0.80, 0.90, 0.95]
PROMISE_COLS = ["promise_same", "promise_first", "promise_second", "promise_standard"]


def mode_options():
    """For every mode and promise: share of all orders that are OTIF, and average days promised."""
    by_mode = pd.read_csv(OUT_DIR / "otif_by_mode.csv").set_index("shipping_mode")
    tvp = pd.read_csv(OUT_DIR / "transit_vs_promise.csv")
    total = by_mode.loc["All orders", "orders"]
    rows = []
    for mode in MODE_ORDER:
        weight = by_mode.loc[mode, "orders"] / total
        shipped = 1 - by_mode.loc[mode, "cancel_rate"]
        dist = tvp[tvp.shipping_mode == mode].set_index("actual_days").share
        current = int(by_mode.loc[mode, "promised_days"])
        for d in DAYS:
            if d < current:
                continue
            rows.append({"shipping_mode": mode, "promise": d, "current": d == current,
                         "otif_points": weight * shipped * dist[dist.index <= d].sum(),
                         "day_points": weight * d})
        if mode == "Same Day":
            # Same Day transit is 0 days for morning orders and 1 day for afternoon ones,
            # so the afternoon share equals the share of shipped orders that took 1 day.
            # (Cancelled orders are assumed to split the same way; this moves the average
            # promise by under 0.0001 days vs the order-level scenario table.)
            afternoon = dist.get(1, 0.0)
            rows.append({"shipping_mode": mode, "promise": CUTOFF, "current": False,
                         "otif_points": weight * shipped, "day_points": weight * afternoon})
    return pd.DataFrame(rows)


def _days(promise):
    return 1 if promise == CUTOFF else promise   # cutoff promises at most 1 day


def all_combinations(opts):
    per_mode = [opts[opts.shipping_mode == m].to_dict("records") for m in MODE_ORDER]
    rows = []
    for combo in itertools.product(*per_mode):
        tiers = [_days(c["promise"]) for c in combo]
        if any(a > b for a, b in zip(tiers, tiers[1:])):
            continue
        rows.append({
            **{f"promise_{m.split()[0].lower()}": c["promise"] for m, c in zip(MODE_ORDER, combo)},
            "otif_rate": sum(c["otif_points"] for c in combo),
            "avg_promised_days": sum(c["day_points"] for c in combo),
            "is_today": all(c["current"] for c in combo),
        })
    return pd.DataFrame(rows)


def frontier(combos):
    """Combinations where no other one gives more OTIF for the same or fewer average days."""
    c = combos.sort_values(["avg_promised_days", "otif_rate"], ascending=[True, False])
    best, keep = -1.0, []
    for i, r in c.iterrows():
        if r.otif_rate > best + 1e-12:
            keep.append(i)
            best = r.otif_rate
    return c.loc[keep].reset_index(drop=True)


def corner_points(front):
    """Upper concave hull of the frontier: the steps worth taking, best return first.

    Between two corners, OTIF bought per extra day of average promise is constant.
    """
    pts = front.sort_values("avg_promised_days").to_dict("records")
    hull = []
    for p in pts:
        while len(hull) >= 2:
            a, b = hull[-2], hull[-1]
            cross = ((b["avg_promised_days"] - a["avg_promised_days"]) * (p["otif_rate"] - a["otif_rate"])
                     - (b["otif_rate"] - a["otif_rate"]) * (p["avg_promised_days"] - a["avg_promised_days"]))
            if cross >= 0:
                hull.pop()
            else:
                break
        hull.append(p)
    h = pd.DataFrame(hull)
    h["otif_pts_per_extra_day"] = h.otif_rate.diff() * 100 / h.avg_promised_days.diff()
    return h


def cheapest_for(combos, target):
    hit = combos[combos.otif_rate >= target - 1e-12]
    return hit.sort_values(["avg_promised_days", "otif_rate"], ascending=[True, False]).iloc[0]


def main():
    opts = mode_options()
    combos = all_combinations(opts)
    front = frontier(combos)
    today = combos[combos.is_today].iloc[0]

    print(f"Today: OTIF {today.otif_rate:.4f}, avg promise {today.avg_promised_days:.4f} days")
    print(f"Combinations allowed by the business rules: {len(combos):,} of {8 * 7 * 7 * 7:,}")
    print("\nEfficient frontier (no other combination gives more OTIF for the same or fewer days)\n",
          front.drop(columns="is_today").round(4).to_string(index=False))

    steps = corner_points(front)
    print("\nCorner points: OTIF bought per extra day of average promise\n",
          steps.drop(columns="is_today").round(4).to_string(index=False))

    # Both quick wins buy ~5x more OTIF per day than anything else, so targets start from them
    quick = combos[(combos.promise_same == CUTOFF) & (combos.promise_first == 2)]
    rows = []
    for t in TARGETS:
        r = cheapest_for(quick, t)
        rows.append({"otif_target": t, **r[PROMISE_COLS].to_dict(), "otif_rate": r.otif_rate,
                     "avg_promised_days": r.avg_promised_days,
                     "extra_days_vs_today": r.avg_promised_days - today.avg_promised_days})
    targets = pd.DataFrame(rows)
    print("\nCheapest promises for each OTIF target, after the two quick wins\n",
          targets.round(4).to_string(index=False))

    # The README's four cumulative steps, matched to this model by their promises
    sc = pd.read_csv(OUT_DIR / "promise_scenarios.csv")
    sc = sc[sc.cumulative | (sc.scenario == "Today")]
    key = lambda df: df[PROMISE_COLS].astype(str).agg("|".join, axis=1)  # noqa: E731
    path = combos.assign(k=key(combos)).set_index("k").loc[key(sc)].reset_index(drop=True)
    on_front = set(key(front))
    print("\nREADME steps checked against this model")
    for (_, s), (_, m) in zip(sc.iterrows(), path.iterrows()):
        print(f"   {s.scenario[:55]:55s} OTIF {s.otif_rate:.4f} vs {m.otif_rate:.4f} | "
              f"avg days {s.avg_promised_days:.4f} vs {m.avg_promised_days:.4f} | "
              f"on frontier: {key(m.to_frame().T).iloc[0] in on_front}")

    front.drop(columns="is_today").to_csv(OUT_DIR / "promise_frontier.csv", index=False)
    steps.drop(columns="is_today").to_csv(OUT_DIR / "promise_frontier_steps.csv", index=False)
    targets.to_csv(OUT_DIR / "promise_frontier_targets.csv", index=False)
    CHART_DIR.mkdir(exist_ok=True)
    charts.promise_frontier(combos, front, steps, path)
    print("\nOutputs written to outputs and charts")


if __name__ == "__main__":
    main()
