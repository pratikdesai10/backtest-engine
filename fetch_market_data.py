"""Bulk data fetcher for Nifty 50, Nifty 500, and indices from Fyers API.

Usage:
    python fetch_market_data.py --list nifty50 --from 2023-01-01 --to 2025-02-14 --resolution D
    python fetch_market_data.py --list nifty500 --from 2024-01-01 --to 2025-02-14 --resolution D
    python fetch_market_data.py --list indices --from 2023-01-01 --to 2025-02-14 --resolution 15
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from src.fyers_auth import get_fyers_client, get_session, generate_token, save_token, load_token
from src.fyers_data import fetch_historical, save_to_csv
from src.data_loader import validate_ohlcv


# Nifty 50 constituents (as of Feb 2025)
NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BHARTIARTL", "BPCL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JSWSTEEL", "KOTAKBANK", "LT", "M&M",
    "MARUTI", "NESTLEIND", "NTPC", "ONGC", "POWERGRID",
    "RELIANCE", "SBILIFE", "SBIN", "SUNPHARMA", "TATAMOTORS",
    "TATASTEEL", "TCS", "TECHM", "TITAN", "TRENT",
    "ULTRACEMCO", "WIPRO", "BAJAJHLDNG", "SHRIRAMFIN", "ADANIENSOL"
]

# Nifty 500 constituents (major stocks - full list is 500 stocks)
# This includes Nifty 50 + Nifty Next 50 + Mid/Small cap stocks
NIFTY_500 = [
    # Nifty 50
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BHARTIARTL", "BPCL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JSWSTEEL", "KOTAKBANK", "LT", "M&M",
    "MARUTI", "NESTLEIND", "NTPC", "ONGC", "POWERGRID",
    "RELIANCE", "SBILIFE", "SBIN", "SUNPHARMA", "TATAMOTORS",
    "TATASTEEL", "TCS", "TECHM", "TITAN", "TRENT",
    "ULTRACEMCO", "WIPRO", "BAJAJHLDNG", "SHRIRAMFIN", "ADANIENSOL",

    # Nifty Next 50
    "ADANIGREEN", "ADANIPOWER", "ATGL", "BANDHANBNK", "BANKBARODA",
    "BEL", "BERGEPAINT", "BOSCHLTD", "CHOLAFIN", "COFORGE",
    "COLPAL", "DALBHARAT", "DIVISLAB", "DIXON", "DLF",
    "GODREJCP", "GLAND", "HAVELLS", "ICICIGI", "ICICIPRULI",
    "INDIGO", "INDUSTOWER", "IRFC", "JSWENERGY", "LTIM",
    "LICI", "M&MFIN", "MARICO", "MUTHOOTFIN", "NAUKRI",
    "PAGEIND", "PERSISTENT", "PETRONET", "PFC", "PIDILITIND",
    "POLYCAB", "PNB", "RECLTD", "SHREECEM", "SIEMENS",
    "SRF", "TORNTPHARM", "TVSMOTOR", "UBL", "VEDL",
    "VOLTAS", "ZOMATO", "ZYDUSLIFE", "ABB", "INDHOTEL",

    # Additional major stocks from Nifty 500
    "360ONE", "3MINDIA", "AARTIIND", "AAVAS", "ABBOTINDIA",
    "ABCAPITAL", "ABFRL", "ACC", "AIAENG", "AJANTPHARM",
    "ALKEM", "AMBUJACEM", "ANGELONE", "APOLLOTYRE", "ARE&M",
    "ASHOKLEY", "ASTERDM", "ASTRAL", "AUROPHARMA", "AWL",
    "BALRAMCHIN", "BATAINDIA", "BHARATFORG", "BIOCON", "BLUESTARCO",
    "BRIGADE", "BSE", "CAMS", "CANBK", "CANFINHOME",
    "CASTROLIND", "CDSL", "CEATLTD", "CENTURYPLY", "CESC",
    "CGPOWER", "CHAMBLFERT", "CHOLAHLDNG", "CLEAN", "CONCOR",
    "COROMANDEL", "CREDITACC", "CRISIL", "CROMPTON", "CUB",
    "CUMMINSIND", "CYIENT", "DABUR", "DEEPAKNTR", "DELHIVERY",
    "DMART", "EIDPARRY", "ELGIEQUIP", "ESCORTS", "EXIDEIND",
    "FEDERALBNK", "FORTIS", "FSL", "GAIL", "GILLETTE",
    "GLENMARK", "GMRAIRPORT", "GODREJAGRO", "GODREJIND", "GODREJPROP",
    "GRANULES", "GRAPHITE", "GRSE", "GUJGASLTD", "HAL",
    "HDFCAMC", "HINDZINC", "HINDPETRO", "HONAUT", "IDFCFIRSTB",
    "IEX", "IGL", "INDIACEM", "INDIAMART", "INDIANB",
    "IOC", "IPCALAB", "IRCTC", "IREDA", "JBCHEPHARM",
    "JINDALSTEL", "JIOFIN", "JKCEMENT", "JMFINANCIL", "JUBLFOOD",
    "JUBLPHARMA", "KAJARIACER", "KAYNES", "KEI", "KFINTECH",
    "KPITTECH", "LALPATHLAB", "LAURUSLABS", "LICHSGFIN", "LODHA",
    "LTF", "LTTS", "LUPIN", "MAHABANK", "MANAPPURAM",
    "MANKIND", "MAPMYINDIA", "MAXHEALTH", "MCX", "METROPOLIS",
    "MFSL", "MGL", "MOTHERSON", "MOTILALOFS", "MPHASIS",
    "MRF", "MSUMI", "NATIONALUM", "NAUKRI", "NAVINFLUOR",
    "NBCC", "NCC", "NHPC", "NLCINDIA", "NMDC",
    "NUVAMA", "NYKAA", "OBEROIRLTY", "OFSS", "PAYTM",
    "PIIND", "PNBHOUSING", "PRESTIGE", "PVRINOX", "RADICO",
    "RAIN", "RAINBOW", "RAMCOCEM", "RBLBANK", "RCF",
    "REDINGTON", "RITES", "RVNL", "SAIL", "SBICARD",
    "SCHAEFFLER", "SOBHA", "SOLARINDS", "SONACOMS", "SONATSOFTW",
    "STARHEALTH", "SUNDARMFIN", "SUNDRMFAST", "SUNTV", "SUPREMEIND",
    "SUZLON", "SYNGENE", "TATACHEM", "TATACOMM", "TATACONSUM",
    "TATAELXSI", "TATAPOWER", "TATATECH", "THERMAX", "TIMKEN",
    "TITAGARH", "TORNTPOWER", "TRIDENT", "TVSMOTOR", "UCOBANK",
    "UNIONBANK", "UPL", "VBL", "VGUARD", "WHIRLPOOL",
    "YESBANK", "ZEEL", "ZENSARTECH"
]

# Indices
INDICES = [
    "NIFTY50-INDEX",
    "NIFTYBANK-INDEX"
]


ListType = Literal["nifty50", "nifty500", "indices"]


def get_symbol_list(list_type: ListType) -> list[str]:
    """Get the list of symbols based on list type."""
    if list_type == "nifty50":
        return [f"NSE:{symbol}-EQ" for symbol in NIFTY_50]
    elif list_type == "nifty500":
        return [f"NSE:{symbol}-EQ" for symbol in NIFTY_500]
    elif list_type == "indices":
        return [f"NSE:{symbol}" for symbol in INDICES]
    else:
        raise ValueError(f"Invalid list type: {list_type}")


def get_resolution_folder(resolution: str) -> str:
    """Get folder name for the resolution.

    Daily -> daily
    Intraday -> {resolution}min
    """
    if resolution.upper() == "D":
        return "daily"
    else:
        return f"{resolution}min"


def fetch_with_retry(
    fyers_client,
    symbol: str,
    resolution: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
    max_retries: int = 3,
    retry_delay: int = 5
) -> tuple[bool, str | None]:
    """Fetch data with retry logic.

    Returns:
        (success: bool, error_message: str | None)
    """
    for attempt in range(max_retries):
        try:
            print(f"  Fetching {symbol} (attempt {attempt + 1}/{max_retries})...", end=" ")

            df = fetch_historical(
                fyers_client,
                symbol=symbol,
                resolution=resolution,
                start_date=start_date,
                end_date=end_date,
            )

            if df.empty:
                print("❌ No data returned")
                return False, "No data returned from API"

            # Validate data
            issues = validate_ohlcv(df)
            if issues:
                print(f"⚠️  Data validation warnings: {', '.join(issues)}")

            # Save to CSV
            filepath = save_to_csv(df, symbol, str(output_dir))
            # Show relative path from output_dir parent
            rel_path = filepath.relative_to(output_dir.parent.parent)
            print(f"✅ Saved {len(df)} bars to {rel_path}")

            return True, None

        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                print(f"❌ Failed: {error_msg}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Failed after {max_retries} attempts: {error_msg}")
                return False, error_msg

    return False, "Max retries exceeded"


def main():
    parser = argparse.ArgumentParser(
        description="Bulk fetch market data from Fyers API"
    )
    parser.add_argument(
        "--list",
        choices=["nifty50", "nifty500", "indices"],
        required=True,
        help="Which list to fetch: nifty50, nifty500, or indices"
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        required=True,
        help="Start date (yyyy-mm-dd)"
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        required=True,
        help="End date (yyyy-mm-dd)"
    )
    parser.add_argument(
        "--resolution",
        "-r",
        default="D",
        help="Candle resolution: D, 1, 5, 15, 30, 60, 120, 240 (default: D)"
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output directory (default: data/)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of symbols to fetch before taking a break (default: 10)"
    )
    parser.add_argument(
        "--batch-delay",
        type=int,
        default=10,
        help="Delay in seconds between batches (default: 10)"
    )
    parser.add_argument(
        "--symbol-delay",
        type=float,
        default=0.5,
        help="Delay in seconds between each symbol (default: 0.5)"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    client_id = os.environ.get("FYERS_APP_ID")
    secret_key = os.environ.get("FYERS_SECRET_KEY")
    redirect_uri = os.environ.get("FYERS_REDIRECT_URI")

    if not client_id or not secret_key or not redirect_uri:
        print("❌ Missing Fyers credentials. Set FYERS_APP_ID, FYERS_SECRET_KEY, "
              "and FYERS_REDIRECT_URI in .env file.")
        print("See .env.example for the template.")
        sys.exit(1)

    # Authenticate
    access_token = load_token()
    if access_token is None:
        print("🔐 Authenticating with Fyers API...")
        session = get_session(client_id, secret_key, redirect_uri)
        print(f"\n🌐 Please visit this URL and authorize:\n{session.generate_authcode()}\n")
        auth_code = input("Enter the auth_code from the redirect URL: ").strip()
        access_token = generate_token(session, auth_code)
        save_token(access_token)
        print("✅ Access token saved for today's session.\n")
    else:
        print("✅ Using cached access token.\n")

    fyers_client = get_fyers_client(client_id, access_token)

    # Get symbol list
    symbols = get_symbol_list(args.list)

    # Create organized directory structure: data/{resolution}/{list_type}/
    # E.g., data/daily/nifty50/, data/15min/indices/
    base_output_dir = Path(args.output_dir)
    resolution_folder = get_resolution_folder(args.resolution)
    output_dir = base_output_dir / resolution_folder / args.list
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📊 Fetching {args.list.upper()} data")
    print(f"📅 Date range: {args.date_from} to {args.date_to}")
    print(f"⏱️  Resolution: {args.resolution}")
    print(f"📁 Output directory: {output_dir}")
    print(f"🔢 Total symbols: {len(symbols)}")
    print(f"⚙️  Batch size: {args.batch_size}, Batch delay: {args.batch_delay}s, Symbol delay: {args.symbol_delay}s")
    print(f"\n{'='*80}\n")

    # Track progress
    successful = []
    failed = []
    start_time = time.time()

    for idx, symbol in enumerate(symbols, 1):
        print(f"[{idx}/{len(symbols)}] ", end="")

        success, error = fetch_with_retry(
            fyers_client,
            symbol=symbol,
            resolution=args.resolution,
            start_date=args.date_from,
            end_date=args.date_to,
            output_dir=output_dir
        )

        if success:
            successful.append(symbol)
        else:
            failed.append((symbol, error))

        # Delay between symbols (except for last one)
        if idx < len(symbols):
            time.sleep(args.symbol_delay)

        # Batch delay
        if idx % args.batch_size == 0 and idx < len(symbols):
            print(f"\n⏸️  Batch complete ({idx}/{len(symbols)}). Waiting {args.batch_delay}s before next batch...\n")
            time.sleep(args.batch_delay)

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*80}")
    print(f"\n📈 SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successful: {len(successful)}/{len(symbols)}")
    print(f"❌ Failed: {len(failed)}/{len(symbols)}")
    print(f"⏱️  Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")

    if failed:
        print(f"\n❌ FAILED SYMBOLS ({len(failed)}):")
        print(f"{'='*80}")
        for symbol, error in failed:
            print(f"  • {symbol}: {error}")

        # Save failed symbols to file
        failed_file = output_dir / f"failed_{args.list}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(failed_file, 'w') as f:
            f.write(f"# Failed symbols for {args.list} - {datetime.now()}\n")
            f.write(f"# Date range: {args.date_from} to {args.date_to}\n")
            f.write(f"# Resolution: {args.resolution}\n\n")
            for symbol, error in failed:
                f.write(f"{symbol}\t{error}\n")
        print(f"\n💾 Failed symbols saved to: {failed_file}")

    print(f"\n✨ Done! Data saved to {output_dir}/")

    if failed:
        sys.exit(1)  # Exit with error code if any failed


if __name__ == "__main__":
    main()
