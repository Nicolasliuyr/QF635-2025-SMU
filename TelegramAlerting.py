import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from io import BytesIO
import matplotlib.pyplot as plt
import pandas as pd


class TelegramBot:
    def __init__(self, env_path: str = '.env'):

        load_dotenv(env_path)
        self.bot_token = os.getenv("Telegram_bot_token")
        self.chat_id = os.getenv("Telegram_chat_id")
        print('???????????????????')
        print(self.bot_token)
        print(self.chat_id)
        self.last_update_id = None
        self.session = None
        self.stop_critical = asyncio.Event()
        self.last_normal = {'text': None, 'chart': None, 'table': None}

    async def start(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def send_text_message(self, text):
        if not text:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with self.session.post(url, data={'chat_id': self.chat_id, 'text': text}) as resp:
            print("✅ Text sent" if resp.status == 200 else f"❌ Text error: {await resp.text()}")

    async def send_photo(self, image_bytesio):
        if not image_bytesio:
            return
        image_bytesio.seek(0)
        buffer_copy = BytesIO(image_bytesio.read())
        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        data = aiohttp.FormData()
        data.add_field('chat_id', self.chat_id)
        data.add_field('photo', buffer_copy, filename='chart.jpg', content_type='image/jpeg')
        async with self.session.post(url, data=data) as resp:
            print("✅ Chart sent" if resp.status == 200 else f"❌ Chart error: {await resp.text()}")

    async def send_file(self, df):
        if not isinstance(df, pd.DataFrame):
            return
        buffer = BytesIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        data = aiohttp.FormData()
        data.add_field('chat_id', self.chat_id)
        data.add_field('document', buffer, filename='table.csv', content_type='text/csv')
        async with self.session.post(url, data=data) as resp:
            print("✅ Table sent" if resp.status == 200 else f"❌ Table error: {await resp.text()}")

    async def send_text_message_with_button(self, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'reply_markup': '{"inline_keyboard": [[{"text": "Acknowledge", "callback_data": "ack"}]]}'
        }
        async with self.session.post(url, data=payload) as resp:
            print("✅ Button sent" if resp.status == 200 else f"❌ Button error: {await resp.text()}")

    async def clear_pending_updates(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        async with self.session.get(url) as resp:
            if resp.status == 200:
                updates = (await resp.json()).get("result", [])
                if updates:
                    self.last_update_id = updates[-1]['update_id']
                    print(f"🔁 Cleared {len(updates)} old updates.")
            else:
                print(f"❌ Failed to clear updates: {await resp.text()}")

    async def check_for_acknowledgement(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {}
        if self.last_update_id is not None:
            params['offset'] = self.last_update_id + 1
        async with self.session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                for update in data.get("result", []):
                    self.last_update_id = update['update_id']
                    if 'callback_query' in update and update['callback_query']['data'] == 'ack':
                        await self.send_text_message("✅ Critical alert acknowledged.")
                        self.stop_critical.set()
            else:
                print(f"❌ Update check failed: {await resp.text()}")

    async def _poll_ack_loop(self):
        while not self.stop_critical.is_set():
            await self.check_for_acknowledgement()
            await asyncio.sleep(2)

    async def _repeat_critical_loop(self, text):
        while not self.stop_critical.is_set():
            await self.send_text_message_with_button(f"🚨 CRITICAL: {text}")
            await self.send_normal_alert(**self.last_normal)
            await asyncio.sleep(5)

    async def send_critical_alert(self, text=None, chart=None, table=None):
        self.stop_critical.clear()
        await self.clear_pending_updates()
        self.last_normal = {'text': text, 'chart': chart, 'table': table}
        await self.send_normal_alert(**self.last_normal)
        asyncio.create_task(self._poll_ack_loop())
        asyncio.create_task(self._repeat_critical_loop(text))

    async def send_normal_alert(self, text=None, chart=None, table=None):
        self.last_normal = {'text': text, 'chart': chart, 'table': table}
        await self.send_text_message(text)
        await self.send_photo(chart)
        await self.send_file(table)

    def create_scatter_plot(self):
        x, y = [1, 2, 3, 4, 5], [2, 1, 4, 3, 5]
        plt.figure(figsize=(6, 4))
        plt.scatter(x, y, color='blue', label='Data points')
        plt.title('Scatter Plot Example')
        plt.xlabel('X Axis')
        plt.ylabel('Y Axis')
        plt.legend()
        plt.tight_layout()
        buffer = BytesIO()
        plt.savefig(buffer, format='jpeg')
        plt.close()
        buffer.seek(0)
        return buffer


# === Example Usage ===
if __name__ == "__main__":
    async def main():
        bot = TelegramBot()
        await bot.start()

        chart = bot.create_scatter_plot()
        table = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})

        # Send normal alert
        await bot.send_normal_alert("📊 Market Update", chart, table)

        # Fire critical alert (background, non-blocking)
        # await bot.send_critical_alert("🚨 Alert!", chart, table)

        # Main task continues without blocking
        for i in range(30):
            print(f"Main task running... {i}")
            await asyncio.sleep(1)

        await bot.close()

    asyncio.run(main())
