import tkinter as tk
from tkinter import ttk
from threading import Thread
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import asyncio
import MainFile
import pandas as pd

# Global flag
running = True

def draw_candle(ax1, ax2, df):
    if df.empty:
        return

    candle_width = 0.0005
    for idx, row in df.iterrows():
        time = row['open_time']
        o, h, l, c = row['open'], row['high'], row['low'], row['close']
        color = 'green' if c >= o else 'red'

        ax1.plot([time, time], [l, h], color=color, linewidth=1)
        rect = patches.Rectangle((mdates.date2num(time) - candle_width / 2, min(o, c)),
                                 candle_width, abs(c - o), color=color)
        ax1.add_patch(rect)

        y_base_top = h + 20
        y_base_bottom = l - 20
        if pd.notna(row['Signal']):
            ax1.text(mdates.date2num(time), y_base_top, row['Signal'], ha='center', va='bottom', fontsize=8, color='blue')
        if pd.notna(row['SignalTrade']):
            ax1.text(mdates.date2num(time), y_base_bottom, row['SignalTrade'], ha='center', va='top', fontsize=8, color='black')
        if pd.notna(row['AfterCare']):
            ax1.text(mdates.date2num(time), y_base_bottom - 10, row['AfterCare'], ha='center', va='top', fontsize=8, color='purple')
        if pd.notna(row['RiskTrigger']):
            ax1.text(mdates.date2num(time), y_base_bottom - 20, row['RiskTrigger'], ha='center', va='top', fontsize=8, color='red')

    ax2.bar(df['open_time'], df['volume'], width=candle_width, color='gray')

def update_chart(canvas, ax1, ax2, fig, labels):
    if not running:
        return

    df = MainFile.storage.get_latest_candles()
    if df.empty:
        root.after(1000, update_chart, canvas, ax1, ax2, fig, labels)
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
    draw_candle(ax1, ax2, df)
    fig.subplots_adjust(top=0.92, bottom=0.2)
    canvas.draw()

    if MainFile.riskMgr is not None:
        labels['realised'].config(text=f"Realised PnL: {MainFile.riskMgr.realised_pnl_today:.2f}")
        labels['unrealised'].config(text=f"Unrealised PnL: {MainFile.riskMgr.unrealised_pnl_closing:.2f}")
        labels['var_pct'].config(text=f"VaR %: {MainFile.riskMgr.latest_var_pct:.2%}")
        labels['var_value'].config(text=f"VaR Value: {MainFile.riskMgr.latest_var_value:.2f}")

    root.after(1000, update_chart, canvas, ax1, ax2, fig, labels)

def update_open_orders(tree):
    try:
        if hasattr(MainFile, "collector") and MainFile.collector is not None:
            orders = MainFile.collector.open_orders
            tree.delete(*tree.get_children())

            if not orders:
                root.after(2000, update_open_orders, tree)
                return

            for order in orders:
                order_type = order.get("type", "")
                side = order.get("side", "")
                stop_price = float(order.get("stopPrice", 0)) if "stopPrice" in order else 0

                # Format condition field
                if order_type == "STOP_MARKET":
                    if side == "BUY":
                        condition = f"Last Price ≥ {stop_price:,.2f}"
                    elif side == "SELL":
                        condition = f"Last Price ≤ {stop_price:,.2f}"
                    else:
                        condition = f"{stop_price:,.2f}"
                else:
                    condition = "-"

                row = [
                    order.get("orderId", ""),
                    order.get("symbol", ""),
                    side,
                    order_type,
                    condition,
                    order.get("status", ""),
                    order.get("price", ""),
                    order.get("origQty", ""),
                    order.get("executedQty", "")
                ]

                tree.insert('', 'end', values=row)

    except Exception as e:
        print(f"⚠️ Error updating open orders: {e}")
    finally:
        # Schedule the next update
        root.after(2000, update_open_orders, tree)

def start_trading():
    global running
    print("✅ Starting trading system...")
    running = True
    Thread(target=lambda: asyncio.run(MainFile.main()), daemon=True).start()

def stop_trading():
    global running
    print("🛑 Stopping trading system.")
    running = False
    root.destroy()

root = tk.Tk()
root.title("Trading System Launcher")
root.geometry("1200x800")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

# === Tab 1: Candlestick Chart ===
tab1 = tk.Frame(notebook)
notebook.add(tab1, text="📈 Candlestick & PnL")

fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(12, 6),
                               gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
canvas = FigureCanvasTkAgg(fig, master=tab1)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

metrics_frame = tk.Frame(tab1)
metrics_frame.pack(pady=5)

labels = {
    'realised': tk.Label(metrics_frame, text="Realised PnL: 0.00", font=("Arial", 10), fg="black"),
    'unrealised': tk.Label(metrics_frame, text="Unrealised PnL: 0.00", font=("Arial", 10), fg="black"),
    'var_pct': tk.Label(metrics_frame, text="VaR %: 0.00%", font=("Arial", 10), fg="black"),
    'var_value': tk.Label(metrics_frame, text="VaR Value: 0.00", font=("Arial", 10), fg="black"),
}
for lbl in labels.values():
    lbl.pack(side=tk.LEFT, padx=10)

btn_frame = tk.Frame(tab1)
btn_frame.pack(side=tk.BOTTOM, pady=10)

tk.Button(btn_frame, text="Y (Start)", bg="green", fg="white", width=20, height=2, command=start_trading).pack(side=tk.LEFT, padx=10)
tk.Button(btn_frame, text="N (Exit)", bg="red", fg="white", width=20, height=2, command=stop_trading).pack(side=tk.RIGHT, padx=10)

# === Tab 2: Open Orders ===
tab2 = tk.Frame(notebook)
notebook.add(tab2, text="📋 Open Orders")

columns = [
    "orderId", "symbol", "side", "type", "condition",
    "status", "price", "origQty", "executedQty"
]
tree = ttk.Treeview(tab2, columns=columns, show='headings')

for col in columns:
    tree.heading(col, text=col)
    tree.column(col, anchor='center', width=120)

tree.pack(fill=tk.BOTH, expand=True)

# Schedule updates
root.after(1000, update_chart, canvas, ax1, ax2, fig, labels)
root.after(2000, update_open_orders, tree)

root.mainloop()
