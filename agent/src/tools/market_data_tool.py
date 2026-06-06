"""Market data tool: fetch OHLCV data from yfinance, OKX, AKShare, tushare, ccxt.

Available as a local tool in chat mode so the agent can get real prices
without needing the separate MCP server process.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from src.agent.tools import BaseTool

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROWS = 250

_SOURCE_PATTERNS = [
    (re.compile(r"^\d{6}\.(SZ|SH)$", re.I), "mootdx"),      # A-shares via 通达信 TCP (free, no auth)
    (re.compile(r"^\d{6}\.BJ$", re.I), "tushare"),           # 北交所 (mootdx doesn't serve BJ)
    (re.compile(r"^[A-Z]+\.US$", re.I), "yfinance"),          # US equities
    (re.compile(r"^\d{3,5}\.HK$", re.I), "yfinance"),         # HK equities
    (re.compile(r"^[A-Z]+-USDT$", re.I), "okx"),              # Crypto via OKX
    (re.compile(r"^[A-Z]+/USDT$", re.I), "ccxt"),             # Crypto via CCXT
]


def _detect_source(code: str) -> str:
    for pattern, source in _SOURCE_PATTERNS:
        if pattern.match(code):
            return source
    return "tushare"


def _get_loader(source: str):
    from backtest.loaders.registry import get_loader_cls_with_fallback
    return get_loader_cls_with_fallback(source)


def _cap_rows(records: list, max_rows: int) -> list | dict[str, object]:
    n = len(records)
    if max_rows < 0:
        max_rows = DEFAULT_MAX_ROWS
    if max_rows == 0 or n <= max_rows:
        return records
    step = math.ceil(n / max_rows)
    sampled = records[::step]
    if sampled[-1] is not records[-1]:
        sampled = sampled + [records[-1]]
    return {
        "rows": n,
        "returned": len(sampled),
        "truncated": True,
        "policy": f"every-{step}th-row (even stride; last bar pinned)",
        "hint": "narrow the date range, coarsen interval, or set max_rows=0 for all rows",
        "data": sampled,
    }


class GetMarketDataTool(BaseTool):
    """Fetch current and historical OHLCV market data for stocks and crypto."""

    name = "get_market_data"

    @classmethod
    def check_available(cls) -> bool:
        return True

    description = (
        "Fetch OHLCV market data for stocks, crypto, or mixed symbols. "
        "Use this to get current prices BEFORE answering any question about "
        "a ticker, stock, or asset. Never answer with prices from memory — "
        "always call this tool first.\n\n"
        "Symbol formats:\n"
        "- US stocks: AAPL.US, TSLA.US\n"
        "- HK stocks: 700.HK, 9988.HK\n"
        "- A-shares: 000001.SZ, 600000.SH\n"
        "- Crypto: BTC-USDT, ETH-USDT\n\n"
        "Sources (auto-detected by symbol format):\n"
        "- yfinance: HK/US equities (free)\n"
        "- OKX: cryptocurrency (free)\n"
        "- tushare: China A-shares (requires TUSHARE_TOKEN)\n"
        "- akshare: multi-market fallback (free)\n"
        "- ccxt: crypto from 100+ exchanges (free)"
    )
    parameters = {
        "type": "object",
        "properties": {
            "codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of symbols (e.g. ['AAPL.US', 'BTC-USDT', '000001.SZ'])",
            },
            "start_date": {
                "type": "string",
                "description": "Start date (YYYY-MM-DD). For current price, use a recent date.",
            },
            "end_date": {
                "type": "string",
                "description": "End date (YYYY-MM-DD). For current price, use today's date.",
            },
            "source": {
                "type": "string",
                "description": "Data source: 'auto' (recommended), 'yfinance', 'okx', 'tushare', 'akshare', 'ccxt'",
                "default": "auto",
            },
            "interval": {
                "type": "string",
                "description": "Bar size: 1D (daily, default), 1H, 4H",
                "default": "1D",
            },
        },
        "required": ["codes", "start_date", "end_date"],
    }
    is_readonly = True
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        codes = kwargs["codes"]
        start_date = kwargs["start_date"]
        end_date = kwargs["end_date"]
        source = kwargs.get("source", "auto")
        interval = kwargs.get("interval", "1D")
        max_rows = int(kwargs.get("max_rows", DEFAULT_MAX_ROWS))

        results = {}

        if source == "auto":
            groups: dict[str, list[str]] = {}
            for code in codes:
                src = _detect_source(code)
                groups.setdefault(src, []).append(code)
        else:
            groups = {source: list(codes)}

        for src, src_codes in groups.items():
            try:
                loader_cls = _get_loader(src)
                loader = loader_cls()
                data_map = loader.fetch(src_codes, start_date, end_date, interval=interval)
            except Exception:
                logger.exception(
                    "market-data loader %r failed for %s", src, src_codes
                )
                data_map = {}

            for symbol, df in data_map.items():
                records = df.reset_index().to_dict(orient="records")
                for r in records:
                    for k, v in r.items():
                        if hasattr(v, "isoformat"):
                            r[k] = v.isoformat()
                        elif hasattr(v, "item"):
                            r[k] = v.item()
                results[symbol] = _cap_rows(records, max_rows)

        unresolved = [c for c in codes if c not in results]
        if unresolved:
            results["_unresolved"] = unresolved

        return json.dumps(results, ensure_ascii=False, indent=2)
