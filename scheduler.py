import asyncio
import logging
import sys
from functions import *
from pprint import pprint

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message

TOKEN = "6848992174:AAETmVftK3cj-gpUM12hcVcr-u8o5cTOWb0"
CHATID = 6777957380


async def main():
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.send_message(chat_id=CHATID, text="Started Scheduled Service.")
    while True:
        # Schedule three calls *concurrently*:
        results = await asyncio.gather(
            get_IP(),
            get_flag_status(),
        )
        pprint(results)
        for result in results:
            await bot.send_message(chat_id=CHATID, text=result)
        await asyncio.sleep(21600)

if __name__ == "__main__":
    asyncio.run(main())
