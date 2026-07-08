"""
AIFXBOT Analysis Engine
Computes precise analysis for each trading entry using live market data.
"""
from typing import Dict, Any, Optional
from datetime import datetime, date


class AnalysisEngine:
    """
    Analyzes trading entries against live market data.
    Generates: P&L, risk metrics, trend analysis, and actionable recommendations.
    """

    @staticmethod
    def analyze_entry(entry: Dict[str, Any], market: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single entry against current market data.
        Returns a complete analysis dict ready for Supabase.
        """
        result = {
            "entry_id": entry.get("id"),
            "created_at": datetime.now().isoformat(),
        }

        if not market or not market.get("current_price"):
            result["reasoning"] = "Market data unavailable. Unable to analyze."
            result["recommendation"] = "hold"
            result["confidence"] = 0.0
            return result

        # --- Core P&L Calculations ---
        entry_price = float(entry.get("entry_price", 0) or 0)
        current_price = float(market.get("current_price", 0) or 0)
        quantity = float(entry.get("quantity", 1) or 1)
        direction = entry.get("direction", "long").lower()

        if direction == "short":
            unrealized_pnl = (entry_price - current_price) * quantity
        else:
            unrealized_pnl = (current_price - entry_price) * quantity

        return_pct = ((current_price - entry_price) / entry_price * 100) if entry_price else 0
        if direction == "short":
            return_pct = -return_pct

        result["unrealized_pnl"] = round(unrealized_pnl, 2)
        result["return_pct"] = round(return_pct, 2)
        result["realized_pnl"] = 0.0

        # --- Risk Metrics ---
        stop_loss = entry.get("stop_loss")
        take_profit = entry.get("take_profit")
        risk_reward = None
        dist_stop = None
        dist_target = None

        if stop_loss and entry_price:
            if direction == "short":
                dist_stop = current_price - stop_loss
                risk = entry_price - stop_loss
            else:
                dist_stop = stop_loss - current_price
                risk = entry_price - stop_loss

        if take_profit and entry_price:
            if direction == "short":
                dist_target = take_profit - current_price
                reward = entry_price - take_profit
            else:
                dist_target = take_profit - current_price
                reward = take_profit - entry_price

            if risk and reward:
                risk_reward = abs(reward / risk) if risk != 0 else None

        result["risk_reward_ratio"] = round(risk_reward, 2) if risk_reward else None
        result["distance_to_stop"] = round(dist_stop, 2) if dist_stop else None
        result["distance_to_target"] = round(dist_target, 2) if dist_target else None
        result["max_drawdown_pct"] = None  # Requires historical data

        # --- Market Context & Trend ---
        ma50 = market.get("fifty_day_ma")
        ma200 = market.get("two_hundred_day_ma")
        wk_high = market.get("fifty_two_week_high")
        wk_low = market.get("fifty_two_week_low")
        change_pct = market.get("change_pct")

        vs_50d = ((current_price - ma50) / ma50 * 100) if ma50 and current_price else None
        vs_200d = ((current_price - ma200) / ma200 * 100) if ma200 and current_price else None
        vs_52w_high = ((current_price - wk_high) / wk_high * 100) if wk_high and current_price else None
        vs_52w_low = ((current_price - wk_low) / wk_low * 100) if wk_low and current_price else None

        result["vs_50d_ma"] = round(vs_50d, 2) if vs_50d else None
        result["vs_200d_ma"] = round(vs_200d, 2) if vs_200d else None
        result["vs_52w_high"] = round(vs_52w_high, 2) if vs_52w_high else None
        result["vs_52w_low"] = round(vs_52w_low, 2) if vs_52w_low else None

        # Determine market trend
        trend_signals = 0
        if vs_50d is not None:
            trend_signals += 1 if vs_50d > 0 else -1
        if vs_200d is not None:
            trend_signals += 1 if vs_200d > 0 else -1
        if change_pct is not None:
            trend_signals += 1 if change_pct > 0 else -1

        if trend_signals >= 2:
            market_trend = "bullish"
        elif trend_signals <= -2:
            market_trend = "bearish"
        elif trend_signals == 0:
            market_trend = "neutral"
        else:
            market_trend = "volatile"
        result["market_trend"] = market_trend

        # --- Recommendation Engine ---
        rec, confidence, reasoning, action, alert_price = AnalysisEngine._generate_recommendation(
            entry, market, return_pct, risk_reward, dist_stop, dist_target, vs_50d, vs_200d, market_trend
        )
        result["recommendation"] = rec
        result["confidence"] = round(confidence, 1)
        result["reasoning"] = reasoning
        result["suggested_action"] = action
        result["alert_price"] = round(alert_price, 2) if alert_price else None
        result["data_freshness_hours"] = 0.0

        return result

    @staticmethod
    def _generate_recommendation(
        entry: Dict[str, Any],
        market: Dict[str, Any],
        return_pct: float,
        risk_reward: Optional[float],
        dist_stop: Optional[float],
        dist_target: Optional[float],
        vs_50d: Optional[float],
        vs_200d: Optional[float],
        trend: str
    ) -> tuple:
        """
        Generate a trading recommendation based on all metrics.
        Returns: (recommendation, confidence, reasoning, suggested_action, alert_price)
        """
        direction = entry.get("direction", "long").lower()
        current_price = market.get("current_price", 0)
        stop_loss = entry.get("stop_loss")
        take_profit = entry.get("take_profit")
        strategy = entry.get("strategy", "").lower()

        signals = []
        score = 0  # -5 to +5

        # 1. Profit/Loss position
        if return_pct >= 20:
            signals.append(f"🟢 Strong profit: +{return_pct:.1f}%")
            score += 2
        elif return_pct >= 5:
            signals.append(f"🟢 In profit: +{return_pct:.1f}%")
            score += 1
        elif return_pct <= -10:
            signals.append(f"🔴 Deep loss: {return_pct:.1f}%")
            score -= 2
        elif return_pct <= -5:
            signals.append(f"🟡 Moderate loss: {return_pct:.1f}%")
            score -= 1
        else:
            signals.append(f"⚪ Near breakeven: {return_pct:.1f}%")

        # 2. Stop loss proximity
        if dist_stop is not None and stop_loss:
            pct_to_stop = abs(dist_stop / current_price * 100) if current_price else 0
            if pct_to_stop < 2:
                signals.append(f"⚠️ Very close to stop loss ({pct_to_stop:.1f}% away)")
                score -= 2
            elif pct_to_stop < 5:
                signals.append(f"⚠️ Approaching stop loss ({pct_to_stop:.1f}% away)")
                score -= 1
            else:
                signals.append(f"✅ Safe distance from stop ({pct_to_stop:.1f}% away)")
                score += 1

        # 3. Target proximity
        if dist_target is not None and take_profit:
            if dist_target < 0:
                signals.append(f"🎯 Target exceeded! Consider taking profit")
                score += 1
            else:
                pct_to_target = abs(dist_target / current_price * 100) if current_price else 0
                signals.append(f"📍 {pct_to_target:.1f}% to target price")

        # 4. Risk/Reward ratio
        if risk_reward:
            if risk_reward >= 3:
                signals.append(f"✅ Excellent R/R: {risk_reward:.1f}x")
                score += 1
            elif risk_reward < 1:
                signals.append(f"❌ Poor R/R: {risk_reward:.1f}x")
                score -= 1

        # 5. Trend alignment
        if trend == "bullish":
            if direction == "long":
                signals.append("📈 Trend is bullish — favorable for longs")
                score += 1
            else:
                signals.append("📈 Trend is bullish — headwind for shorts")
                score -= 1
        elif trend == "bearish":
            if direction == "short":
                signals.append("📉 Trend is bearish — favorable for shorts")
                score += 1
            else:
                signals.append("📉 Trend is bearish — headwind for longs")
                score -= 1

        # 6. Moving average context
        if vs_50d is not None:
            if vs_50d > 5:
                signals.append(f"📊 {vs_50d:.1f}% above 50-day MA — strong momentum")
            elif vs_50d < -5:
                signals.append(f"📊 {vs_50d:.1f}% below 50-day MA — weak momentum")

        # 7. 52-week range context
        wk_high = market.get("fifty_two_week_high")
        wk_low = market.get("fifty_two_week_low")
        if wk_high and wk_low and current_price:
            range_pct = (current_price - wk_low) / (wk_high - wk_low) * 100 if (wk_high - wk_low) else 0
            if range_pct > 90:
                signals.append(f"🔥 Near 52-week high ({range_pct:.0f}% of range)")
                if direction == "long":
                    score -= 1  # Overbought caution
            elif range_pct < 10:
                signals.append(f"❄️ Near 52-week low ({range_pct:.0f}% of range)")
                if direction == "long":
                    score += 1  # Value opportunity

        # --- Map score to recommendation ---
        if score >= 3:
            rec = "strong_buy"
            action = "add"
            confidence = 85 + min(score, 5) * 2
            alert_price = current_price * 0.95 if current_price else None
        elif score >= 1:
            rec = "buy"
            action = "add"
            confidence = 70 + score * 5
            alert_price = current_price * 0.97 if current_price else None
        elif score >= -1:
            rec = "hold"
            action = "hold"
            confidence = 60 - abs(score) * 10
            alert_price = current_price * 1.03 if current_price else None
        elif score >= -3:
            rec = "reduce"
            action = "trim"
            confidence = 60 + abs(score) * 10
            alert_price = current_price * 1.05 if current_price else None
        else:
            rec = "sell"
            action = "exit"
            confidence = 80 + abs(score) * 3
            alert_price = stop_loss if stop_loss else (current_price * 0.98 if current_price else None)

        # Cap confidence
        confidence = max(0, min(100, confidence))

        # Build reasoning
        reasoning_lines = [
            f"Position Analysis for {entry.get('symbol', 'Unknown')}:",
            f"  • Entry Price: ${entry.get('entry_price', 'N/A')}, Current: ${current_price:.2f}",
            f"  • Return: {return_pct:+.2f}% (${unrealized_pnl if 'unrealized_pnl' in dir() else 'N/A'})",
            f"  • Market Trend: {trend.title()}",
            "",
            "Key Signals:",
        ]
        for sig in signals:
            reasoning_lines.append(f"  {sig}")
        reasoning_lines.append("")
        reasoning_lines.append(f"Composite Score: {score}/+5 → Recommendation: {rec.upper().replace('_', ' ')}")
        reasoning_lines.append(f"Suggested Action: {action.upper()}")
        if alert_price:
            reasoning_lines.append(f"Watch Alert: ${alert_price:.2f}")

        reasoning = "\n".join(reasoning_lines)

        return rec, confidence, reasoning, action, alert_price

    @staticmethod
    def analyze_batch(entries: list[Dict[str, Any]], market_data: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Analyze multiple entries against fetched market data."""
        results = []
        print(f"\n🧠 Analyzing {len(entries)} entr(y/ies)...")
        for i, entry in enumerate(entries, 1):
            sym = entry.get("symbol", "UNKNOWN")
            market = market_data.get(sym)
            print(f"  [{i}/{len(entries)}] {sym} ...", end=" ")
            if not market:
                print("⚠️ No market data")
                continue
            analysis = AnalysisEngine.analyze_entry(entry, market)
            results.append(analysis)
            rec = analysis.get("recommendation", "unknown")
            conf = analysis.get("confidence", 0)
            ret = analysis.get("return_pct", 0)
            print(f"{rec.upper()} (conf={conf}%, ret={ret:+.1f}%)")
        return results


if __name__ == "__main__":
    # Quick test with sample data
    test_entry = {
        "id": 1,
        "symbol": "AAPL",
        "entry_price": 180.00,
        "quantity": 10,
        "direction": "long",
        "stop_loss": 165.00,
        "take_profit": 210.00,
        "strategy": "momentum",
    }
    test_market = {
        "current_price": 185.50,
        "fifty_day_ma": 175.00,
        "two_hundred_day_ma": 170.00,
        "fifty_two_week_high": 200.00,
        "fifty_two_week_low": 150.00,
        "change_pct": 1.2,
    }
    print("=" * 60)
    print("AIFXBOT Analysis Engine - Test")
    print("=" * 60)
    result = AnalysisEngine.analyze_entry(test_entry, test_market)
    print(f"\nReturn: {result['return_pct']:+.2f}%")
    print(f"Recommendation: {result['recommendation'].upper()}")
    print(f"Confidence: {result['confidence']}%")
    print(f"Action: {result['suggested_action']}")
    print("\nReasoning:")
    print(result['reasoning'])
    print("=" * 60)
