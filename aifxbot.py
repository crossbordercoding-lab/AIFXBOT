"""
AIFXBOT - AI Finance Exchange Bot
Main orchestrator: fetches live market data, analyzes entries, and stores results in Supabase.
"""
import sys
from datetime import datetime
from supabase_client import SupabaseClient
from finance_fetcher import FinanceFetcher
from analysis_engine import AnalysisEngine


class AIFXBOT:
    """Main bot class that orchestrates market data fetching and entry analysis."""

    def __init__(self):
        self.db = SupabaseClient()
        self.fetcher = FinanceFetcher()
        self.engine = AnalysisEngine()

    # ------------------------------------------------------------------
    # Database Helpers (CRUD via REST API)
    # ------------------------------------------------------------------

    def get_active_entries(self) -> list:
        """Fetch all active entries from Supabase."""
        try:
            data = self.db.select("entries", "*", status="eq.active")
            return data if data else []
        except Exception as e:
            print(f"❌ Error fetching entries: {e}")
            return []

    def get_market_data(self, symbol: str) -> dict:
        """Fetch cached market data for a symbol."""
        try:
            data = self.db.select("market_data", "*", symbol="eq." + symbol)
            return data[0] if data else {}
        except Exception:
            return {}

    def upsert_market_data(self, data: dict) -> bool:
        """Store/update market snapshot in Supabase."""
        try:
            # Upsert on symbol column (unique constraint)
            self.db.upsert("market_data", {
                "symbol": data["symbol"],
                "market": data.get("market", "US"),
                "current_price": data.get("current_price"),
                "previous_close": data.get("previous_close"),
                "open_price": data.get("open_price"),
                "high_price": data.get("high_price"),
                "low_price": data.get("low_price"),
                "change_abs": data.get("change_abs"),
                "change_pct": data.get("change_pct"),
                "volume": data.get("volume"),
                "avg_volume": data.get("avg_volume"),
                "market_cap": data.get("market_cap"),
                "fifty_two_week_high": data.get("fifty_two_week_high"),
                "fifty_two_week_low": data.get("fifty_two_week_low"),
                "fifty_day_ma": data.get("fifty_day_ma"),
                "two_hundred_day_ma": data.get("two_hundred_day_ma"),
                "pe_ratio": data.get("pe_ratio"),
                "eps": data.get("eps"),
                "currency": data.get("currency", "USD"),
                "exchange": data.get("exchange"),
                "is_market_open": data.get("is_market_open"),
            })
            return True
        except Exception as e:
            print(f"  ⚠️ Failed to store market data for {data.get('symbol')}: {e}")
            return False

    def insert_analysis(self, analysis: dict) -> bool:
        """Store analysis result in Supabase."""
        try:
            self.db.insert("analysis_logs", {
                "entry_id": analysis["entry_id"],
                "unrealized_pnl": analysis.get("unrealized_pnl"),
                "return_pct": analysis.get("return_pct"),
                "risk_reward_ratio": analysis.get("risk_reward_ratio"),
                "distance_to_stop": analysis.get("distance_to_stop"),
                "distance_to_target": analysis.get("distance_to_target"),
                "market_trend": analysis.get("market_trend"),
                "vs_50d_ma": analysis.get("vs_50d_ma"),
                "vs_200d_ma": analysis.get("vs_200d_ma"),
                "vs_52w_high": analysis.get("vs_52w_high"),
                "vs_52w_low": analysis.get("vs_52w_low"),
                "recommendation": analysis.get("recommendation"),
                "confidence": analysis.get("confidence"),
                "reasoning": analysis.get("reasoning"),
                "suggested_action": analysis.get("suggested_action"),
                "alert_price": analysis.get("alert_price"),
                "data_freshness_hours": analysis.get("data_freshness_hours", 0),
            })
            return True
        except Exception as e:
            print(f"  ⚠️ Failed to store analysis for entry #{analysis.get('entry_id')}: {e}")
            return False

    # ------------------------------------------------------------------
    # Core Workflow
    # ------------------------------------------------------------------

    def run(self):
        """Execute full analysis cycle: fetch → analyze → store."""
        print("=" * 70)
        print(" AIFXBOT - AI Finance Exchange Bot")
        print(f" Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # 1. Fetch active entries
        print("\n📋 Step 1: Fetching active entries from Supabase...")
        entries = self.get_active_entries()
        if not entries:
            print("  ⚠️ No active entries found. Add some via Supabase dashboard!")
            print("  Hint: INSERT INTO entries (symbol, name, entry_price, quantity, entry_date)")
            print("        VALUES ('AAPL', 'Apple Inc.', 180.00, 10, '2025-06-01');")
            return
        print(f"  ✅ Found {len(entries)} active entr(y/ies)")
        for e in entries:
            print(f"     • {e.get('symbol')} | {e.get('direction', 'long').upper()} | ${e.get('entry_price')} x {e.get('quantity')}")

        # 2. Collect unique symbols
        symbols = list(set(e.get("symbol") for e in entries if e.get("symbol")))
        print(f"\n📊 Step 2: Fetching live market data for {len(symbols)} symbol(s)...")

        market_data = {}
        for sym in symbols:
            data = self.fetcher.fetch_full(sym)
            if data:
                data["fetched_at"] = datetime.now().isoformat()
                market_data[sym] = data
                self.upsert_market_data(data)
                print(f"  ✅ {sym}: ${data.get('current_price'):,.2f} ({data.get('change_pct', 0):+.2f}%)")
            else:
                print(f"  ❌ {sym}: Failed to fetch market data")

        if not market_data:
            print("\n❌ No market data available. Aborting analysis.")
            return

        # 3. Analyze each entry
        print(f"\n🧠 Step 3: Running analysis engine...")
        analyses = []
        for entry in entries:
            sym = entry.get("symbol")
            mkt = market_data.get(sym)
            if not mkt:
                print(f"  ⚠️ {sym}: Skipping (no market data)")
                continue
            analysis = self.engine.analyze_entry(entry, mkt)
            analyses.append(analysis)

            # Store in Supabase
            self.insert_analysis(analysis)

            # Print summary
            rec = analysis.get("recommendation", "unknown").upper().replace("_", " ")
            conf = analysis.get("confidence", 0)
            ret = analysis.get("return_pct", 0)
            pnl = analysis.get("unrealized_pnl", 0)
            action = analysis.get("suggested_action", "hold").upper()
            print(f"\n  📌 {sym} Analysis:")
            print(f"     Return: {ret:+.2f}% | Unrealized P&L: ${pnl:,.2f}")
            print(f"     Recommendation: {rec} (confidence: {conf}%)")
            print(f"     Suggested Action: {action}")
            if analysis.get("alert_price"):
                print(f"     🔔 Alert Price: ${analysis['alert_price']:,.2f}")
            if analysis.get("distance_to_stop") is not None:
                print(f"     🛡️ Distance to Stop: ${analysis['distance_to_stop']:,.2f}")
            if analysis.get("distance_to_target") is not None:
                print(f"     🎯 Distance to Target: ${analysis['distance_to_target']:,.2f}")

        # 4. Summary Report
        print("\n" + "=" * 70)
        print(" 📊 ANALYSIS SUMMARY")
        print("=" * 70)
        total_pnl = sum(a.get("unrealized_pnl", 0) for a in analyses)
        avg_return = sum(a.get("return_pct", 0) for a in analyses) / len(analyses) if analyses else 0
        rec_counts = {}
        for a in analyses:
            r = a.get("recommendation", "unknown")
            rec_counts[r] = rec_counts.get(r, 0) + 1

        print(f"  Total Unrealized P&L: ${total_pnl:+,.2f}")
        print(f"  Average Return: {avg_return:+.2f}%")
        print(f"  Analyses Generated: {len(analyses)}")
        print(f"  Recommendations:")
        for rec, count in sorted(rec_counts.items(), key=lambda x: -x[1]):
            emoji = {"strong_buy": "🟢🟢", "buy": "🟢", "hold": "⚪", "reduce": "🟡", "sell": "🔴"}.get(rec, "❓")
            print(f"    {emoji} {rec.upper().replace('_', ' ')}: {count}")

        print(f"\n  ✅ All data stored in Supabase:")
        print(f"     • market_data: {len(market_data)} snapshots")
        print(f"     • analysis_logs: {len(analyses)} records")
        print(f"\n{'=' * 70}")
        print(" AIFXBOT run complete. Next analysis scheduled.")
        print(f"{'=' * 70}\n")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def print_help():
    print("""
AIFXBOT - AI Finance Exchange Bot
Usage:
  python aifxbot.py [command]

Commands:
  run       Execute full analysis cycle (default)
  test      Test with sample entries (no Supabase needed)
  entries   List active entries from Supabase
  markets   Show latest market data from Supabase
  analysis  Show latest analysis results from Supabase
  help      Show this message

Examples:
  python aifxbot.py run
  python aifxbot.py entries
    """)


def cmd_test():
    """Run a quick test without Supabase."""
    print("=" * 70)
    print(" AIFXBOT - Test Mode (No Supabase)")
    print("=" * 70)

    fetcher = FinanceFetcher()
    engine = AnalysisEngine()

    test_entries = [
        {"id": 1, "symbol": "AAPL", "name": "Apple", "entry_price": 180.00, "quantity": 10, "direction": "long", "stop_loss": 165, "take_profit": 210, "strategy": "momentum"},
        {"id": 2, "symbol": "NVDA", "name": "NVIDIA", "entry_price": 120.00, "quantity": 25, "direction": "long", "stop_loss": 100, "take_profit": 160, "strategy": "growth"},
        {"id": 3, "symbol": "BTC-USD", "name": "Bitcoin", "entry_price": 65000.00, "quantity": 0.5, "direction": "long", "stop_loss": 55000, "take_profit": 80000, "strategy": "swing"},
    ]

    symbols = [e["symbol"] for e in test_entries]
    market_data = fetcher.fetch_batch(symbols)
    analyses = engine.analyze_batch(test_entries, market_data)

    print("\n" + "=" * 70)
    print(" TEST RESULTS SUMMARY")
    print("=" * 70)
    for a in analyses:
        print(f"\n  Entry #{a['entry_id']}: {a.get('recommendation', 'N/A').upper()}")
        print(f"    Return: {a.get('return_pct', 0):+.2f}% | P&L: ${a.get('unrealized_pnl', 0):,.2f}")
        print(f"    Confidence: {a.get('confidence', 0)}%")
    print("=" * 70)


def cmd_entries():
    """List entries from Supabase."""
    bot = AIFXBOT()
    entries = bot.get_active_entries()
    print(f"\n📋 Active Entries ({len(entries)}):")
    for e in entries:
        print(f"  #{e.get('id')} | {e.get('symbol')} | {e.get('direction', 'long').upper()} | ${e.get('entry_price')} x {e.get('quantity')} | {e.get('strategy', 'N/A')} | {e.get('status')}")


def cmd_markets():
    """Show latest market data."""
    bot = AIFXBOT()
    try:
        data = bot.db.select("market_data", "*")
        print(f"\n📊 Market Data ({len(data)} snapshots):")
        for m in data:
            print(f"  {m.get('symbol')} | ${m.get('current_price'):,.2f} | {m.get('change_pct', 0):+.2f}% | Cap: {m.get('market_cap', 'N/A')}")
    except Exception as e:
        print(f"❌ Error: {e}")


def cmd_analysis():
    """Show latest analysis results."""
    bot = AIFXBOT()
    try:
        # Get latest analysis per entry using the view
        data = bot.db.select("v_entry_analysis", "*")
        print(f"\n🧠 Latest Analysis ({len(data)} results):")
        for a in data:
            sym = a.get('symbol', 'N/A')
            rec = a.get('recommendation', 'N/A')
            conf = a.get('confidence', 0)
            ret = a.get('return_pct', 0)
            print(f"  {sym} | {rec.upper()} | Conf: {conf}% | Return: {ret:+.2f}%")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "run"

    if cmd == "help" or cmd == "-h" or cmd == "--help":
        print_help()
    elif cmd == "test":
        cmd_test()
    elif cmd == "entries":
        cmd_entries()
    elif cmd == "markets":
        cmd_markets()
    elif cmd == "analysis":
        cmd_analysis()
    elif cmd == "run":
        bot = AIFXBOT()
        bot.run()
    else:
        print(f"Unknown command: {cmd}")
        print_help()
