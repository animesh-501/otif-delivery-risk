# Data

**Source:** [DataCo Smart Supply Chain for Big Data Analysis](https://data.mendeley.com/datasets/8gx2fvg2k6/5) (Mendeley Data, public).
180,519 order lines from 65,752 orders, Jan 2015 to Jan 2018, with shipping mode, promised and actual transit days, delivery status, market, region, product and customer fields.

The file is about 96 MB, too large to keep in a GitHub repo, so it isn't committed. Download `DataCoSupplyChainDataset.csv` from the link above and place it at:

```
data/raw/DataCoSupplyChainDataset.csv
```

The file is Latin-1 encoded; `src/data.py` handles that.
