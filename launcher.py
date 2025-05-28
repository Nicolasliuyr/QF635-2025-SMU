import tkinter as tk
from threading import Thread
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import asyncio
from MainFile import main, storage

# Global flag
running = True

def draw_candle(ax1, ax2, c, show_signal=True, show_fill=True):
    time = c['open_time']
    o, h, l, cl = c['open'], c['high'], c['low'], c['close']
    volume = c['volume']
    signal = c.get('signal')
    fill = c.get('fill_status')
    color = 'green' if cl >= o else 'red'
    candle_width = 0.0005  # ~43.2 seconds

    # Wick
    ax1.plot([time, time], [l, h], color=color, linewidth=1)

    # Body
    rect = patches.Rectangle(
        (mdates.date2num(time) - candle_width / 2, min(o, cl)),
        candle_width, abs(cl - o),
        color=color
    )
    ax1.add_patch(rect)

    # Signal text (BUY/SELL) on finalized candles only
    if show_signal and signal and signal != "HOLD":
        ax1.text(mdates.date2num(time), h + 10, signal, ha='center', va='bottom', fontsize=9, color='blue')

    # Fill status (F or PF)
    if show_fill and fill:
        ax1.text(mdates.date2num(time), l - 10, fill, ha='center', va='top', fontsize=9, color='black')

    # Volume bar
    ax2.bar(time, volume, width=candle_width, color='gray')

def update_chart(canvas, ax1, ax2, fig):
    if not running:
        return

    candles = storage.get_latest_candles(minutes=60)
    if not candles:
        root.after(1000, update_chart, canvas, ax1, ax2, fig)
        return

    ax1.clear()
    ax2.clear()

    ax1.set_title("Candlestick Chart (Past 60 Minutes)")
    ax1.set_ylabel("Price")
    ax2.set_ylabel("Volume")
    ax2.set_xlabel("Time (HH:MM)")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    # Separate finalized and developing candle
    finalized = candles[:-1]
    developing = candles[-1:]

    for c in finalized:
        draw_candle(ax1, ax2, c, show_signal=True, show_fill=True)

    for c in developing:
        draw_candle(ax1, ax2, c, show_signal=False, show_fill=False)

    fig.subplots_adjust(top=0.92, bottom=0.15)
    canvas.draw()

    root.after(1000, update_chart, canvas, ax1, ax2, fig)

def start_trading():
    global running
    print("✅ Starting trading system...")
    running = True
    Thread(target=lambda: asyncio.run(main()), daemon=True).start()

def stop_trading():
    global running
    print("🛑 Stopping trading system.")
    running = False
    root.destroy()

# GUI setup
root = tk.Tk()
root.title("Trading System Launcher")
root.geometry("1000x700")

# Create Matplotlib figure with 2 subplots (candlestick + volume)
fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(12, 6),
                               gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
canvas = FigureCanvasTkAgg(fig, master=root)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Control buttons
btn_frame = tk.Frame(root)
btn_frame.pack(side=tk.BOTTOM, pady=10)

tk.Button(btn_frame, text="Y (Start)", bg="green", fg="white", width=20, height=2, command=start_trading).pack(side=tk.LEFT, padx=10)
tk.Button(btn_frame, text="N (Exit)", bg="red", fg="white", width=20, height=2, command=stop_trading).pack(side=tk.RIGHT, padx=10)

# Start the chart update loop
root.after(1000, update_chart, canvas, ax1, ax2, fig)

# Start GUI
root.mainloop()

'''
import tkinter as tk
from threading import Thread
import MainFile  # Make sure MainFile.py defines `async def main()`
from MainFile import storage

def start_trading():
    print("✅ Starting trading system...")
    Thread(target=lambda: __import__('asyncio').run(MainFile.main()), daemon=True).start()

def stop_trading():
    print("🛑 Exiting without starting.")
    root.destroy()

# GUI setup
root = tk.Tk()
root.title("Start Trading System")
root.geometry("300x150")

tk.Label(root, text="Start Trading System?").pack(pady=10)

tk.Button(root, text="Y (Start)", bg="green", fg="white", width=20, height=2, command=start_trading).pack(pady=5)
tk.Button(root, text="N (Exit)", bg="red", fg="white", width=20, height=2, command=stop_trading).pack(pady=5)

root.mainloop()

'''