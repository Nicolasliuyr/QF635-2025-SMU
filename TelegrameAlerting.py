import asyncio
import aiohttp
from io import BytesIO
import matplotlib.pyplot as plt
import pandas as pd

class TelegramBot:
    def __init__(self):
        self.bot_token = '7712527710:AAHmq8TAyB475TQdkllO2s3hLZipeONvN0E'
        self.chat_id = '6772300878'
        self.last_update_id = None
        self.stop_critical = asyncio.Event()
        self.last_normal = {'text': None, 'chart': None, 'table': None}

    async def send_text_message(self, text):
        if text:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data={'chat_id': self.chat_id, 'text': text}) as resp:
                    print("✅ Text sent" if resp.status == 200 else f"❌ Error: {await resp.text()}")

    async def send_photo(self, image_bytesio):
        if image_bytesio:
            image_bytesio.seek(0)
            buffer_copy = BytesIO(image_bytesio.read())
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            data = aiohttp.FormData()
            data.add_field('chat_id', self.chat_id)
            data.add_field('photo', buffer_copy, filename='chart.jpg', content_type='image/jpeg')
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    print("✅ Chart sent" if resp.status == 200 else f"❌ Error: {await resp.text()}")

    async def send_file(self, df):
        if isinstance(df, pd.DataFrame):
            buffer = BytesIO()
            df.to_csv(buffer, index=False)
            buffer.seek(0)
            url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
            data = aiohttp.FormData()
            data.add_field('chat_id', self.chat_id)
            data.add_field('document', buffer, filename='table.csv', content_type='text/csv')
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    print("✅ Table sent" if resp.status == 200 else f"❌ Error: {await resp.text()}")

    async def send_text_message_with_button(self, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'reply_markup': '{"inline_keyboard": [[{"text": "Acknowledge", "callback_data": "ack"}]]}'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                print("✅ Button message sent" if resp.status == 200 else f"❌ Error: {await resp.text()}")

    async def clear_pending_updates(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    updates = data.get("result", [])
                    if updates:
                        self.last_update_id = updates[-1]['update_id']
                        print(f"🔁 Cleared {len(updates)} old updates. Starting from update_id={self.last_update_id}")
                else:
                    print(f"❌ Failed to clear updates: {await resp.text()}")

    async def check_for_acknowledgement(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {}
        if self.last_update_id is not None:
            params['offset'] = self.last_update_id + 1

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for update in data.get("result", []):
                        self.last_update_id = update['update_id']
                        if 'callback_query' in update and update['callback_query']['data'] == 'ack':
                            await self.send_text_message("✅ Critical alert acknowledged.")
                            self.stop_critical.set()
                elif resp.status == 404:
                    print("ℹ️ No updates yet — 404 returned. Retrying...")
                else:
                    print(f"❌ Unexpected error: {await resp.text()}")

    async def send_critical_alert(self, text=None, chart=None, table=None):
        await self.clear_pending_updates()

        async def poll():
            while not self.stop_critical.is_set():
                await self.check_for_acknowledgement()
                await asyncio.sleep(2)

        async def repeat():
            while not self.stop_critical.is_set():
                await self.send_text_message_with_button(f"🚨 CRITICAL: {text}")
                await self.send_normal_alert(**self.last_normal)
                await asyncio.sleep(5)

        self.last_normal = {'text': text, 'chart': chart, 'table': table}
        await self.send_normal_alert(text, chart, table)

        await asyncio.gather(poll(), repeat())

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
        chart = bot.create_scatter_plot()
        table = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})

        # Normal message
        # await bot.send_normal_alert(text="📊 Market Update", chart=chart, table=table)

        # Critical alert
        await bot.send_critical_alert(text="🚨 Alert!", chart=chart, table=table)

    asyncio.run(main())
