import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.gridspec as gridspec
import asyncio
import MainFile
import pandas as pd

running = False
loop = None

status_labels = {}
open_orders_tree = None


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

        label_y_offset = 0
        label_spacing = 25  # pixels between labels

        for label, color in [
            (row.get("SignalTrade"), "black"),
            (row.get("AfterCare"), "purple"),
            (row.get("RiskTrigger"), "red")
        ]:
            if pd.notna(label):
                ax1.text(
                    mdates.date2num(time),
                    y_base_bottom - label_y_offset,
                    label,
                    ha='center',
                    va='top',
                    fontsize=8,
                    color=color
                )
                label_y_offset += label_spacing

        '''if pd.notna(row['SignalTrade']):
            ax1.text(mdates.date2num(time), y_base_bottom, row['SignalTrade'], ha='center', va='top', fontsize=8, color='black')
        if pd.notna(row['AfterCare']):
            ax1.text(mdates.date2num(time), y_base_bottom - 10, row['AfterCare'], ha='center', va='top', fontsize=8, color='purple')
        if pd.notna(row['RiskTrigger']):
            ax1.text(mdates.date2num(time), y_base_bottom - 20, row['RiskTrigger'], ha='center', va='top', fontsize=8, color='red')'''

    ax2.bar(df['open_time'], df['volume'], width=candle_width, color='gray')


def update_chart():

    # Get the full DataFrame from storage
    df = MainFile.storage.get_latest_candles()

    # ✅ Only keep the last 60 rows for plotting
    df = df.tail(60)

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

    for key in status_labels:
        val = MainFile.status.get(key, 0)
        status_labels[key].config(text=f"{key}: {val:.3f}")

    update_open_orders()
    root.after(1000, update_chart)


def update_open_orders():
    global open_orders_tree
    for row in open_orders_tree.get_children():
        open_orders_tree.delete(row)

    orders = MainFile.status.get("openOrders", [])
    for order in orders:
        condition = ""
        if order.get("type") == "STOP_MARKET":
            side = order.get("side")
            stop_price = order.get("stopPrice") or order.get("price")
            if side == "BUY":
                condition = f">= {stop_price}"
            elif side == "SELL":
                condition = f"<= {stop_price}"

        open_orders_tree.insert("", tk.END, values=(
            order.get("orderId"), order.get("symbol"), order.get("side"),
            order.get("type"), order.get("price"),
            order.get("origQty"), order.get("executedQty"),
            order.get("status"), condition
        ))



def start_trading():
    global running, loop
    if running:
        print("⚠️ Trading system is already running.")
        return

    print("✅ Starting trading system...")
    running = True
    loop = asyncio.new_event_loop()
    Thread(target=lambda: loop.run_until_complete(MainFile.main()), daemon=True).start()

def confirm_square_off():
    if messagebox.askyesno("Confirm Square-Off", "Are you sure you want to square off all positions?"):
        print("✅ User confirmed square-off.")
        MainFile.confirm_and_trigger_square_off()
    else:
        print("❎ Square-off cancelled by user.")


def stop_trading():
    global running, loop
    print("🛑 Stopping trading system")
    running = False

    async def shutdown():
        try:
            await MainFile.save_all_to_csv_temp()
            print("✅ All data saved.")
        except Exception as e:
            print(f"❌ Error saving data: {e}")
        root.quit()

    asyncio.run_coroutine_threadsafe(shutdown(), loop)


root = tk.Tk()
root.title("Trading System Launcher")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

frame_chart = tk.Frame(notebook)
frame_orders = tk.Frame(notebook)
frame_test = tk.Frame(notebook)
notebook.add(frame_chart, text="Chart")
notebook.add(frame_orders, text="Open Orders")
notebook.add(frame_test, text="Test Alerts")

frame_top = tk.Frame(frame_chart)
frame_top.pack(side=tk.TOP, fill=tk.X)

btn_start = tk.Button(frame_top, text="Start Trading", command=start_trading, bg="green", fg="white")
btn_start.pack(side=tk.LEFT, padx=10)
btn_square_off = tk.Button(frame_top, text="EMERGENCY SQUARE-OFF", command=confirm_square_off, bg="orange", fg="black")
btn_square_off.pack(side=tk.LEFT, padx=10)
btn_stop = tk.Button(frame_top, text="Stop Trading", command=stop_trading, bg="red", fg="white")
btn_stop.pack(side=tk.LEFT, padx=10)

def send_warning_alert():
    asyncio.run_coroutine_threadsafe(MainFile.send_test_warning_alert(), loop)

def send_critical_alert():
    asyncio.run_coroutine_threadsafe(MainFile.send_test_critical_alert(), loop)

btn_warning = tk.Button(frame_test, text="Send Warning Alert", command=send_warning_alert, bg="yellow")
btn_warning.pack(pady=20, padx=10)
btn_critical = tk.Button(frame_test, text="Send Critical Alert", command=send_critical_alert, bg="red", fg="white")
btn_critical.pack(pady=10, padx=10)

frame_status = tk.Frame(frame_chart)
frame_status.pack(side=tk.TOP, fill=tk.X)
for key in ["position", "totalMarginBalance", "availableBalance", "var_value", "unrealisedPnL", "realisedPnL"]:
    lbl = tk.Label(frame_status, text=f"{key}: 0.000", font=("Arial", 10))
    lbl.pack(side=tk.LEFT, padx=10)
    status_labels[key] = lbl

#fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

fig = plt.figure(figsize=(10, 6))
gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])  # 3:1 ratio
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1], sharex=ax1)

canvas = FigureCanvasTkAgg(fig, master=frame_chart)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

columns = ["orderId", "symbol", "side", "type", "price", "origQty", "executedQty", "status", "condition"]
open_orders_tree = ttk.Treeview(frame_orders, columns=columns, show='headings', height=20)
column_widths = {
    "orderId": 100,
    "symbol": 80,
    "side": 60,
    "type": 90,
    "price": 80,
    "origQty": 80,
    "executedQty": 90,
    "status": 90,
    "condition": 100
}
for col in columns:
    open_orders_tree.heading(col, text=col)
    open_orders_tree.column(col, anchor='center', width=column_widths.get(col, 80))

open_orders_tree.pack(fill="both", expand=True)

root.after(1000, update_chart)
root.mainloop()
