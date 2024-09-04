import asyncio
import logging
import sys
from functions import *
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

# Bot token can be obtained via https://t.me/BotFather
TOKEN = "6848992174:AAETmVftK3cj-gpUM12hcVcr-u8o5cTOWb0"
# All handlers should be attached to the Router (or Dispatcher)
dp = Dispatcher()
CHATID = 6777957380


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    pprint(message)
    try:
        if message.text == "/ip":
            ip = await get_IP()
            await message.answer(ip)
            #print(ip)
        elif message.text == "/flag":
            flagstat = await get_flag_status()
            await message.answer(flagstat)
            #print(
from bs4 import BeautifulSoupflagstat)
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    # Most event objects have aliases for API methods that can be called in events' context
    # For example if you want to answer to incoming message you can use `message.answer(...)` alias
    # and the target chat will be passed to :ref:`aiogram.methods.send_message.SendMessage`
    # method automatically or call API method directly via
    # Bot instance: `bot.send_message(chat_id=message.chat.id, ...)`
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


async def job_function(ibot, chatid):
    print("INSIDE")
    ip = await get_IP()
    await ibot.send_message(chat_id=chatid, text=ip)
    flagstat = await get_flag_status()
    await ibot.send_message(chat_id=chatid, text=flagstat)


async def thread_function(ibot, chatid):
    await ibot.send_message(chat_id=chatid, text="Inside the Thread that was started, Starting work.")
    isched = AsyncIOScheduler()
    # Schedule job_function to be called every 1 second
    # FIXME: Do not forget to change end_date to actual date
    isched.add_job(job_function, 'interval', seconds=5, args=(ibot, chatid))
    isched.start()


async def main(mbot) -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    await mbot.send_message(chat_id=CHATID, text="Thread started, moving on.")

    # And the run events dispatching
    await dp.start_polling(mbot)


async def coroutine():
    return await asyncio.sleep(10, "Coroutine")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot2 = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    #x = threading.Thread(target=asyncio.run, args=(thread_function(bot2, CHATID),))
    #x.start()
    #loop = asyncio.new_event_loop()
    #asyncio.set_event_loop(loop)
    #loop.run_until_complete(main(bot))
    #asyncio.run(main(bot))

    loop = asyncio.get_event_loop()

    coro = coroutine()  # Getting the coroutine object

    future = asyncio.run_coroutine_threadsafe(coro, loop)  # returns a `concurrent.futures.Future` instance
    result = future.result()
    print(result)
