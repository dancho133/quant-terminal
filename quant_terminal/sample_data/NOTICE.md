# Dataset attribution and scope

The included BTCUSDT daily OHLCV snapshot is historical public market data from
[Binance Vision](https://data.binance.vision/), normalized from monthly spot archives.
The adjacent JSON manifest lists each original archive URL and verified SHA-256,
the normalized CSV checksum, dates, field transformations and retrieval date.
No price bars were generated, backfilled or adjusted.

This dataset is separate from the MIT-licensed program. Binance's
[Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
(version 1.0, updated August 26, 2026, inspected October 13, 2026) place the data and
derived charts/analytical work under
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) with supplemental
upstream terms. The bundled snapshot and generated example research outputs are
provided for noncommercial educational research under those terms.
Commercial data use needs a separately licensed provider. No affiliation or
endorsement is implied.

Timestamps changed from milliseconds (2023-2024) or microseconds (2025) to ISO UTC.
The six normalized columns are timestamp, open, high, low, close, volume; volume is
BTC base-asset volume. USDT is treated as a quote unit; the demo assumes it is stable.

Synthetic fixtures used in tests are authored for arithmetic checks. They are
explicitly distinct from this historical snapshot and are not market evidence.
