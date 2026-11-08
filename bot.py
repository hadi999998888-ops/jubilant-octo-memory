import asyncio
import logging
import sqlite3
import re
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter
)

# =============== НАСТРОЙКИ ===============

TOKEN = "9015705095:AAE64m-zwxXcBYr-zz7b0dOlcMW6YBJ3mQI"
ADMIN_ID = 7608889836

LOOP = "@LoopHack"
LOOP_URL = "https://t.me/LoopHack"
ANGEL = "@smertnuy_angelok"
ANGEL_URL = "https://t.me/smertnuy_angelok"

DB = "loop_hack.sqlite3"

EMOJI = {
    "chat": "5906476035192396092",
    "phone": "5906991701850856372",
    "check": "5906840875484321836",
    "wait": "5906598824012420908",
    "announce": "5906797358875681525",
    "rose": "5287348867317125082",
    "folder": "5906839307821259375"
}

logging.basicConfig(level=logging.INFO)

bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())


def em(name, fallback):
    return f'<tg-emoji emoji-id="{EMOJI[name]}">{fallback}</tg-emoji>'


# =============== БАЗА ДАННЫХ ===============

def database():
    return sqlite3.connect(DB)


def init_db():
    with database() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS channels(
            channel TEXT PRIMARY KEY,
            url TEXT,
            title TEXT
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            message_id INTEGER,
            description TEXT
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS support(
            admin_message INTEGER PRIMARY KEY,
            user_id INTEGER
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS pending(
            user_id INTEGER PRIMARY KEY,
            post_id INTEGER
        )
        """)

        con.execute(
            "INSERT OR IGNORE INTO channels VALUES(?,?,?)",
            (LOOP, LOOP_URL, "LOOP HACK")
        )

        con.execute(
            "INSERT OR IGNORE INTO channels VALUES(?,?,?)",
            (ANGEL, ANGEL_URL, "ANGEL KFG")
        )


def save_user(user_id):
    with database() as con:
        con.execute(
            "INSERT OR IGNORE INTO users VALUES(?)",
            (user_id,)
        )


def channels():
    with database() as con:
        return con.execute(
            "SELECT channel,url,title FROM channels"
        ).fetchall()


# =============== КЛАВИАТУРЫ ===============

def subscription_keyboard():
    rows = []

    for channel, url, title in channels():
        rows.append([
            InlineKeyboardButton(
                text=f"📢 {title}",
                url=url
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="✅ Проверить",
            callback_data="check"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📞 Менеджер",
                callback_data="manager"
            )
        ],
        [
            InlineKeyboardButton(
                text="📢 LOOP HACK",
                url=LOOP_URL
            )
        ]
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🌹 РАССЫЛКА",
                callback_data="broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                text="🌹 СОЗДАТЬ ПОСТ",
                callback_data="create_post"
            )
        ],
        [
            InlineKeyboardButton(
                text="🌹 ДОБАВИТЬ ПОДПИСКИ",
                callback_data="subscriptions"
            )
        ]
    ])


# =============== СОСТОЯНИЯ ===============

class AdminStates(StatesGroup):
    material = State()
    description = State()
    broadcast = State()
    add_channel = State()
    add_url = State()


class UserStates(StatesGroup):
    manager = State()


# =============== ПОДПИСКИ ===============

async def check_membership(user_id):
    missing = []

    for channel, url, title in channels():
        try:
            member = await bot.get_chat_member(
                channel, user_id
            )

            if member.status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR
            ):
                missing.append(title)

        except Exception:
            missing.append(title)

    return missing


async def subscription_screen(message):
    await message.answer(
        f'{em("chat","💬")} <b>Подпишись на нужные каналы</b>',
        reply_markup=subscription_keyboard()
    )


async def send_menu(message):
    await message.answer(
        f'{em("chat","💬")} <b>Добро пожаловать в главное меню</b>\n'
        f'{em("rose","🌹")} <b>LOOP HACK</b>\n\n'
        f'{em("folder","📁")} Получай нужные файлы.\n'
        'Перейди в наш канал, там будут все софты.',
        reply_markup=main_keyboard()
    )


# =============== ВЫДАЧА ПОСТОВ ===============

async def deliver_post(user_id, post_id):
    with database() as con:
        post = con.execute(
            "SELECT chat_id,message_id,description "
            "FROM posts WHERE id=?",
            (post_id,)
        ).fetchone()

    if not post:
        await bot.send_message(user_id, "Материал не найден.")
        return

    chat_id, message_id, description = post

    try:
        await bot.copy_message(
            user_id,
            chat_id,
            message_id
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 LOOP HACK",
                    url=LOOP_URL
                )
            ]
        ])

        await bot.send_message(
            user_id,
            f'{em("folder","📁")} <b>Описание материала</b>\n'
            f'{escape(description)}',
            reply_markup=keyboard
        )

    except TelegramForbiddenError:
        pass


# =============== START ===============

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    user_id = message.from_user.id
    save_user(user_id)

    payload = message.text.split(maxsplit=1)
    post_id = None

    if len(payload) > 1:
        arg = payload[1]

        if arg.startswith("p") and arg[1:].isdigit():
            post_id = int(arg[1:])

            with database() as con:
                con.execute(
                    "INSERT OR REPLACE INTO pending VALUES(?,?)",
                    (user_id, post_id)
                )

    missing = await check_membership(user_id)

    if missing:
        await subscription_screen(message)
        return

    if post_id:
        await deliver_post(user_id, post_id)

        with database() as con:
            con.execute(
                "DELETE FROM pending WHERE user_id=?",
                (user_id,)
            )
    else:
        await send_menu(message)

    if user_id == ADMIN_ID:
        await message.answer(
            "Админ-панель: /admin"
        )


@dp.callback_query(F.data == "check")
async def check_button(callback: CallbackQuery):
    missing = await check_membership(
        callback.from_user.id
    )

    if missing:
        await callback.answer(
            "Сначала подпишись на все каналы!",
            show_alert=True
        )
        return

    with database() as con:
        row = con.execute(
            "SELECT post_id FROM pending WHERE user_id=?",
            (callback.from_user.id,)
        ).fetchone()

        con.execute(
            "DELETE FROM pending WHERE user_id=?",
            (callback.from_user.id,)
        )

    await callback.answer("Подписка подтверждена!")

    await callback.message.delete()

    if row:
        await deliver_post(
            callback.from_user.id,
            row[0]
        )
    else:
        await send_menu(callback.message)


# =============== АДМИНКА ===============

@dp.message(Command("admin"))
async def admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    await state.clear()

    await message.answer(
        f'{em("chat","💬")} <b>Добро пожаловать в админку</b>\n'
        'Выбери, что ты хочешь:',
        reply_markup=admin_keyboard()
    )


# =============== СОЗДАНИЕ ПОСТА ===============

@dp.callback_query(F.data == "create_post")
async def create_post(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminStates.material)

    await callback.message.answer(
        f'{em("rose","🌹")} Пришли материал любого формата.'
    )

    await callback.answer()


@dp.message(AdminStates.material, F.from_user.id == ADMIN_ID)
async def get_material(message: Message, state: FSMContext):
    await state.update_data(
        chat_id=message.chat.id,
        message_id=message.message_id
    )

    await state.set_state(AdminStates.description)

    await message.answer("Пришли описание материала.")


@dp.message(AdminStates.description, F.from_user.id == ADMIN_ID)
async def get_description(message: Message, state: FSMContext):
    description = message.text or message.caption

    if not description:
        await message.answer("Пришли текстовое описание.")
        return

    data = await state.get_data()

    with database() as con:
        cursor = con.execute(
            "INSERT INTO posts(chat_id,message_id,description) "
            "VALUES(?,?,?)",
            (
                data["chat_id"],
                data["message_id"],
                description
            )
        )

        post_id = cursor.lastrowid

    await state.clear()

    await message.answer(
        f'{em("wait","⏳")} Создаю ссылку...'
    )

    await asyncio.sleep(1)

    me = await bot.get_me()

    link = f"https://t.me/{me.username}?start=p{post_id}"

    await message.answer(
        f'{em("wait","⏳")} <b>Готово!</b>\n\n'
        f'<code>{link}</code>'
    )


# =============== РАССЫЛКА ===============

@dp.callback_query(F.data == "broadcast")
async def broadcast_start(
    callback: CallbackQuery,
    state: FSMContext
):
    if callback.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminStates.broadcast)

    await callback.message.answer(
        "Пришли материал для рассылки."
    )

    await callback.answer()


@dp.message(AdminStates.broadcast, F.from_user.id == ADMIN_ID)
async def broadcast(message: Message, state: FSMContext):
    await state.clear()

    with database() as con:
        users = [
            row[0] for row in
            con.execute("SELECT id FROM users").fetchall()
        ]

    await message.answer(
        f'{em("wait","⏳")} Начинаю рассылку: {len(users)} пользователей.'
    )

    sent = 0
    failed = 0

    for user_id in users:
        try:
            await bot.copy_message(
                user_id,
                message.chat.id,
                message.message_id
            )
            sent += 1
            await asyncio.sleep(0.06)

        except TelegramRetryAfter as error:
            await asyncio.sleep(error.retry_after + 1)

            try:
                await bot.copy_message(
                    user_id,
                    message.chat.id,
                    message.message_id
                )
                sent += 1
            except Exception:
                failed += 1

        except Exception:
            failed += 1

    await message.answer(
        f"Рассылка завершена.\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}"
    )


# =============== ПОДПИСКИ ===============

@dp.callback_query(F.data == "subscriptions")
async def subscriptions(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Добавить канал",
                callback_data="add_channel"
            )
        ],
        [
            InlineKeyboardButton(
                text="➖ Удалить канал",
                callback_data="remove_channel"
            )
        ]
    ])

    await callback.message.answer(
        "Управление подписками:",
        reply_markup=keyboard
    )

    await callback.answer()


@dp.callback_query(F.data == "add_channel")
async def add_channel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminStates.add_channel)

    await callback.message.answer(
        "Пришли @username канала или ID канала."
    )

    await callback.answer()


@dp.message(AdminStates.add_channel, F.from_user.id == ADMIN_ID)
async def get_channel(message: Message, state: FSMContext):
    channel = (message.text or "").strip()

    if not (
        channel.startswith("@")
        or re.fullmatch(r"-100\d+", channel)
    ):
        await message.answer("Неверный ID канала.")
        return

    await state.update_data(channel=channel)

    await state.set_state(AdminStates.add_url)

    await message.answer(
        "Пришли ссылку на канал."
    )


@dp.message(AdminStates.add_url, F.from_user.id == ADMIN_ID)
async def get_channel_url(message: Message, state: FSMContext):
    url = (message.text or "").strip()

    if not url.startswith("https://t.me/"):
        await message.answer("Неверная ссылка.")
        return

    data = await state.get_data()

    try:
        chat = await bot.get_chat(data["channel"])
        me = await bot.get_me()

        member = await bot.get_chat_member(
            chat.id,
            me.id
        )

        if member.status not in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ):
            await message.answer(
                "Сначала сделай бота администратором канала."
            )
            await state.clear()
            return

        with database() as con:
            con.execute(
                "INSERT OR REPLACE INTO channels VALUES(?,?,?)",
                (str(chat.id), url, chat.title or data["channel"])
            )

        await message.answer("Канал успешно добавлен.")

    except Exception as error:
        await message.answer(
            f"Ошибка добавления канала: {escape(str(error)[:300])}"
        )

    await state.clear()


@dp.callback_query(F.data == "remove_channel")
async def remove_channel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    rows = []

    for channel, url, title in channels():
        if channel == LOOP:
            continue

        rows.append([
            InlineKeyboardButton(
                text=f"❌ {title}",
                callback_data=f"remove:{channel}"
            )
        ])

    await callback.message.answer(
        "Выбери канал для удаления:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=rows
        )
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("remove:"))
async def remove_channel_confirm(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    channel = callback.data.split(":", 1)[1]

    if channel == LOOP:
        await callback.answer(
            "LOOP HACK удалить нельзя.",
            show_alert=True
        )
        return

    with database() as con:
        con.execute(
            "DELETE FROM channels WHERE channel=?",
            (channel,)
        )

    await callback.answer("Канал удалён.")


# =============== МЕНЕДЖЕР ===============

@dp.callback_query(F.data == "manager")
async def manager(callback: CallbackQuery, state: FSMContext):
    missing = await check_membership(
        callback.from_user.id
    )

    if missing:
        await callback.answer(
            "Сначала подпишись на каналы.",
            show_alert=True
        )
        return

    await state.set_state(UserStates.manager)

    await callback.message.answer(
        "Напиши свой вопрос менеджеру одним сообщением."
    )

    await callback.answer()


@dp.message(UserStates.manager)
async def manager_message(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        return

    try:
        copied = await bot.copy_message(
            ADMIN_ID,
            message.chat.id,
            message.message_id
        )

        with database() as con:
            con.execute(
                "INSERT OR REPLACE INTO support VALUES(?,?)",
                (
                    copied.message_id,
                    message.from_user.id
                )
            )

        await message.answer(
            "Вопрос отправлен менеджеру. Ожидай ответа."
        )

    except Exception:
        await message.answer(
            "Не удалось отправить сообщение."
        )

    await state.clear()


# =============== ОТВЕТ АДМИНА ===============

@dp.message(F.from_user.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(message: Message):
    with database() as con:
        row = con.execute(
            "SELECT user_id FROM support WHERE admin_message=?",
            (message.reply_to_message.message_id,)
        ).fetchone()

    if not row:
        return

    try:
        await bot.copy_message(
            row[0],
            message.chat.id,
            message.message_id
        )

        await message.reply("Ответ отправлен.")

    except Exception:
        await message.reply("Не удалось отправить ответ.")


# =============== ЗАПУСК ===============

async def main():
    init_db()

    print("LOOP HACK BOT STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
