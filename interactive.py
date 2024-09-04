import asyncio
import logging
import sys
from functions import *
from pprint import pprint

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message

# Bot token can be obtained via https://t.me/BotFather


# All handlers should be attached to the Router (or Dispatcher)
dp = Dispatcher()


@dp.message()
async def echo_handler(message: Message) -> None:
    pprint(message)
    try:
        if message.text == "/ip":
            ip = await get_IP()
            await message.answer(ip)
            # print(ip)
        elif message.text == "/flag":
            flagstat = await get_flag_status()
            await message.answer(flagstat)
            # print(flagstat)
        elif message.text == "/hosts":
            flagstat = await get_host_statuses()
            await message.answer(flagstat)
            # print(flagstat)
        elif message.text == "/services":
            flagstat = await get_service_statuses()
            await message.answer(flagstat)
            # print(flagstat)
        else:
            await message.answer("Nice try!")
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.send_message(chat_id=CHATID, text="Started Interactive Service.")
    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
