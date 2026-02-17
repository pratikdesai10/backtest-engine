# Bulk Market Data Fetcher

## Overview

`fetch_market_data.py` is a utility script to download historical OHLC data for multiple stocks/indices from Fyers API in bulk.

## Features

- ✅ **Predefined lists**: Nifty 50, Nifty 500, and Indices (Nifty, Bank Nifty)
- ✅ **Organized storage**: Automatic organization by timeframe and list type
- ✅ **Intelligent batching**: Configurable batch size and delays to avoid API rate limits
- ✅ **Retry logic**: Automatic retry with exponential backoff (3 attempts)
- ✅ **Progress tracking**: Real-time progress with success/failure indicators
- ✅ **Error handling**: Failed symbols are logged to a file for manual retry
- ✅ **Data validation**: Automatic OHLCV validation for each downloaded file

## File Organization

Data is automatically organized by **timeframe** and **list type**:

```
data/
├── daily/
│   ├── nifty50/
│   │   ├── NSE_RELIANCE-EQ.csv
│   │   ├── NSE_TCS-EQ.csv
│   │   └── ...
│   ├── nifty500/
│   │   └── ...
│   └── indices/
│       ├── NSE_NIFTY50-INDEX.csv
│       └── NSE_NIFTYBANK-INDEX.csv
├── 15min/
│   ├── nifty50/
│   ├── nifty500/
│   └── indices/
├── 5min/
│   └── ...
└── 60min/
    └── ...
```

**Resolution to folder mapping:**
- `D` (Daily) → `data/daily/{list}/`
- `15` (15-min) → `data/15min/{list}/`
- `5` (5-min) → `data/5min/{list}/`
- `60` (1-hour) → `data/60min/{list}/`

## Usage

### Basic Usage

```bash
# Fetch Nifty 50 daily data → saves to data/daily/nifty50/
python fetch_market_data.py --list nifty50 --from 2023-01-01 --to 2025-02-14 --resolution D

# Fetch Nifty 500 daily data → saves to data/daily/nifty500/
python fetch_market_data.py --list nifty500 --from 2024-01-01 --to 2025-02-14 --resolution D

# Fetch indices with 15-min candles → saves to data/15min/indices/
python fetch_market_data.py --list indices --from 2023-01-01 --to 2025-02-14 --resolution 15
```

### Advanced Options

```bash
# Custom batching to be more gentle on the API
python fetch_market_data.py \
  --list nifty500 \
  --from 2023-01-01 \
  --to 2025-02-14 \
  --resolution D \
  --batch-size 5 \
  --batch-delay 15 \
  --symbol-delay 1.0

# Custom output directory
python fetch_market_data.py \
  --list nifty50 \
  --from 2024-01-01 \
  --to 2025-02-14 \
  --resolution D \
  --output-dir my_data/
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--list` | Required | Which list to fetch: `nifty50`, `nifty500`, or `indices` |
| `--from` | Required | Start date in `yyyy-mm-dd` format |
| `--to` | Required | End date in `yyyy-mm-dd` format |
| `--resolution` | `D` | Candle resolution: `D`, `1`, `5`, `15`, `30`, `60`, `120`, `240` |
| `--output-dir` | `data/` | Base output directory (files saved to `{output-dir}/{resolution}/{list}/`) |
| `--batch-size` | `10` | Number of symbols to fetch before taking a break |
| `--batch-delay` | `10` | Delay in seconds between batches |
| `--symbol-delay` | `0.5` | Delay in seconds between each symbol |

## Stock Lists

### Nifty 50 (50 stocks)
Major blue-chip stocks including RELIANCE, TCS, INFY, HDFC BANK, ICICI BANK, etc.

### Nifty 500 (~300 stocks)
Comprehensive list including Nifty 50 + Nifty Next 50 + major mid/small cap stocks across sectors.

### Indices (2 indices)
- `NSE:NIFTY50-INDEX` - Nifty 50 Index
- `NSE:NIFTYBANK-INDEX` - Bank Nifty Index

## Output

### Success Case
```
📁 Output directory: data/daily/nifty50

[1/50] Fetching NSE:RELIANCE-EQ (attempt 1/3)... ✅ Saved 489 bars to data/daily/nifty50/NSE_RELIANCE-EQ.csv
[2/50] Fetching NSE:TCS-EQ (attempt 1/3)... ✅ Saved 489 bars to data/daily/nifty50/NSE_TCS-EQ.csv
...
[10/50] Fetching NSE:HDFCBANK-EQ (attempt 1/3)... ✅ Saved 489 bars to data/daily/nifty50/NSE_HDFCBANK-EQ.csv

⏸️  Batch complete (10/50). Waiting 10s before next batch...
```

### Failed Symbols
If any symbols fail to download, they are:
1. Displayed in the final summary
2. Saved to a timestamped file in the same directory: `{output-dir}/{resolution}/{list}/failed_{list}_{timestamp}.txt`

Example `data/daily/nifty50/failed_nifty50_20250217_140523.txt`:
```
# Failed symbols for nifty50 - 2025-02-17 14:05:23
# Date range: 2023-01-01 to 2025-02-14
# Resolution: D

NSE:SYMBOL1-EQ    No data returned from API
NSE:SYMBOL2-EQ    Connection timeout
```

## Tips

1. **Start with smaller lists**: Test with `--list indices` first to ensure authentication works
2. **Monitor rate limits**: Increase `--batch-delay` and `--symbol-delay` if you see frequent failures
3. **Use retry for failures**: The script exits with code 1 if any symbols fail - check the failed list and retry manually
4. **Daily data recommended**: For backtesting strategies, daily (`D`) resolution is usually sufficient
5. **Intraday data limits**: Fyers API limits intraday data to 100 days per request (automatically chunked)

## Authentication

The script uses the same Fyers authentication as `main.py fetch`:

1. Set credentials in `.env` file:
   ```
   FYERS_APP_ID=your_app_id_here
   FYERS_SECRET_KEY=your_secret_key_here
   FYERS_REDIRECT_URI=https://trade.fyers.in/api-login/redirect-uri/abc123
   ```

2. On first run, you'll be prompted to authorize:
   ```
   🔐 Authenticating with Fyers API...
   🌐 Please visit this URL and authorize:
   [URL will be displayed]

   Enter the auth_code from the redirect URL:
   ```

3. Token is cached for 24 hours in `.fyers_token`

## Example Session

```bash
$ python fetch_market_data.py --list nifty50 --from 2024-01-01 --to 2025-02-14 --resolution D

✅ Using cached access token.

📊 Fetching NIFTY50 data
📅 Date range: 2024-01-01 to 2025-02-14
⏱️  Resolution: D
📁 Output directory: data/daily/nifty50
🔢 Total symbols: 50
⚙️  Batch size: 10, Batch delay: 10s, Symbol delay: 0.5s

================================================================================

[1/50] Fetching NSE:ADANIENT-EQ (attempt 1/3)... ✅ Saved 281 bars to data/daily/nifty50/NSE_ADANIENT-EQ.csv
[2/50] Fetching NSE:ADANIPORTS-EQ (attempt 1/3)... ✅ Saved 281 bars to data/daily/nifty50/NSE_ADANIPORTS-EQ.csv
...
[50/50] Fetching NSE:ADANIENSOL-EQ (attempt 1/3)... ✅ Saved 281 bars to data/daily/nifty50/NSE_ADANIENSOL-EQ.csv

================================================================================

📈 SUMMARY
================================================================================
✅ Successful: 50/50
❌ Failed: 0/50
⏱️  Total time: 127.3s (2.1 minutes)

✨ Done! Data saved to data/daily/nifty50/
```

## Integration with Backtest Engine

After fetching data, use it with the backtest engine:

```bash
# Run optimization on all Nifty 50 daily data
python main.py optimize --strategy macd_crossover --data-dir data/daily/nifty50/ --max-variants 500

# Run single backtest
python main.py backtest --strategy rsi_reversal --data data/daily/nifty50/NSE_RELIANCE-EQ.csv

# Test intraday strategy on 15-min data
python main.py optimize --strategy my_intraday --data-dir data/15min/nifty50/ --max-variants 300
```
