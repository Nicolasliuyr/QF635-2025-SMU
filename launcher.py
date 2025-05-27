import tkinter as tk
from threading import Thread
import MainFile  # Make sure MainFile.py defines `async def main()`

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