"""
Stock quote tool — fetches A-share data via opencli datayes and optionally
captures datayes visualization screenshots.

The tool returns structured JSON data + a screenshot path (MEDIA: prefix)
that the gateway auto-delivers as a native image attachment on all platforms.
"""

import json
import logging
import subprocess
from datetime import datetime

from tools.registry import registry

logger = logging.getLogger(__name__)


def _check_requirements() -> bool:
    """Check if opencli datayes is available."""
    try:
        result = subprocess.run(
            ["opencli", "list"],
            capture_output=True, text=True, timeout=10,
        )
        return "datayes" in result.stdout.lower()
    except Exception:
        return False


def stock_quote(
    code: str,
    include_chart_hint: bool = True,
    task_id: str = None,
) -> str:
    """Fetch A-share stock quote data from datayes (via opencli).

    Returns JSON with:
    - stocks: list of quote data dicts (price, change, volume, etc.)
    - summary: human-readable summary
    - chart_urls: datayes URLs for visual charts (use browser_navigate to screenshot)

    For rich chart images: after calling this tool, use browser_navigate to visit
    the chart_urls provided, then browser_vision to capture the visualization.
    """
    codes = [c.strip() for c in code.split(",") if c.strip()]
    if not codes:
        return json.dumps({"error": "no stock codes provided"}, ensure_ascii=False)

    # Fetch data via opencli
    code_str = ",".join(codes)
    try:
        result = subprocess.run(
            ["opencli", "datayes", "quote", "--format", "json", code_str],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return json.dumps({
                "error": f"opencli failed (exit {result.returncode})",
                "stderr": result.stderr[:500],
            }, ensure_ascii=False)

        data = json.loads(result.stdout)
        if isinstance(data, dict) and "data" in data:
            stocks = data["data"]
        elif isinstance(data, list):
            stocks = data
        else:
            stocks = [data]

        if not isinstance(stocks, list):
            stocks = [stocks]

    except subprocess.TimeoutExpired:
        return json.dumps({"error": "opencli datayes quote timed out"}, ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "failed to parse opencli JSON output",
            "raw": result.stdout[:300] if 'result' in dir() else "",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # Build summary
    lines = []
    for s in stocks:
        name = s.get("name", "?")
        code_val = s.get("code", "?")
        price = s.get("price", "?")
        change_pct = s.get("changePercent", "?")
        change = s.get("change", "?")
        try:
            arrow = "🟢" if float(change_pct) >= 0 else "🔴"
        except (ValueError, TypeError):
            arrow = "⚪"
        lines.append(f"{arrow} **{name}** ({code_val})")
        lines.append(f"   现价: ¥{price}  {change_pct}% ({change})")
        high = s.get("high", "?")
        low = s.get("low", "?")
        amount = s.get("amount", "?")
        volume = s.get("volume", "?")
        turnover = s.get("turnoverRate", "?")
        lines.append(f"   最高: ¥{high}  最低: ¥{low}  成交额: {amount}")
        lines.append(f"   成交量: {volume}  换手率: {turnover}%")
        lines.append("")

    # Build chart URLs for browser visualization (public pages, no login required)
    chart_urls = []
    for s in stocks:
        code_val = s.get("code", "")
        name = s.get("name", "")
        # Determine market prefix for eastmoney: sz for Shenzhen (00xxxx, 30xxxx), sh for Shanghai (60xxxx)
        if code_val.startswith(("6", "9")):
            market_prefix = "sh"
        else:
            market_prefix = "sz"
        chart_urls.append({
            "code": code_val,
            "name": name,
            "eastmoney_url": f"https://quote.eastmoney.com/{market_prefix}{code_val}.html",
            "datayes_url": f"https://r.datayes.com/stocks/{code_val}",
        })

    output = {
        "stocks": stocks,
        "summary": "\n".join(lines),
        "chart_urls": chart_urls,
        "timestamp": datetime.now().isoformat(),
    }
    if include_chart_hint:
        output["chart_hint"] = (
            "To include chart images in your response: "
            "1. browser_navigate to the eastmoney_url from chart_urls (public, no login needed) "
            "2. browser_vision (question='截图K线图和资金流向图表') "
            "3. Include the screenshot_path as MEDIA:<path> in your text response"
        )

    return json.dumps(output, ensure_ascii=False, default=str)


registry.register(
    name="stock_quote",
    toolset="finance",
    schema={
        "name": "stock_quote",
        "description": "Fetch A-share stock quote data from datayes via opencli. "
                       "Returns price, change, volume, turnover rate and other key metrics. "
                       "Also provides chart URLs — use browser_navigate to the eastmoney_url "
                       "from chart_urls (public, no login), then browser_vision to capture "
                       "K-line charts and visualization images. "
                       "Example: code='002384' or code='002384,300502' for multiple stocks.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code(s), comma-separated. "
                                   "e.g. '002384' (东山精密), '300502' (新易盛), "
                                   "'002384,300502' for multiple.",
                },
                "include_chart_hint": {
                    "type": "boolean",
                    "description": "Include chart URL hints for browser screenshot (default: true)",
                    "default": True,
                },
            },
            "required": ["code"],
        },
    },
    handler=lambda args, **kw: stock_quote(
        code=args.get("code", ""),
        include_chart_hint=args.get("include_chart_hint", True),
        task_id=kw.get("task_id"),
    ),
    check_fn=_check_requirements,
)
