"""Is anything besides the shipping mode's promise driving late orders?

Two independent checks:
  1. Statistical: within each shipping mode, does the late rate differ by market, region,
     category, weekday, etc.? (chi-square test, Bonferroni-corrected, plus effect size)
  2. Predictive: does a model with every order-time feature beat a lookup table that only
     knows the shipping mode? Trained on 2015-2016, tested on 2017 onward.
Only information known when the order is placed is used. Actual transit days,
delivery status and ship date are outcomes, so they are excluded.
"""
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.metrics import log_loss, roc_auc_score

from config import SEED, TEST_START

DRIVERS = {
    "market": "Market",
    "order_region": "Destination region",
    "customer_segment": "Customer segment",
    "main_department": "Department",
    "main_category": "Product category",
    "order_weekday": "Order weekday",
    "order_month": "Order month",
    "order_hour_band": "Order time of day",
    "units_band": "Units in order",
}
MIN_GROUP = 200  # ignore tiny groups when reporting the spread in late rate


def _prepare(orders):
    o = orders[~orders.cancelled].copy()
    o["late"] = (~o.on_time).astype(int)
    o["order_weekday"] = o.order_ts.dt.day_name()
    o["order_month"] = o.order_ts.dt.month_name()
    o["order_hour_band"] = pd.cut(o.order_ts.dt.hour, [-1, 5, 11, 17, 23],
                                  labels=["Night", "Morning", "Afternoon", "Evening"]).astype(str)
    o["units_band"] = pd.cut(o.units, [0, 1, 3, 6, np.inf], labels=["1", "2-3", "4-6", "7+"]).astype(str)
    return o


def _cramers_v(table):
    chi2, p, _, _ = chi2_contingency(table)
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    return chi2, p, float(np.sqrt(chi2 / (n * k))) if k > 0 else 0.0


def driver_tests(orders):
    o = _prepare(orders)
    rows = []

    # Reference point: the shipping mode itself
    _, p, v = _cramers_v(pd.crosstab(o.shipping_mode, o.late))
    rates = o.groupby("shipping_mode").late.mean()
    rows.append({"driver": "Shipping mode", "within_mode": "all orders", "groups": len(rates),
                 "late_rate_spread_pts": (rates.max() - rates.min()) * 100, "cramers_v": v, "p_value": p})

    # Each candidate driver, inside each mode that has any variation in lateness
    modes = [m for m, r in rates.items() if 0 < r < 1]
    n_tests = len(DRIVERS) * len(modes)
    for col, name in DRIVERS.items():
        for mode in modes:
            sub = o[o.shipping_mode == mode]
            table = pd.crosstab(sub[col], sub.late)
            _, p, v = _cramers_v(table)
            g = sub.groupby(col).late.agg(["mean", "size"])
            g = g[g["size"] >= MIN_GROUP]
            rows.append({"driver": name, "within_mode": mode, "groups": len(table),
                         "late_rate_spread_pts": (g["mean"].max() - g["mean"].min()) * 100,
                         "cramers_v": v, "p_value": p})

    out = pd.DataFrame(rows)
    out["p_value_bonferroni"] = np.minimum(out.p_value * np.where(out.driver == "Shipping mode", 1, n_tests), 1)
    out["significant_after_correction"] = out.p_value_bonferroni < 0.05
    return out


FEATURES = ["shipping_mode", "market", "order_region", "customer_segment", "main_department",
            "main_category", "order_weekday", "order_month", "order_hour", "units", "lines",
            "sales", "avg_discount_rate", "max_product_price"]
CATEGORICAL = ["shipping_mode", "market", "order_region", "customer_segment", "main_department",
               "main_category", "order_weekday", "order_month"]


def model_check(orders):
    o = _prepare(orders)
    o["order_hour"] = o.order_ts.dt.hour
    for c in CATEGORICAL:
        o[c] = o[c].astype("category")
    train, test = o[o.order_ts < TEST_START], o[o.order_ts >= TEST_START]

    # 1. Lookup table: late rate per shipping mode, learned on the training years
    lookup = train.groupby("shipping_mode", observed=True).late.mean()
    p_lookup = test.shipping_mode.map(lookup).astype(float).clip(1e-4, 1 - 1e-4)

    # 2. Two-rule lookup: shipping mode, plus whether a Same Day order came in after 12:00
    def rule_key(df):
        after_noon = (df.shipping_mode == "Same Day") & (df.order_hour >= 12)
        return df.shipping_mode.astype(str) + np.where(after_noon, " / after 12:00", "")
    rule = train.groupby(rule_key(train)).late.mean()
    p_rule = rule_key(test).map(rule).astype(float).clip(1e-4, 1 - 1e-4)

    # 3. Gradient boosting on every order-time feature
    model = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.05, num_leaves=31,
                               min_child_samples=100, subsample=0.8, subsample_freq=1,
                               colsample_bytree=0.8, random_state=SEED, n_jobs=1,
                               deterministic=True, force_col_wise=True, verbose=-1)
    model.fit(train[FEATURES], train.late)
    p_model = model.predict_proba(test[FEATURES])[:, 1]

    # 4. Same model without the shipping mode: how much is left once the promise is removed?
    no_mode = [f for f in FEATURES if f != "shipping_mode"]
    model_nm = lgb.LGBMClassifier(**model.get_params()).fit(train[no_mode], train.late)
    p_nm = model_nm.predict_proba(test[no_mode])[:, 1]

    def score(name, p):
        return {"approach": name, "test_auc": roc_auc_score(test.late, p),
                "test_log_loss": log_loss(test.late, p)}

    return pd.DataFrame([
        score("Shipping-mode lookup (1 feature)", p_lookup),
        score("Shipping mode + Same Day 12:00 cutoff (2 rules)", p_rule),
        score(f"LightGBM, all {len(FEATURES)} order-time features", p_model),
        score("LightGBM, same features minus shipping mode", p_nm),
    ]).assign(train_orders=len(train), test_orders=len(test))
