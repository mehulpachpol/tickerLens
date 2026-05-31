from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote


def _now_iso_date() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def _redis_client():
    try:
        import redis  # type: ignore

        from tickerlens_api.settings import settings

        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


_REDIS = _redis_client()


def normalize_yahoo_symbol(*, ticker: str, default_exchange_suffix: str = ".NS") -> str:
    """
    Convert a plain NSE ticker (e.g. "INFY") into a Yahoo Finance symbol (e.g. "INFY.NS").

    If the caller already provided a Yahoo-style symbol ("TCS.NS"), it is preserved.
    """

    t = (ticker or "").strip().upper()
    if not t:
        raise ValueError("ticker is required")
    if "." in t:
        return t
    return f"{t}{default_exchange_suffix}"


def yahoo_quote_url(symbol: str) -> str:
    safe = quote(symbol, safe="")
    return f"https://finance.yahoo.com/quote/{safe}"


def make_yahoo_doc_id(symbol: str) -> str:
    """
    Doc id namespace for non-PDF tool sources.
    Used by the UI to open sources via /documents/{doc_id}/download.
    """

    return f"yf:{symbol}"


def make_yahoo_chunk_id(symbol: str) -> str:
    return f"yf:{symbol}:fundamentals"


def _format_number(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        # Keep small numbers readable, but avoid scientific for large ints.
        if isinstance(v, float):
            if abs(v) < 1 and v != 0:
                return f"{v:.4f}".rstrip("0").rstrip(".")
            return f"{v:.4f}".rstrip("0").rstrip(".")
        return str(v)
    return str(v)


def _pick(info: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in info and info[k] is not None:
            return info[k]
    return None


def _truncate(text: str | None, max_chars: int) -> str | None:
    if not text:
        return None
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3].rstrip() + "..."


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _pct(v: Any) -> str | None:
    f = _safe_float(v)
    if f is None:
        return None
    return f"{f * 100:.2f}%"


def _first_report_period(table: dict[Any, dict[str, Any]] | None) -> tuple[str | None, dict[str, Any] | None]:
    if not table:
        return None, None
    # yfinance returns dict keyed by pd.Timestamp; choose most recent date.
    try:
        keys = sorted(table.keys(), reverse=True)
    except Exception:
        keys = list(table.keys())
    if not keys:
        return None, None
    k = keys[0]
    try:
        iso = dt.date.fromisoformat(str(k)[:10]).isoformat()
    except Exception:
        iso = str(k)
    return iso, table.get(k) or None


def _coerce_major_holders(df: Any) -> dict[str, Any] | None:
    try:
        if df is None:
            return None
        if getattr(df, "empty", False):
            return None
        out: dict[str, Any] = {}
        # Expected columns: Breakdown, Value (but yfinance sometimes uses index)
        if "Breakdown" in df.columns and "Value" in df.columns:
            for _, row in df.iterrows():
                out[str(row.get("Breakdown"))] = row.get("Value")
            return out or None
        # Fallback: first column is values, index is breakdown
        if len(df.columns) >= 1:
            col = df.columns[0]
            for idx, row in df.iterrows():
                out[str(idx)] = row.get(col)
            return out or None
    except Exception:
        return None
    return None


def _coerce_holders(df: Any, *, limit: int) -> list[dict[str, Any]] | None:
    try:
        if df is None:
            return None
        if getattr(df, "empty", False):
            return None
        rows: list[dict[str, Any]] = []
        for _, row in df.head(limit).iterrows():
            d = {}
            for k in df.columns:
                v = row.get(k)
                if v is None:
                    continue
                d[str(k)] = v
            if d:
                rows.append(d)
        return rows or None
    except Exception:
        return None


@dataclass(frozen=True)
class YahooFundamentalsSnapshot:
    yahoo_symbol: str
    as_of: str
    info: dict[str, Any]

    income_stmt_period: str | None = None
    income_stmt: dict[str, Any] | None = None
    balance_sheet_period: str | None = None
    balance_sheet: dict[str, Any] | None = None
    cashflow_period: str | None = None
    cashflow: dict[str, Any] | None = None

    major_holders: dict[str, Any] | None = None
    institutional_holders: list[dict[str, Any]] | None = None
    mutualfund_holders: list[dict[str, Any]] | None = None


_CACHE: dict[str, tuple[float, YahooFundamentalsSnapshot]] = {}


def get_yahoo_fundamentals(
    *,
    ticker: str,
    exchange_suffix: str = ".NS",
    cache_ttl_s: int = 15 * 60,
    holders_limit: int = 10,
    include_statements: bool = True,
    include_holders: bool = True,
) -> YahooFundamentalsSnapshot:
    """
    Best-effort fundamentals snapshot using the free yfinance data source.

    Notes:
    - Yahoo Finance is unofficial/unversioned; fields can be missing.
    - This function is designed to be safe-to-fail and cacheable.
    """

    yahoo_symbol = normalize_yahoo_symbol(ticker=ticker, default_exchange_suffix=exchange_suffix)
    now = time.time()
    cached = _CACHE.get(yahoo_symbol)
    if cached and cached[0] > now:
        return cached[1]

    import yfinance as yf

    t = yf.Ticker(yahoo_symbol)
    info: dict[str, Any] = {}
    try:
        # Prefer method if available to avoid property caching quirks.
        getter = getattr(t, "get_info", None)
        if callable(getter):
            info = getter() or {}
        else:
            info = getattr(t, "info", {}) or {}
    except Exception:
        info = {}

    income_stmt_period = None
    income_stmt = None
    balance_sheet_period = None
    balance_sheet = None
    cashflow_period = None
    cashflow = None

    if include_statements:
        try:
            get_income = getattr(t, "get_income_stmt", None) or getattr(t, "get_incomestmt", None)
            if callable(get_income):
                table = get_income(as_dict=True, pretty=True, freq="yearly")
                income_stmt_period, income_stmt = _first_report_period(table)
        except Exception:
            income_stmt_period, income_stmt = None, None
        try:
            get_bs = getattr(t, "get_balance_sheet", None) or getattr(t, "get_balancesheet", None)
            if callable(get_bs):
                table = get_bs(as_dict=True, pretty=True, freq="yearly")
                balance_sheet_period, balance_sheet = _first_report_period(table)
        except Exception:
            balance_sheet_period, balance_sheet = None, None
        try:
            get_cf = getattr(t, "get_cash_flow", None) or getattr(t, "get_cashflow", None)
            if callable(get_cf):
                table = get_cf(as_dict=True, pretty=True, freq="yearly")
                cashflow_period, cashflow = _first_report_period(table)
        except Exception:
            cashflow_period, cashflow = None, None

    major_holders = None
    institutional_holders = None
    mutualfund_holders = None
    if include_holders:
        try:
            getter = getattr(t, "get_major_holders", None)
            mh = getter() if callable(getter) else getattr(t, "major_holders", None)
            major_holders = _coerce_major_holders(mh)
        except Exception:
            major_holders = None
        try:
            getter = getattr(t, "get_institutional_holders", None)
            ih = getter() if callable(getter) else getattr(t, "institutional_holders", None)
            institutional_holders = _coerce_holders(ih, limit=holders_limit)
        except Exception:
            institutional_holders = None
        try:
            getter = getattr(t, "get_mutualfund_holders", None)
            mf = getter() if callable(getter) else getattr(t, "mutualfund_holders", None)
            mutualfund_holders = _coerce_holders(mf, limit=holders_limit)
        except Exception:
            mutualfund_holders = None

    snap = YahooFundamentalsSnapshot(
        yahoo_symbol=yahoo_symbol,
        as_of=_now_iso_date(),
        info=info or {},
        income_stmt_period=income_stmt_period,
        income_stmt=income_stmt,
        balance_sheet_period=balance_sheet_period,
        balance_sheet=balance_sheet,
        cashflow_period=cashflow_period,
        cashflow=cashflow,
        major_holders=major_holders,
        institutional_holders=institutional_holders,
        mutualfund_holders=mutualfund_holders,
    )

    _CACHE[yahoo_symbol] = (now + max(0, int(cache_ttl_s)), snap)
    return snap


@dataclass(frozen=True)
class YahooFundamentalsContext:
    yahoo_symbol: str
    as_of: str
    context_text: str


def get_yahoo_fundamentals_context(
    *,
    ticker: str,
    exchange_suffix: str = ".NS",
    cache_ttl_s: int = 15 * 60,
    holders_limit: int = 10,
    include_statements: bool = True,
    include_holders: bool = True,
    summary_max_chars: int = 900,
) -> YahooFundamentalsContext:
    """
    Redis-cached wrapper that returns a ready-to-inject context string.

    We cache the *rendered* context (string) instead of the raw snapshot because yfinance
    objects can contain non-JSON-serializable values (e.g., pandas timestamps).
    """

    yahoo_symbol = normalize_yahoo_symbol(ticker=ticker, default_exchange_suffix=exchange_suffix)
    as_of = _now_iso_date()
    cache_key = f"cache:yf:fundamentals:{yahoo_symbol}:{as_of}"

    if _REDIS:
        try:
            cached = _REDIS.get(cache_key)
            if cached:
                return YahooFundamentalsContext(yahoo_symbol=yahoo_symbol, as_of=as_of, context_text=cached)
        except Exception:
            pass

    snap = get_yahoo_fundamentals(
        ticker=yahoo_symbol,
        exchange_suffix=exchange_suffix,
        cache_ttl_s=cache_ttl_s,
        holders_limit=holders_limit,
        include_statements=include_statements,
        include_holders=include_holders,
    )
    ctx = snapshot_to_context_text(snap, summary_max_chars=summary_max_chars)

    if _REDIS:
        try:
            _REDIS.set(cache_key, ctx, ex=max(1, int(cache_ttl_s)))
        except Exception:
            pass

    return YahooFundamentalsContext(yahoo_symbol=yahoo_symbol, as_of=snap.as_of, context_text=ctx)


def snapshot_to_context_text(snapshot: YahooFundamentalsSnapshot, *, summary_max_chars: int = 900) -> str:
    """
    Convert a snapshot into a compact, model-readable context block.
    """

    info = snapshot.info or {}
    lines: list[str] = []
    lines.append("SOURCE: Yahoo Finance (via yfinance)")
    lines.append(f"symbol: {snapshot.yahoo_symbol}")
    lines.append(f"as_of: {snapshot.as_of}")

    name = _pick(info, "longName", "shortName")
    if name:
        lines.append(f"company_name: {name}")
    sector = _pick(info, "sector")
    industry = _pick(info, "industry")
    if sector:
        lines.append(f"sector: {sector}")
    if industry:
        lines.append(f"industry: {industry}")
    emp = _pick(info, "fullTimeEmployees")
    if emp is not None:
        lines.append(f"full_time_employees: {_format_number(emp)}")
    website = _pick(info, "website")
    if website:
        lines.append(f"website: {website}")

    lines.append("")
    lines.append("KEY_METRICS:")
    mapping = [
        ("market_cap", ("marketCap",)),
        ("enterprise_value", ("enterpriseValue",)),
        ("trailing_pe", ("trailingPE",)),
        ("forward_pe", ("forwardPE",)),
        ("peg_ratio", ("pegRatio",)),
        ("price_to_book", ("priceToBook",)),
        ("price_to_sales", ("priceToSalesTrailing12Months",)),
        ("beta", ("beta",)),
        ("52w_high", ("fiftyTwoWeekHigh",)),
        ("52w_low", ("fiftyTwoWeekLow",)),
        ("50d_ma", ("fiftyDayAverage",)),
        ("200d_ma", ("twoHundredDayAverage",)),
        ("current_ratio", ("currentRatio",)),
        ("debt_to_equity", ("debtToEquity",)),
        ("total_cash", ("totalCash",)),
        ("total_debt", ("totalDebt",)),
        ("roe", ("returnOnEquity",)),
        ("roa", ("returnOnAssets",)),
        ("gross_margin", ("grossMargins",)),
        ("operating_margin", ("operatingMargins",)),
        ("net_profit_margin", ("profitMargins",)),
    ]
    for out_key, in_keys in mapping:
        v = _pick(info, *in_keys)
        if v is None:
            continue
        if out_key.endswith("_margin"):
            v_fmt = _pct(v) or _format_number(v)
        else:
            v_fmt = _format_number(v)
        lines.append(f"{out_key}: {v_fmt}")

    if snapshot.income_stmt:
        lines.append("")
        lines.append(f"INCOME_STATEMENT (yearly, period_end={snapshot.income_stmt_period}):")
        for k in (
            "Total Revenue",
            "Cost Of Revenue",
            "Gross Profit",
            "Operating Expense",
            "Operating Income",
            "EBIT",
            "EBITDA",
            "Net Income",
            "Basic EPS",
            "Diluted EPS",
        ):
            if k in snapshot.income_stmt and snapshot.income_stmt[k] is not None:
                lines.append(f"{k}: {_format_number(snapshot.income_stmt[k])}")

    if snapshot.balance_sheet:
        lines.append("")
        lines.append(f"BALANCE_SHEET (yearly, period_end={snapshot.balance_sheet_period}):")
        for k in (
            "Total Assets",
            "Total Liabilities Net Minority Interest",
            "Total Equity Gross Minority Interest",
            "Stockholders Equity",
            "Working Capital",
            "Cash And Cash Equivalents",
            "Retained Earnings",
            "Inventory",
            "Total Debt",
        ):
            if k in snapshot.balance_sheet and snapshot.balance_sheet[k] is not None:
                lines.append(f"{k}: {_format_number(snapshot.balance_sheet[k])}")

    if snapshot.cashflow:
        lines.append("")
        lines.append(f"CASH_FLOW (yearly, period_end={snapshot.cashflow_period}):")
        for k in (
            "Operating Cash Flow",
            "Cash Flow From Continuing Operating Activities",
            "Investing Cash Flow",
            "Financing Cash Flow",
            "Capital Expenditure",
            "Free Cash Flow",
        ):
            if k in snapshot.cashflow and snapshot.cashflow[k] is not None:
                lines.append(f"{k}: {_format_number(snapshot.cashflow[k])}")

    if snapshot.major_holders:
        lines.append("")
        lines.append("MAJOR_HOLDERS:")
        for k in (
            "insidersPercentHeld",
            "institutionsPercentHeld",
            "institutionsFloatPercentHeld",
            "institutionsCount",
        ):
            if k in snapshot.major_holders and snapshot.major_holders[k] is not None:
                v = snapshot.major_holders[k]
                if "Percent" in k:
                    lines.append(f"{k}: {_pct(v) or _format_number(v)}")
                else:
                    lines.append(f"{k}: {_format_number(v)}")

    if snapshot.institutional_holders:
        lines.append("")
        lines.append("TOP_INSTITUTIONAL_HOLDERS:")
        for row in snapshot.institutional_holders:
            holder = row.get("Holder")
            shares = row.get("Shares")
            date_reported = row.get("Date Reported")
            value = row.get("Value")
            pct_held = row.get("pctHeld")
            parts = [
                f"holder={holder}" if holder else None,
                f"shares={_format_number(shares)}" if shares is not None else None,
                f"date={date_reported}" if date_reported else None,
                f"value={_format_number(value)}" if value is not None else None,
                f"pctHeld={_format_number(pct_held)}" if pct_held is not None else None,
            ]
            parts = [p for p in parts if p]
            if parts:
                lines.append("- " + " | ".join(parts))

    if snapshot.mutualfund_holders:
        lines.append("")
        lines.append("TOP_MUTUAL_FUND_HOLDERS:")
        for row in snapshot.mutualfund_holders:
            holder = row.get("Holder")
            shares = row.get("Shares")
            date_reported = row.get("Date Reported")
            value = row.get("Value")
            pct_held = row.get("pctHeld")
            parts = [
                f"holder={holder}" if holder else None,
                f"shares={_format_number(shares)}" if shares is not None else None,
                f"date={date_reported}" if date_reported else None,
                f"value={_format_number(value)}" if value is not None else None,
                f"pctHeld={_format_number(pct_held)}" if pct_held is not None else None,
            ]
            parts = [p for p in parts if p]
            if parts:
                lines.append("- " + " | ".join(parts))

    summary = _truncate(_pick(info, "longBusinessSummary"), max_chars=summary_max_chars)
    if summary:
        lines.append("")
        lines.append("BUSINESS_SUMMARY:")
        lines.append(summary)

    return "\n".join(lines).strip()
