"""Static charts for the README."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402

from config import CHART_DIR, MODE_ORDER  # noqa: E402

ON_TIME, LATE, INK, MUTED, ACCENT = "#2da44e", "#cf222e", "#1f2328", "#656d76", "#1f6feb"

plt.rcParams.update({
    "figure.dpi": 150, "font.size": 10, "axes.edgecolor": "#d0d7de", "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
    "axes.grid": True, "grid.color": "#eaeef2", "grid.linewidth": 0.8, "legend.frameon": False,
})


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(CHART_DIR / name, bbox_inches="tight")
    plt.close(fig)


def otif_by_mode(by_mode):
    b = by_mode.set_index("shipping_mode").loc[["All orders"] + MODE_ORDER]
    fig, ax = plt.subplots(figsize=(7.5, 3))
    colors = [MUTED if m == "All orders" else ACCENT for m in b.index]
    bars = ax.barh(b.index, b.otif_rate * 100, color=colors)
    ax.bar_label(bars, labels=[f"{r:.0%}" + ("" if m == "All orders" else f"   ({s:.0%} of orders)")
                               for m, r, s in zip(b.index, b.otif_rate, b.share_of_orders)],
                 padding=4, color=INK, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(axis="y", visible=False)
    ax.set_title("OTIF by shipping mode, Jan 2015 - Jan 2018")
    _save(fig, "01_otif_by_mode.png")


def transit_vs_promise(tvp):
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.2), sharey=True)
    for ax, mode in zip(axes, MODE_ORDER):
        share = tvp[tvp.shipping_mode == mode].set_index("actual_days")["share"].reindex(range(0, 7), fill_value=0)
        promise = int(tvp[tvp.shipping_mode == mode].promised_days.iloc[0])
        ax.bar(share.index, share * 100, color=[ON_TIME if d <= promise else LATE for d in share.index], width=0.75)
        ax.axvline(promise + 0.5, color=INK, ls="--", lw=1.2)
        ax.text(promise + 0.6, 97, f"promise: {promise} day{'s' if promise != 1 else ''}",
                fontsize=8.5, color=INK, va="top",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
        ax.set_title(mode, fontsize=10.5)
        ax.set_xticks(range(0, 7))
        ax.set_xlabel("Actual transit days")
        ax.set_ylim(0, 100)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Share of shipped orders")
    axes[0].yaxis.set_major_formatter(mtick.PercentFormatter())
    fig.suptitle("Actual transit vs. what was promised (green = on time, red = late)",
                 x=0.01, ha="left", fontweight="bold", fontsize=12)
    _save(fig, "02_transit_vs_promise.png")


def driver_strength(tests):
    # Standard Class is 60% of orders, so it's the cleanest read on every other factor.
    # Same Day's order-time result is added because it's the one other real driver.
    t = tests.copy()
    head = t[t.driver == "Shipping mode"].assign(label="Shipping mode (all orders)")
    cutoff = t[(t.driver == "Order time of day") & (t.within_mode == "Same Day")].assign(
        label="Order time of day (Same Day orders)")
    rest = t[(t.within_mode == "Standard Class") & (t.driver != "Order time of day")].assign(
        label=lambda d: d.driver + " (Standard Class)")
    top = pd.concat([rest.sort_values("cramers_v"), head, cutoff])
    fig, ax = plt.subplots(figsize=(7.5, 4))
    colors = [LATE if s else "#afb8c1" for s in top.significant_after_correction]
    ax.barh(top.label, top.cramers_v, color=colors)
    ax.set_xlim(0, 1.05)
    ax.grid(axis="y", visible=False)
    ax.set_title("How strongly each factor is tied to lateness (Cramér's V)")
    ax.set_xlabel("0 = no link, 1 = fully determines whether an order is late")
    ax.text(0, -0.25, "Red = significant after Bonferroni correction. Nothing else is significant in any "
            "mode; full results in outputs/driver_tests.csv.", transform=ax.transAxes, color=MUTED, fontsize=9)
    _save(fig, "03_what_drives_lateness.png")


def scenarios(sc):
    s = sc.reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    labels = [x if i == 0 else f"Ceiling: {x[0].lower()}{x[1:]}" if i == len(s) - 1 else f"{i}. {x}"
              for i, x in enumerate(s.scenario)]
    colors = [MUTED] + [ACCENT] * (len(s) - 2) + ["#8c959f"]
    bars = ax.barh(labels, s.otif_rate * 100, color=colors)
    ax.bar_label(bars, labels=[f"{r:.0%}   avg promise {d:.1f} days" for r, d in zip(s.otif_rate, s.avg_promised_days)],
                 padding=4, color=INK, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 135)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(axis="y", visible=False)
    ax.set_title("OTIF if promises matched real transit (steps 1-4 are cumulative)")
    _save(fig, "04_promise_scenarios.png")


def trend(by_month):
    m = by_month
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.plot(m.month, m.otif_rate * 100, color=ACCENT, lw=1.8)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_title("Monthly OTIF: flat at ~40% for three years")
    _save(fig, "05_otif_trend.png")


def make_all(t, tests, sc):
    otif_by_mode(t["otif_by_mode"])
    transit_vs_promise(t["transit_vs_promise"])
    driver_strength(tests)
    scenarios(sc)
    trend(t["otif_by_month"])
