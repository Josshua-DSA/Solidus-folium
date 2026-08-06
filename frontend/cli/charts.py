import math
from rich.text import Text


def plot_ascii_line(data: list, width: int = 40, height: int = 6) -> Text:
    """
    Plots a real-time dynamic ASCII line chart from a sequence of numeric data points.
    Returns a rich.text.Text object ready for direct rendering.
    """
    result = Text()
    
    if not data:
        result.append("  [ NO HISTORICAL DATA AVAILABLE ]")
        return result
        
    if len(data) > width:
        chunk_size = len(data) / width
        sampled = []
        for i in range(width):
            start = int(i * chunk_size)
            end = int((i + 1) * chunk_size)
            chunk = data[start:max(start+1, end)]
            sampled.append(sum(chunk) / len(chunk))
        data = sampled
    elif len(data) < width:
        stretched = []
        for i in range(width):
            idx = int((i / width) * len(data))
            stretched.append(data[idx])
        data = stretched

    val_min = min(data)
    val_max = max(data)
    val_range = val_max - val_min if val_max > val_min else 1.0
    
    canvas = [[" " for _ in range(width)] for _ in range(height)]
    
    for col, val in enumerate(data):
        normalized = (val - val_min) / val_range
        row = int(normalized * (height - 1))
        row = max(0, min(height - 1, row))
        canvas_row = (height - 1) - row
        canvas[canvas_row][col] = "●"

    for c in range(width - 1):
        r1 = height - 1 - int(((data[c] - val_min) / val_range) * (height - 1))
        r2 = height - 1 - int(((data[c+1] - val_min) / val_range) * (height - 1))
        
        step = 1 if r2 > r1 else -1
        for r in range(r1, r2 + step, step):
            if 0 <= r < height:
                if canvas[r][c] == " ":
                    canvas[r][c] = "·"

    for r in range(height):
        y_val = val_max - (r / (height - 1)) * val_range if height > 1 else val_max
        if y_val >= 1e6:
            label = f"{y_val / 1e6:.1f}M"
        else:
            label = f"{y_val:,.0f}"
            
        result.append(f"{label:>8} │ ", style="dim")
        
        row_str = "".join(canvas[r])
        line_color = "#A3BE8C" if data[-1] >= data[0] else "#BF616A"
        result.append(row_str, style=line_color)
        result.append("\n")
        
    result.append(" " * 9 + "└" + "─" * width, style="dim")
    result.append("\n")
    
    return result


from typing import Optional

def plot_ascii_candlestick(ohlcv_data: list, width: int = 52, height: int = 8, support_price: Optional[float] = None, resistance_price: Optional[float] = None) -> Text:
    """
    Plots an advanced ASCII Candlestick + Volume Combo Chart with Support/Resistance overlay.
    Returns a rich.text.Text object formatted natively.
    """
    result = Text()
    
    if not ohlcv_data:
        result.append("  [ NO OHLCV PRICE HISTORY AVAILABLE ]")
        return result
        
    if len(ohlcv_data) > width:
        chunk_size = len(ohlcv_data) / width
        sampled = []
        for i in range(width):
            start = int(i * chunk_size)
            end = int((i + 1) * chunk_size)
            chunk = ohlcv_data[start:max(start+1, end)]
            avg_open = chunk[0]['open']
            avg_close = chunk[-1]['close']
            avg_high = max(x['high'] for x in chunk)
            avg_low = min(x['low'] for x in chunk)
            avg_vol = sum(x.get('volume', 100000) for x in chunk) / len(chunk)
            sampled.append({'open': avg_open, 'high': avg_high, 'low': avg_low, 'close': avg_close, 'volume': avg_vol})
        ohlcv_data = sampled
    elif len(ohlcv_data) < width:
        stretched = []
        for i in range(width):
            idx = int((i / width) * len(ohlcv_data))
            stretched.append(ohlcv_data[idx])
        ohlcv_data = stretched

    all_prices = []
    for d in ohlcv_data:
        all_prices.extend([d['open'], d['high'], d['low'], d['close']])
        
    if support_price: all_prices.append(support_price)
    if resistance_price: all_prices.append(resistance_price)
        
    val_min = min(all_prices)
    val_max = max(all_prices)
    val_range = val_max - val_min if val_max > val_min else 1.0

    canvas = [[(" ", "") for _ in range(width)] for _ in range(height)]

    # Draw Candlesticks
    for col, day in enumerate(ohlcv_data):
        o, h, l, c = day['open'], day['high'], day['low'], day['close']
        
        def to_row(val):
            norm = (val - val_min) / val_range
            r = int(norm * (height - 1))
            return (height - 1) - max(0, min(height - 1, r))

        r_open = to_row(o)
        r_close = to_row(c)
        r_high = to_row(h)
        r_low = to_row(l)

        is_bullish = c >= o
        color_style = "#A3BE8C" if is_bullish else "#BF616A"
        body_char = "█" if is_bullish else "▒"

        # Wicks
        wick_start = min(r_high, r_low)
        wick_end = max(r_high, r_low)
        for r in range(wick_start, wick_end + 1):
            canvas[r][col] = ("│", color_style)

        # Body
        body_start = min(r_open, r_close)
        body_end = max(r_open, r_close)
        for r in range(body_start, body_end + 1):
            canvas[r][col] = (body_char, color_style)

    # Render Candlestick rows with price scale & Support/Resistance Indicators
    for r in range(height):
        y_val = val_max - (r / (height - 1)) * val_range if height > 1 else val_max
        label = f"Rp {y_val:,.0f}"
        
        # Check overlay tag
        tag_style = "dim"
        tag_prefix = " "
        if resistance_price and abs(y_val - resistance_price) / val_range < 0.08:
            tag_style = "bold #D08770"
            tag_prefix = "R"
        elif support_price and abs(y_val - support_price) / val_range < 0.08:
            tag_style = "bold #81A1C1"
            tag_prefix = "S"
            
        result.append(f"{label:>11} {tag_prefix}│ ", style=tag_style)
        
        for col in range(width):
            char, style = canvas[r][col]
            if style:
                result.append(char, style=style)
            else:
                result.append(char)
                
        result.append("\n")
        
    result.append(" " * 14 + "└" + "─" * width, style="dim")
    result.append("\n")
    
    # Draw Volume Sub-Chart (2 Rows)
    volumes = [d.get('volume', 100000) for d in ohlcv_data]
    max_vol = max(volumes) if max(volumes) > 0 else 1.0
    
    vol_row1 = []
    vol_row2 = []
    
    for col, day in enumerate(ohlcv_data):
        v = day.get('volume', 100000)
        norm_v = v / max_vol
        is_bullish = day['close'] >= day['open']
        color = "#A3BE8C" if is_bullish else "#BF616A"
        
        if norm_v >= 0.75:
            vol_row1.append(("█", color))
            vol_row2.append(("█", color))
        elif norm_v >= 0.40:
            vol_row1.append((" ", color))
            vol_row2.append(("█", color))
        elif norm_v >= 0.15:
            vol_row1.append((" ", color))
            vol_row2.append(("▄", color))
        else:
            vol_row1.append((" ", color))
            vol_row2.append((" ", color))

    result.append(f"{'VOL (M)':>12} │ ", style="dim")
    for char, style in vol_row1:
        result.append(char, style=style)
    result.append("\n")
    
    result.append(f"{max_vol/1e6:>11.1f}M │ ", style="dim")
    for char, style in vol_row2:
        result.append(char, style=style)
    result.append("\n")
    
    return result
