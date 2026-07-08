"""
AIFXBOT Finance Fetcher Module
Fetches live market data from Yahoo Finance public API (no API key required)
Supports: US Stocks, Crypto, Forex, ETFs, Indices
"""
import requests
import json
from typing import Optional, Dict, Any


class FinanceFetcher:
    """Fetch real-time financial data from Yahoo Finance."""

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    @staticmethod
    def fetch_quote(symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current quote for a symbol.
        Returns dict with price, change, volume, technicals, etc.
        """
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        try:
            resp = requests.get(url, headers=FinanceFetcher.HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            chart = data.get("chart", {})
            result = chart.get("result", [{}])[0] if chart.get("result") else None
            if not result:
                error = chart.get("error", {})
                print(f"  ⚠️ Yahoo Finance error for {symbol}: {error}")
                return None

            meta = result.get("meta", {})
            indicators = result.get("indicators", {})
            quote_list = indicators.get("quote", [{}])[0] if indicators.get("quote") else {}
            adjclose = indicators.get("adjclose", [{}])[0] if indicators.get("adjclose") else {}

            # Extract latest price
            prices = adjclose.get("adjclose", quote_list.get("close", []))
            latest_price = prices[-1] if prices else meta.get("regularMarketPrice", meta.get("previousClose"))
            prev_close = meta.get("previousClose", meta.get("chartPreviousClose"))

            # Change calculation
            change_abs = latest_price - prev_close if latest_price and prev_close else None
            change_pct = (change_abs / prev_close * 100) if change_abs and prev_close else None

            return {
                "symbol": symbol,
                "fetched_at": None,  # set by caller
                "market": FinanceFetcher._detect_market(symbol),
                "current_price": latest_price,
                "previous_close": prev_close,
                "open_price": meta.get("regularMarketOpen"),
                "high_price": meta.get("regularMarketDayHigh"),
                "low_price": meta.get("regularMarketDayLow"),
                "change_abs": change_abs,
                "change_pct": change_pct,
                "volume": meta.get("regularMarketVolume"),
                "currency": meta.get("currency", "USD"),
                "exchange": meta.get("exchangeName"),
                "market_cap": None,  # requires summary endpoint
                "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
                "fifty_day_ma": meta.get("fiftyDayAverage"),
                "two_hundred_day_ma": meta.get("twoHundredDayAverage"),
                "is_market_open": meta.get("marketState") == "REGULAR",
            }
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Network error fetching {symbol}: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            print(f"  ❌ Data parsing error for {symbol}: {e}")
            return None

    @staticmethod
    def fetch_summary(symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch additional summary data (PE ratio, market cap, EPS, etc.)
        """
        modules = "summaryDetail,defaultKeyStatistics,financialData"
        url = f"{FinanceFetcher.SUMMARY_URL}/{symbol}?modules={modules}"
        try:
            resp = requests.get(url, headers=FinanceFetcher.HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            quote = data.get("quoteSummary", {}).get("result", [{}])[0] if data.get("quoteSummary", {}).get("result") else {}
            if not quote:
                return None

            summary = quote.get("summaryDetail", {})
            stats = quote.get("defaultKeyStatistics", {})
            financial = quote.get("financialData", {})

            def _num(val):
                if val is None or val == {}:
                    return None
                if isinstance(val, dict):
                    return val.get("raw", val.get("fmt"))
                return val

            return {
                "symbol": symbol,
                "market_cap": _num(stats.get("marketCap")),
                "pe_ratio": _num(summary.get("trailingPE")),
                "forward_pe": _num(summary.get("forwardPE")),
                "eps": _num(stats.get("trailingEps")),
                "revenue": _num(financial.get("totalRevenue")),
                "profit_margin": _num(financial.get("profitMargins")),
                "debt_to_equity": _num(financial.get("debtToEquity")),
                "roe": _num(financial.get("returnOnEquity")),
                "beta": _num(summary.get("beta")),
                "dividend_yield": _num(summary.get("dividendYield")),
                "avg_volume": _num(summary.get("averageVolume")),
                "short_ratio": _num(summary.get("shortRatio")),
            }
        except Exception as e:
            print(f"  ⚠️ Summary fetch failed for {symbol}: {e}")
            return None

    @staticmethod
    def fetch_full(symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch both quote and summary, merged into one dict."""
        quote = FinanceFetcher.fetch_quote(symbol)
        if not quote:
            return None

        summary = FinanceFetcher.fetch_summary(symbol)
        if summary:
            for k, v in summary.items():
                if v is not None and quote.get(k) is None:
                    quote[k] = v

        return quote

    @staticmethod
    def fetch_batch(symbols: list[str]) -> Dict[str, Any]:
        """Fetch multiple symbols. Returns {symbol: data_or_None}."""
        results = {}
        print(f"\n📊 Fetching market data for {len(symbols)} symbol(s)...")
        for i, sym in enumerate(symbols, 1):
            print(f"  [{i}/{len(symbols)}] {sym} ...", end=" ")
            data = FinanceFetcher.fetch_full(sym)
            if data:
                print(f"✅ ${data.get('current_price')}")
            results[sym] = data
        return results

    @staticmethod
    def _detect_market(symbol: str) -> str:
        """Detect market type from symbol."""
        s = symbol.upper()
        if s.endswith("-USD") or s.endswith("-USDT") or s.endswith("-BTC"):
            return "CRYPTO"
        if "=X" in s or s.startswith("EUR") or s.startswith("GBP") or s.startswith("JPY"):
            return "FOREX"
        if ".SH" in s or ".SZ" in s or ".BJ" in s:
            return "CN"
        if ".HK" in s:
            return "HK"
        return "US"


if __name__ == "__main__":
    # Test with a few symbols
    test_symbols = ["AAPL", "NVDA", "BTC-USD", "EURUSD=X"]
    print("=" * 60)
    print("AIFXBOT Finance Fetcher - Test Run")
    print("=" * 60)
    for sym in test_symbols:
        data = FinanceFetcher.fetch_full(sym)
        if data:
            print(f"\n{sym}:")
            print(f"  Price: ${data.get('current_price'):,.2f}")
            print(f"  Change: {data.get('change_pct'):+.2f}%")
            print(f"  Market Cap: {data.get('market_cap'):,.0f}" if data.get('market_cap") else "")
            print(f"  PE Ratio: {data.get('pe_ratio')}")
        else:
            print(f"\n{sym}: ❌ Failed to fetch")
    print("\n" + "=" * 60)
