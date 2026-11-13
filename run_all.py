"""Run the full analysis: SQL KPIs -> driver tests -> model check -> promise scenarios -> charts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd  # noqa: E402

import charts  # noqa: E402
import data  # noqa: E402
import drivers  # noqa: E402
import promise  # noqa: E402
from config import CHART_DIR, OUT_DIR  # noqa: E402

pd.set_option("display.width", 200)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    CHART_DIR.mkdir(exist_ok=True)

    t = data.build()
    o = t["orders"]
    print("\nOTIF by shipping mode\n", t["otif_by_mode"].round(3).to_string(index=False))

    tests = drivers.driver_tests(o)
    print("\nDriver tests (within each shipping mode)\n", tests.round(4).to_string(index=False))

    model = drivers.model_check(o)
    print("\nCan anything beat a simple lookup? (train 2015-16, test 2017+)\n", model.round(4).to_string(index=False))

    sc = promise.scenarios(o)
    print("\nPromise scenarios\n", sc.round(4).to_string(index=False))

    allrow = t["otif_by_mode"].set_index("shipping_mode").loc["All orders"]
    summary = {
        "orders": len(o),
        "order_lines": int(o.lines.sum()),
        "otif_today": allrow.otif_rate,
        "on_time_rate_shipped": allrow.on_time_rate_shipped,
        "cancel_rate": allrow.cancel_rate,
        "late_sales_share": allrow.late_sales / o.sales.sum(),
        "otif_after_promise_fixes": sc.loc[sc.cumulative, "otif_rate"].iloc[-1],
        "avg_promise_days_today": sc.avg_promised_days.iloc[0],
        "avg_promise_days_after_fixes": sc.loc[sc.cumulative, "avg_promised_days"].iloc[-1],
        "auc_mode_lookup": model.test_auc.iloc[0],
        "auc_two_rules": model.test_auc.iloc[1],
        "auc_lightgbm_all_features": model.test_auc.iloc[2],
        "auc_lightgbm_without_mode": model.test_auc.iloc[3],
    }
    print("\nSummary\n", pd.Series(summary).round(4).to_string())

    for name in ["otif_by_mode", "otif_by_month", "transit_vs_promise"]:
        t[name].to_csv(OUT_DIR / f"{name}.csv", index=False)
    tests.to_csv(OUT_DIR / "driver_tests.csv", index=False)
    model.to_csv(OUT_DIR / "model_check.csv", index=False)
    sc.to_csv(OUT_DIR / "promise_scenarios.csv", index=False)
    promise.promise_curve(o).to_csv(OUT_DIR / "on_time_by_promise.csv", index=False)
    pd.Series(summary).to_csv(OUT_DIR / "summary.csv", header=["value"])

    charts.make_all(t, tests, sc)
    print("\nOutputs written to outputs and charts")


if __name__ == "__main__":
    main()
