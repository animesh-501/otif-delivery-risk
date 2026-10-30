"""Paths and analysis settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "DataCoSupplyChainDataset.csv"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"
CHART_DIR = ROOT / "charts"

# Model check: train on 2015-2016 orders, test on 2017 onward (no shuffling across time)
TEST_START = "2017-01-01"
SEED = 42

MODE_ORDER = ["Same Day", "First Class", "Second Class", "Standard Class"]

# Columns kept from the raw file, renamed to snake_case
COLUMNS = {
    "Order Id": "order_id",
    "Order Item Id": "order_item_id",
    "order date (DateOrders)": "order_ts",
    "shipping date (DateOrders)": "ship_ts",
    "Shipping Mode": "shipping_mode",
    "Days for shipment (scheduled)": "promised_days",
    "Days for shipping (real)": "actual_days",
    "Delivery Status": "delivery_status",
    "Late_delivery_risk": "late_flag_raw",
    "Order Status": "order_status",
    "Market": "market",
    "Order Region": "order_region",
    "Order Country": "order_country",
    "Customer Segment": "customer_segment",
    "Department Name": "department",
    "Category Name": "category",
    "Order Item Quantity": "quantity",
    "Sales": "sales",
    "Order Item Discount Rate": "discount_rate",
    "Product Price": "product_price",
}
