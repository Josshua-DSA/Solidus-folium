import json
import os
import random

def generate_candlestick_html(ticker: str, ohlcv_data: list, output_path: str = "/tmp/fincept_chart.html") -> str:
    """
    Generates a high-performance interactive TradingView Lightweight Charts HTML file.
    
    Args:
        ticker: The stock symbol (e.g., 'BBCA.JK')
        ohlcv_data: A list of dicts with: 'date' (YYYY-MM-DD), 'open', 'high', 'low', 'close', 'volume'
        output_path: Path where the HTML file will be saved.
    Returns:
        The absolute path to the generated HTML.
    """
    # Ensure correct format for Lightweight Charts (timestamp or YYYY-MM-DD string)
    formatted_candles = []
    formatted_volumes = []
    
    for i, d in enumerate(ohlcv_data):
        date_str = d.get('date')
        if not date_str:
            # Fallback dates if missing
            from datetime import datetime, timedelta
            date_str = (datetime.now() - timedelta(days=len(ohlcv_data) - i)).strftime("%Y-%m-%d")
            
        candle = {
            "time": date_str,
            "open": float(d["open"]),
            "high": float(d["high"]),
            "low": float(d["low"]),
            "close": float(d["close"])
        }
        volume = {
            "time": date_str,
            "value": float(d.get("volume", 0)),
            "color": "rgba(46, 204, 113, 0.4)" if d["close"] >= d["open"] else "rgba(231, 76, 60, 0.4)"
        }
        formatted_candles.append(candle)
        formatted_volumes.append(volume)

    # TradingView Lightweight Charts template styled with Nord Theme
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Fincept Interactive Chart: {ticker}</title>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body {{
            background-color: #2E3440;
            color: #D8DEE9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 10px;
            overflow: hidden;
        }}
        #container {{
            width: 100vw;
            height: 92vh;
        }}
        #header {{
            padding: 5px 15px;
            background-color: #3B4252;
            border-bottom: 2px solid #88C0D0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-radius: 4px;
            margin-bottom: 10px;
        }}
        .ticker {{
            font-size: 20px;
            font-weight: bold;
            color: #88C0D0;
        }}
        .status {{
            font-size: 13px;
            color: #A3BE8C;
        }}
    </style>
</head>
<body>
    <div id="header">
        <div class="ticker">📊 {ticker} Equity Research Desk</div>
        <div class="status">● Sandbox Active | TradingView Engine</div>
    </div>
    <div id="container"></div>

    <script>
        const chart = LightweightCharts.createChart(document.getElementById('container'), {{
            width: window.innerWidth - 20,
            height: window.innerHeight - 80,
            layout: {{
                backgroundColor: '#2E3440',
                textColor: '#D8DEE9',
            }},
            grid: {{
                vertLines: {{ color: '#3B4252' }},
                horzLines: {{ color: '#3B4252' }},
            }},
            crosshair: {{
                mode: LightweightCharts.CrosshairMode.Normal,
            }},
            rightPriceScale: {{
                borderColor: '#4C566A',
            }},
            timeScale: {{
                borderColor: '#4C566A',
            }},
        }});

        const candlestickSeries = chart.addCandlestickSeries({{
            upColor: '#A3BE8C',
            downColor: '#BF616A',
            borderDownColor: '#BF616A',
            borderUpColor: '#A3BE8C',
            wickDownColor: '#BF616A',
            wickUpColor: '#A3BE8C',
        }});

        const volumeSeries = chart.addHistogramSeries({{
            color: '#26a69a',
            priceFormat: {{
                type: 'volume',
            }},
            priceScaleId: '',
            scaleMargins: {{
                top: 0.8,
                bottom: 0,
            }},
        }});

        const candleData = {json.dumps(formatted_candles)};
        const volumeData = {json.dumps(formatted_volumes)};

        candlestickSeries.setData(candleData);
        volumeSeries.setData(volumeData);

        // Auto-fit content
        chart.timeScale().fitContent();

        // Responsive resize
        window.addEventListener('resize', () => {{
            chart.resize(window.innerWidth - 20, window.innerHeight - 80);
        }});
    </script>
</body>
</html>
"""
    with open(output_path, "w") as f:
        f.write(html_content)
        
    return output_path
