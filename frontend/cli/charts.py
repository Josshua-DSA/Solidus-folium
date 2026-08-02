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
        
    # Standardise length to match width
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
    
    # Create empty character canvas grid
    canvas = [[" " for _ in range(width)] for _ in range(height)]
    
    # Map values to rows (0 is bottom, height-1 is top)
    for col, val in enumerate(data):
        normalized = (val - val_min) / val_range
        row = int(normalized * (height - 1))
        row = max(0, min(height - 1, row))
        canvas_row = (height - 1) - row
        canvas[canvas_row][col] = "●"

    # Draw lines connecting dots where possible
    for c in range(width - 1):
        r1 = height - 1 - int(((data[c] - val_min) / val_range) * (height - 1))
        r2 = height - 1 - int(((data[c+1] - val_min) / val_range) * (height - 1))
        
        step = 1 if r2 > r1 else -1
        for r in range(r1, r2 + step, step):
            if 0 <= r < height:
                if canvas[r][c] == " ":
                    canvas[r][c] = "·"

    # Build final Text object with Y-axis labels
    for r in range(height):
        y_val = val_max - (r / (height - 1)) * val_range if height > 1 else val_max
        if y_val >= 1e6:
            label = f"{y_val / 1e6:.1f}M"
        else:
            label = f"{y_val:,.0f}"
            
        result.append(f"{label:>8} │ ", style="dim")
        
        row_str = "".join(canvas[r])
        # Color the line: green if uptrend overall, blue otherwise
        line_color = "#A3BE8C" if data[-1] >= data[0] else "#BF616A"
        result.append(row_str, style=line_color)
        result.append("\n")
        
    # Add timeline border bottom
    result.append(" " * 9 + "└" + "─" * width, style="dim")
    result.append("\n")
    
    return result


def plot_ascii_candlestick(ohlcv_data: list, width: int = 50, height: int = 7) -> Text:
    """
    Plots an ASCII Candlestick chart from a list of dicts with keys: 'open', 'high', 'low', 'close'.
    Returns a rich.text.Text object with proper green/red coloring applied natively.
    """
    result = Text()
    
    if not ohlcv_data:
        result.append("  [ NO OHLCV PRICE HISTORY AVAILABLE ]")
        return result
        
    # Scale data length to target width
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
            sampled.append({'open': avg_open, 'high': avg_high, 'low': avg_low, 'close': avg_close})
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
        
    val_min = min(all_prices)
    val_max = max(all_prices)
    val_range = val_max - val_min if val_max > val_min else 1.0

    # Canvas stores (character, color_style) tuples
    canvas = [[(" ", "") for _ in range(width)] for _ in range(height)]

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
        color_style = "#A3BE8C" if is_bullish else "#BF616A"  # Nord green / red
        body_char = "█" if is_bullish else "▒"

        # Draw shadows (wicks)
        wick_start = min(r_high, r_low)
        wick_end = max(r_high, r_low)
        for r in range(wick_start, wick_end + 1):
            canvas[r][col] = ("│", color_style)

        # Draw real body
        body_start = min(r_open, r_close)
        body_end = max(r_open, r_close)
        for r in range(body_start, body_end + 1):
            canvas[r][col] = (body_char, color_style)

    # Render lines as rich.text.Text with native styles
    for r in range(height):
        y_val = val_max - (r / (height - 1)) * val_range if height > 1 else val_max
        label = f"Rp {y_val:,.0f}"
        
        result.append(f"{label:>12} │ ", style="dim")
        
        for col in range(width):
            char, style = canvas[r][col]
            if style:
                result.append(char, style=style)
            else:
                result.append(char)
                
        result.append("\n")
        
    # Add timeline border bottom
    result.append(" " * 13 + "└" + "─" * width, style="dim")
    result.append("\n")
    
    return result
