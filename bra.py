import os
import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
import json

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold, hcode

import config
from tinydb import TinyDB, Query

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

db = TinyDB('base.json')
User = Query()
Withdrawal = Query()
AdminCommand = Query()
Settings = Query()
Promo = Query()
Check = Query()

users_table = db.table('users')
withdrawals_table = db.table('withdrawals')
admin_commands_table = db.table('admin_commands')
settings_table = db.table('settings')
promo_table = db.table('promo_codes')
checks_table = db.table('checks')

BOT_USERNAME = "starsy_zarabotoxk_bot"
STICKER_ID = "CAACAgQAAxkBAAEO2wpoaGWT-UagSPkJjKk3FQNJYX1g_gAC2BYAAhQKOVOm2YJ5-sTESDYE"
FLYER_API_KEY = "FL-zszzsM-yyGIiR-ElICUF-ZpuEcO"
FLYER_API_URL = "https://api.flyerservice.io"

if not settings_table.all():
    settings_table.insert({
        'min_referrals': 5,
        'min_tasks': 3,
        'referral_reward': 1
    })

# States
class AdminStates(StatesGroup):
    # каналы
    add_channel_id = State()
    add_channel_link = State()
    delete_channel = State()
    
    # задания
    add_task_channel_id = State()
    add_task_link = State()
    add_task_reward = State()
    delete_task = State()
    
    # настройки 
    set_min_refs = State()
    set_min_tasks = State()
    set_ref_reward = State()
    
    # промо
    add_promo_code = State()
    add_promo_reward = State()
    add_promo_limit = State()
    delete_promo = State()
    
    # пользователи
    freeze_user = State()
    unfreeze_user = State()
    reset_user = State()
    
    # чеки
    add_check_amount = State()
    add_check_limit = State()
    delete_check = State()


def generate_check_code():
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"CHK-{timestamp}-{random_part}"

async def check_subscription(user_id: int) -> bool:
    """Проверка подписки через Flyer API"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "key": FLYER_API_KEY,
                "user_id": user_id,
                "language_code": "ru",
                "message": {
                    "text": "📢 Для доступа к боту необходимо подписаться на наши каналы",
                    "button_bot": "✅ Я подписался",
                    "button_channel": "🔗 Подписаться",
                    "button_boost": "⚡ Буст",
                    "button_url": "🌐 Сайт",
                    "button_fp": "🎁 Подарок"
                }
            }
            
            async with session.post(f"{FLYER_API_URL}/check", json=payload) as response:
                result = await response.json()
                print(f"Flyer API response: {result}")  # Debug
                # Flyer API возвращает skip=True если подписка выполнена
                return result.get('skip', False)
    except Exception as e:
        print(f"Error in check_subscription: {e}")
        # В случае ошибки разрешаем доступ, чтобы не блокировать пользователей
        return True

async def show_subscription_message(chat_id: int, user_id: int):
    """Показ сообщения о подписке через Flyer"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "key": FLYER_API_KEY,
                "user_id": user_id,
                "language_code": "ru",
                "message": {
                    "text": "📢 Для доступа к боту необходимо подписаться на наши каналы",
                    "button_bot": "✅ Я подписался",
                    "button_channel": "🔗 Подписаться",
                    "button_boost": "⚡ Буст",
                    "button_url": "🌐 Сайт",
                    "button_fp": "🎁 Подарок"
                }
            }
            
            async with session.post(f"{FLYER_API_URL}/check", json=payload) as response:
                result = await response.json()
                print(f"Flyer subscription check: {result}")  # Debug
                
                # Если есть информация о каналах, показываем кнопки
                if result.get('channels'):
                    builder = InlineKeyboardBuilder()
                    for channel in result['channels']:
                        builder.button(text="🔗 Подписаться", url=channel.get('url', '#'))
                    builder.button(text="✅ Я подписался", callback_data="check_subscription")
                    builder.adjust(1)
                    
                    await bot.send_message(
                        chat_id,
                        "📢 Для доступа к боту необходимо подписаться на наши каналы:\n\nПосле подписки нажмите кнопку ниже 👇",
                        reply_markup=builder.as_markup()
                    )
                else:
                    # Стандартное сообщение если нет информации о каналах
                    builder = InlineKeyboardBuilder()
                    builder.button(text="✅ Я подписался", callback_data="check_subscription")
                    builder.adjust(1)
                    
                    await bot.send_message(
                        chat_id,
                        "📢 Для доступа к боту необходимо подписаться на наши каналы.\n\nПосле подписки нажмите кнопку ниже 👇",
                        reply_markup=builder.as_markup()
                    )
                    
    except Exception as e:
        print(f"Error in show_subscription_message: {e}")
        # Fallback сообщение
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Я подписался", callback_data="check_subscription")
        builder.adjust(1)
        
        await bot.send_message(
            chat_id,
            "📢 Для доступа к боту необходимо подписаться на наши каналы.\n\nПосле подписки нажмите кнопку ниже 👇",
            reply_markup=builder.as_markup()
        )

async def get_user_tasks(user_id: int, limit: int = 5) -> List[Dict]:
    """Получение заданий для пользователя через Flyer API"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "key": FLYER_API_KEY,
                "user_id": user_id,
                "language_code": "ru",
                "limit": limit
            }
            
            async with session.post(f"{FLYER_API_URL}/get_tasks", json=payload) as response:
                result = await response.json()
                print(f"Flyer tasks response: {result}")  # Debug
                return result.get('result', [])
    except Exception as e:
        print(f"Error in get_user_tasks: {e}")
        return []

async def check_task_status(signature: str) -> str:
    """Проверка статуса задания через Flyer API"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "key": FLYER_API_KEY,
                "signature": signature
            }
            
            async with session.post(f"{FLYER_API_URL}/check_task", json=payload) as response:
                result = await response.json()
                print(f"Flyer task status: {result}")  # Debug
                return result.get('result', 'null')
    except Exception as e:
        print(f"Error in check_task_status: {e}")
        return 'null'

async def get_completed_tasks_count(user_id: int) -> int:
    """Получение количества выполненных заданий через Flyer API"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "key": FLYER_API_KEY,
                "user_id": user_id
            }
            
            async with session.post(f"{FLYER_API_URL}/get_completed_tasks", json=payload) as response:
                result = await response.json()
                print(f"Flyer completed tasks: {result}")  # Debug
                if result.get('result'):
                    return result['result'].get('count_all_tasks', 0)
                return 0
    except Exception as e:
        print(f"Error in get_completed_tasks_count: {e}")
        return 0

def main_menu_markup() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💫 Заработать звезды", callback_data="referral")
    builder.button(text="👤 Мой профиль", callback_data="profile")
    builder.button(text="💰 Вывод", callback_data="withdraw")
    builder.button(text="🎯 Задания", callback_data="tasks_1")
    builder.button(text="🎁 Промокод", callback_data="promo")
    builder.button(text="🎰 Слоты", callback_data="slots")
    builder.button(text="📌 Инструкция", callback_data="instruction")
    builder.button(text="🏆 Топ лидеров", callback_data="top_day")
    builder.adjust(1, 2, 2, 1, 1)
    return builder.as_markup()

async def show_main_menu(chat_id: int):
    try:
        await bot.send_message(
            chat_id,
            "🌟 <b>Главное меню</b> 🌟\n\nВыберите раздел:",
            reply_markup=main_menu_markup(),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        print(f"Error in show_main_menu: {e}")

@dp.message(Command("start"))
async def send_welcome(message: Message):
    global BOT_USERNAME
    if not BOT_USERNAME:
        me = await bot.get_me()
        BOT_USERNAME = me.username
    
    user_id = message.from_user.id
    try:
        await bot.send_sticker(message.chat.id, STICKER_ID)
        
        # Проверяем подписку
        is_subscribed = await check_subscription(user_id)
        print(f"User {user_id} subscribed: {is_subscribed}")  # Debug
        
        if not is_subscribed:
            await show_subscription_message(message.chat.id, user_id)
            return
        
        args = message.text.split()
        if len(args) > 1:
            arg = args[1]
            
            # Check if it's a check code
            check = checks_table.search(Check.code == arg)
            if check:
                check = check[0]
                if user_id in check.get('used_by', []):
                    await message.answer("⚠️ Вы уже активировали этот чек!")
                    await show_main_menu(message.chat.id)
                    return
                
                if len(check.get('used_by', [])) >= check['limit']:
                    await message.answer("⚠️ Лимит активаций этого чека исчерпан!")
                    await show_main_menu(message.chat.id)
                    return
                
                user_data = users_table.search(User.user_id == user_id)
                if not user_data:
                    users_table.insert({
                        'user_id': user_id,
                        'balance': 0,
                        'first_name': message.from_user.first_name,
                        'last_name': message.from_user.last_name if message.from_user.last_name else '',
                        'referrer_id': None,
                        'registration_date': datetime.now().isoformat(),
                        'referrals': [],
                        'username': message.from_user.username or "NoUsername",
                        'frozen': False,
                        'used_promo_codes': [],
                        'pending_referrer': None
                    })
                    user_data = users_table.search(User.user_id == user_id)
                
                if user_data[0].get('frozen', False):
                    await message.answer("❄️ Ваш аккаунт заморожен! Активация невозможна.")
                    await show_main_menu(message.chat.id)
                    return
                
                new_balance = user_data[0]['balance'] + check['amount']
                used_by = check.get('used_by', [])
                used_by.append(user_id)
                
                users_table.update({'balance': new_balance}, User.user_id == user_id)
                checks_table.update({'used_by': used_by}, Check.code == arg)
                
                await message.answer(
                    f"🎉 Чек успешно активирован!\n\n"
                    f"+{check['amount']} звезд ⭐️\n"
                    f"💫 Ваш баланс: {new_balance} звезд"
                )
                
                await show_main_menu(message.chat.id)
                return
            
            # Existing referral code handling
            referrer_id = arg
            
            if not users_table.search(User.user_id == user_id):
                users_table.insert({
                    'user_id': user_id,
                    'balance': 0,
                    'first_name': message.from_user.first_name,
                    'last_name': message.from_user.last_name if message.from_user.last_name else '',
                    'referrer_id': None,
                    'pending_referrer': int(referrer_id) if referrer_id and referrer_id != str(user_id) else None,
                    'registration_date': datetime.now().isoformat(),
                    'referrals': [],
                    'username': message.from_user.username or "NoUsername",
                    'frozen': False,
                    'used_promo_codes': []
                })
                await message.answer(
                    "👋 Добро пожаловать!\n\n"
                    "Чтобы реферал был засчитан, вам нужно:\n"
                    "1. Подписаться на все каналы\n"
                    "2. Выполнить хотя бы одно задание\n\n"
                    "После этого ваш пригласитель получит награду!"
                )

        if not users_table.search(User.user_id == user_id):
            users_table.insert({
                'user_id': user_id,
                'balance': 0,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name if message.from_user.last_name else '',
                'referrer_id': None,
                'pending_referrer': None,
                'registration_date': datetime.now().isoformat(),
                'referrals': [],
                'username': message.from_user.username or "NoUsername",
                'frozen': False,
                'used_promo_codes': []
            })

        await show_main_menu(message.chat.id)
    except Exception as e:
        print(f"Error in send_welcome: {e}")

# ... (остальной код остается без изменений, как в предыдущем варианте)

# --- начало скрипта без изменений (твоя логика flyer API, users, referrals и т.д.) ---

# ⬇️ новый блок админки вместо старого

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    user_id = message.from_user.id
    if user_id != config.ADMIN_ID:
        return
    
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📊 Статистика", "admin_stats"),
        ("📈 Статистика заданий", "admin_task_stats_1"),
        ("👥 Пользователи", "admin_users_1"),
        ("➕ Добавить задание", "admin_add"),
        ("➖ Удалить задание", "admin_delete"),
        ("📢 Добавить канал", "admin_add_channel"),
        ("🗑 Удалить канал", "admin_delete_channel"),
        ("🎫 Создать промокод", "admin_add_promo"),
        ("❌ Удалить промокод", "admin_delete_promo"),
        ("👥 Мин. рефералов", "admin_set_min_refs"),
        ("🎯 Мин. заданий", "admin_set_min_tasks"),
        ("⭐ Награда за реферала", "admin_set_ref_reward"),
        ("❄️ Заморозить", "admin_freeze"),
        ("🔥 Разморозить", "admin_unfreeze"),
        ("🔄 Обнулить", "admin_reset"),
        ("🧾 Создать чек", "admin_add_check"),
        ("🗑 Удалить чек", "admin_delete_check")
    ]
    
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    
    builder.adjust(2, 2, 2, 2, 2, 2, 2, 2, 1)
    
    await message.answer(
        "🔧 <b>Админ-панель</b> 🔧",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


@dp.message(F.text)
async def handle_text_messages(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # если админ — проверяем состояние
    if user_id == config.ADMIN_ID:
        current_state = await state.get_state()
        if current_state:
            await handle_admin_input(message, state)
            return
    
    # обработка промокодов / чеков
    await handle_promo_input(message)


async def handle_admin_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    try:
        if current_state == AdminStates.add_channel_id.state:
            await state.update_data(channel_id=message.text)
            await state.set_state(AdminStates.add_check_amount)
            builder = InlineKeyboardBuilder()
            builder.button(text="🚫 Отмена", callback_data="admin_cancel")
            await message.answer("📢 Введите ссылку на канал (например: https://t.me/channel):", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.add_channel_link.state:
            data = await state.get_data()
            channels_table.insert({
                'channel_id': data['channel_id'],
                'link': message.text
            })
            await message.answer("✅ Канал успешно добавлен в обязательные подписки!")
            await state.clear()
        
        elif current_state == AdminStates.delete_channel.state:
            try:
                channel_num = int(message.text) - 1
                all_channels = channels_table.all()
                if 0 <= channel_num < len(all_channels):
                    channels_table.remove(doc_ids=[all_channels[channel_num].doc_id])
                    await message.answer("✅ Канал успешно удален!")
                else:
                    await message.answer("❌ Ошибка! Некорректный номер канала.")
                await state.clear()
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.add_check_amount.state:
            try:
                amount = int(message.text)
                if amount <= 0:
                    raise ValueError
                await state.update_data(amount=amount)
                await state.set_state(AdminStates.add_check_limit)
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer(
                    "📌 Введите лимит активаций для этого чека:",
                    reply_markup=builder.as_markup()
                )
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())

        elif current_state == AdminStates.add_check_limit.state:
            try:
                limit = int(message.text)
                if limit <= 0:
                    raise ValueError
                data = await state.get_data()
                code = generate_check_code()
                checks_table.insert({
                    'code': code,
                    'amount': data['amount'],
                    'limit': limit,
                    'used_by': []
                })
                check_link = f"https://t.me/{BOT_USERNAME}?start={code}"

                builder = InlineKeyboardBuilder()
                builder.button(text="⭐ Получить", url=check_link)

                await message.answer(
                    f"Чек на {data['amount']} ⭐\n\n"
                    f"Внутри чека: {limit} активаций по {data['amount']} ⭐",
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
                await state.clear()
                await state.clear()
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())


        elif current_state == AdminStates.add_task_channel_id.state:
            await state.update_data(channel_id=message.text)
            await state.set_state(AdminStates.add_task_link)
            builder = InlineKeyboardBuilder()
            builder.button(text="🚫 Отмена", callback_data="admin_cancel")
            await message.answer("🔗 Введите ссылку на канал для задания:", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.add_task_link.state:
            await state.update_data(link=message.text)
            await state.set_state(AdminStates.add_task_reward)
            builder = InlineKeyboardBuilder()
            builder.button(text="🚫 Отмена", callback_data="admin_cancel")
            await message.answer("⭐ Введите количество звезд за выполнение задания:", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.add_task_reward.state:
            try:
                reward = int(message.text)
                if reward <= 0:
                    raise ValueError
                data = await state.get_data()
                tasks_table.insert({
                    'channel_id': data['channel_id'],
                    'link': data['link'],
                    'reward': reward
                })
                await message.answer("✅ Задание успешно добавлено!")
                await state.clear()
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.delete_task.state:
            try:
                task_num = int(message.text) - 1
                all_tasks = tasks_table.all()
                if 0 <= task_num < len(all_tasks):
                    tasks_table.remove(doc_ids=[all_tasks[task_num].doc_id])
                    await message.answer("✅ Задание успешно удалено!")
                else:
                    await message.answer("❌ Ошибка! Некорректный номер задания.")
                await state.clear()
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.set_min_refs.state:
            try:
                new_min_refs = int(message.text)
                if new_min_refs < 0:
                    raise ValueError
                settings_table.update({'min_referrals': new_min_refs}, Settings.min_referrals.exists())
                await message.answer(f"✅ Минимальное количество рефералов изменено на: {new_min_refs}")
                await state.clear()
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.set_min_tasks.state:
            try:
                new_min_tasks = int(message.text)
                if new_min_tasks < 0:
                    raise ValueError
                settings_table.update({'min_tasks': new_min_tasks}, Settings.min_tasks.exists())
                await message.answer(f"✅ Минимальное количество заданий изменено на: {new_min_tasks}")
                await state.clear()
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.set_ref_reward.state:
            try:
                reward = int(message.text)
                if reward < 0:
                    raise ValueError
                settings_table.update({'referral_reward': reward}, Settings.referral_reward.exists())
                await message.answer(f"✅ Награда за реферала изменена на: {reward} ⭐️")
                await state.clear()
            except ValueError:
                builder = InlineKeyboardBuilder()
                builder.button(text="🚫 Отмена", callback_data="admin_cancel")
                await message.answer("⚠️ Ошибка! Введите корректное число.", reply_markup=builder.as_markup())
        
        elif current_state == AdminStates.add_promo_code.state:
            await state.update_data(code=message.text)
            await state.set_state(AdminStates.add_promo_reward)
            builder = InlineKeyboardBuilder()
            builder.button(text="🚫 Отмена", callback_data="admin_cancel")
            await message.answer("⭐ Введите количество звезд за активацию промокода:", reply_markup=builder.as_markup())
    
    except Exception as e:
        print(f"Error in handle_admin_input: {e}")
        await message.answer("⚠️ Ошибка обработки ввода администратора.")

# --- дальше твой код без изменений ---


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Проверяем подписку еще раз
    is_subscribed = await check_subscription(user_id)
    print(f"Subscription check callback for {user_id}: {is_subscribed}")  # Debug
    
    if is_subscribed:
        user_data = users_table.search(User.user_id == user_id)
        if not user_data:
            users_table.insert({
                'user_id': user_id,
                'balance': 0,
                'first_name': callback.from_user.first_name,
                'last_name': callback.from_user.last_name if callback.from_user.last_name else '',
                'referrer_id': None,
                'pending_referrer': None,
                'registration_date': datetime.now().isoformat(),
                'referrals': [],
                'username': callback.from_user.username or "NoUsername",
                'frozen': False,
                'used_promo_codes': []
            })
        
        await callback.message.edit_text(
            "🌟 <b>Главное меню</b> 🌟\n\nВыберите раздел:",
            reply_markup=main_menu_markup(),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.answer("⚠️ Вы не подписаны на все каналы! Пожалуйста, подпишитесь и нажмите снова.", show_alert=True)
        # Показываем сообщение о подписке снова
        await show_subscription_message(callback.message.chat.id, user_id)

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="cancel")
    
    reg_date = datetime.fromisoformat(user_data['registration_date']).strftime("%d.%m.%Y")
    referrals_count = len(user_data.get('referrals', []))
    tasks_count = await get_completed_tasks_count(user_id)
    withdrawals_count = len([w for w in withdrawals_table.search(Withdrawal.user_id == user_id) if w['status'] == '✅ Выполнено'])
    
    profile_text = (
        "👤 <b>Мой профиль</b> 👤\n\n"
        f"🆔 ID: {hcode(user_id)}\n"
        f"📅 Регистрация: {reg_date}\n\n"
        f"💫 Баланс: {user_data['balance']} ⭐️\n"
        f"🎯 Заданий: {tasks_count}\n"
        f"👥 Рефералов: {referrals_count}\n\n"
        "📊 <b>Статистика</b>\n"
        f"💰 Выводов: {withdrawals_count}"
    )
    
    await callback.message.edit_text(
        text=profile_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "referral")
async def referral_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    settings = settings_table.all()[0]
    referral_reward = settings.get('referral_reward', 1)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="cancel")
    
    referrals_count = len(user_data.get('referrals', []))
    total_earned = referrals_count * referral_reward
    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    referral_text = (
        "💎 <b>Реферальная программа</b> 💎\n\n"
        f"🔗 Приводи друзей и получай {referral_reward} ⭐️ за каждого!\n\n"
        "👇 <b>Ваша реферальная ссылка:</b>\n"
        f"{hcode(referral_link)}\n\n"
        "🏆 <b>Ваша статистика:</b>\n"
        f"├ Приглашено: {referrals_count}\n"
        f"└ Заработано: {total_earned} ⭐️"
    )
    
    await callback.message.edit_text(
        text=referral_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("tasks_"))
async def tasks_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    
    if user_data.get('frozen', False):
        await callback.message.edit_text("❄️ Ваш аккаунт заморожен! Задания недоступны.")
        return
    
    tasks = await get_user_tasks(user_id, limit=10)
    
    if not tasks:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="cancel")
        await callback.message.edit_text(
            "🎯 <b>Доступных заданий нет</b>\n\nПроверяйте позже, задания обновляются регулярно!",
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Сохраняем задачи в состоянии пользователя для последующей проверки
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    
    storage = MemoryStorage()
    state = FSMContext(storage, callback.from_user.id, callback.from_user.id)
    await state.update_data(current_tasks=tasks)
    
    task = tasks[0]
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✅ Выполнить задание", url=task.get('url', '#'))
    builder.button(text="🔍 Проверить выполнение", callback_data=f"check_task_{task['signature']}")
    builder.button(text="🔙 Назад", callback_data="cancel")
    builder.adjust(1, 1, 1)
    
    task_text = (
        "🎯 <b>Новое задание</b>\n\n"
        f"📝 {task.get('title', 'Задание')}\n"
        f"💫 Награда: {task.get('reward', 0)} ⭐️\n\n"
        f"📋 Описание:\n{task.get('description', 'Нет описания')}"
    )
    
    await callback.message.edit_text(
        text=task_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("check_task_"))
async def check_task_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    signature = callback.data.split("_", 2)[2]
    
    if user_data.get('frozen', False):
        await callback.message.edit_text("❄️ Ваш аккаунт заморожен! Проверка заданий невозможна.")
        return
    
    status = await check_task_status(signature)
    
    if status == 'complete':
        # Задание выполнено, начисляем награду
        tasks = await get_user_tasks(user_id, limit=10)
        current_task = next((t for t in tasks if t['signature'] == signature), None)
        
        if current_task:
            reward = current_task.get('reward', 0)
            new_balance = user_data['balance'] + reward
            
            # Проверяем, есть ли pending_referrer и это первое выполненное задание
            tasks_count = await get_completed_tasks_count(user_id)
            pending_referrer = user_data.get('pending_referrer')
            if pending_referrer and tasks_count == 0:
                referrer = users_table.search(User.user_id == pending_referrer)
                if referrer and not referrer[0].get('frozen', False):
                    settings = settings_table.all()[0]
                    ref_reward = settings.get('referral_reward', 1)
                    referrer_balance = referrer[0]['balance'] + ref_reward
                    referrer_data = referrer[0]
                    referrer_data['referrals'] = referrer_data.get('referrals', []) + [user_id]
                    users_table.update(
                        {
                            'balance': referrer_balance, 
                            'referrals': referrer_data['referrals']
                        }, 
                        User.user_id == pending_referrer
                    )
                    await bot.send_message(
                        pending_referrer, 
                        f"✨ Новый подтвержденный реферал! +{ref_reward} звезд ⭐️\n\n"
                        f"💫 Твой баланс: {referrer_balance} звезд",
                        parse_mode=ParseMode.HTML
                    )
                # Обновляем referrer_id пользователя
                users_table.update(
                    {
                        'referrer_id': pending_referrer,
                        'pending_referrer': None
                    },
                    User.user_id == user_id
                )
            
            users_table.update({'balance': new_balance}, User.user_id == user_id)
            
            await callback.message.answer(
                f"🎉 Задание выполнено!\n\n"
                f"+{reward} звезд ⭐️\n"
                f"💫 Новый баланс: {new_balance} звезд"
            )
            
            # Показываем следующее задание
            await tasks_callback(callback)
        else:
            await callback.message.edit_text("❌ Ошибка при получении информации о задании.")
    
    elif status == 'incomplete':
        await callback.message.edit_text("⚠️ Задание еще не выполнено! Пожалуйста, завершите задание и попробуйте снова.")
    
    elif status == 'waiting':
        await callback.message.edit_text("⏳ Задание выполнено! Ожидайте выплаты в течение 24 часов.")
    
    elif status == 'abort':
        await callback.message.edit_text("❌ Вы отписались от канала! Пожалуйста, подпишитесь снова.")
    
    elif status == 'unavailable':
        await callback.message.edit_text("❌ Задание больше недоступно.")
    
    else:
        await callback.message.edit_text("❌ Ошибка при проверке задания. Попробуйте позже.")

@dp.callback_query(F.data == "promo")
async def promo_callback(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="cancel")
    await callback.message.edit_text(
        "🎁 <b>Активация промокода</b>\n\nВведите промокод для получения бонуса:",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    settings = settings_table.all()[0]
    min_referrals = settings.get('min_referrals', 5)
    min_tasks = settings.get('min_tasks', 3)
    
    referrals_count = len(user_data.get('referrals', []))
    tasks_count = await get_completed_tasks_count(user_id)
    
    builder = InlineKeyboardBuilder()
    buttons = [
        ("15 ⭐️", "withdraw_15"),
        ("25 ⭐️", "withdraw_25"),
        ("50 ⭐️", "withdraw_50"),
        ("100 ⭐️", "withdraw_100"),
        ("150 ⭐️", "withdraw_150"),
        ("350 ⭐️", "withdraw_350"),
        ("500 ⭐️", "withdraw_500")
    ]
    
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    
    builder.button(text="🔙 Назад", callback_data="cancel")
    builder.adjust(2, 2, 2, 1)
    
    withdraw_text = (
        f"💰 <b>Вывод звезд</b> 💰\n\n"
        f"💫 Ваш баланс: {user_data['balance']} ⭐️\n\n"
        f"📌 Требования:\n"
        f"├ {min_referrals} рефералов (у вас: {referrals_count})\n"
        f"└ {min_tasks} заданий (у вас: {tasks_count})\n\n"
        f"👇 Выберите сумму для вывода:"
    )
    
    await callback.message.edit_text(
        text=withdraw_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("withdraw_"))
async def withdraw_amount_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    settings = settings_table.all()[0]
    min_referrals = settings.get('min_referrals', 5)
    min_tasks = settings.get('min_tasks', 3)
    
    try:
        stars = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        return
    
    referrals_count = len(user_data.get('referrals', []))
    tasks_count = await get_completed_tasks_count(user_id)
    
    if user_data.get('frozen', False):
        await callback.message.edit_text("❄️ Ваш аккаунт заморожен! Вывод невозможен.")
        return
    
    if user_data['balance'] < stars:
        await callback.message.edit_text(
            f"⚠️ Недостаточно звезд!\n\n💫 Ваш баланс: {user_data['balance']} ⭐️"
        )
        return
    
    if referrals_count < min_referrals or tasks_count < min_tasks:
        await callback.message.edit_text(
            f"⚠️ Не выполнены требования!\n\n"
            f"📌 Нужно: {min_referrals} рефералов и {min_tasks} заданий\n"
            f"💫 У вас: {referrals_count} рефералов и {tasks_count} заданий"
        )
        return
    
    withdrawal_id = len(withdrawals_table.all()) + 1
    withdrawals_table.insert({
        'id': withdrawal_id,
        'user_id': user_id,
        'stars': stars,
        'status': '⏳ Ожидание',
        'username': user_data['username'],
        'timestamp': datetime.now().isoformat()
    })
    
    new_balance = user_data['balance'] - stars
    users_table.update({'balance': new_balance}, User.user_id == user_id)
    
    await callback.message.edit_text(
        f"📌 Заявка №{withdrawal_id} на {stars} звезд создана!\n\n"
        "Ожидайте обработки администратором."
    )
    
    public_text = (
        f"📌 Заявка №{withdrawal_id}\n"
        f"👤 @{user_data['username']} | ID: {user_id}\n"
        f"💫 Сумма: {stars} звезд\n"
        f"📊 Статус: ⏳ Ожидание"
    )
    public_msg = await bot.send_message(config.PUBLIC_CHANNEL_ID, public_text)
    
    admin_text = (
        f"📌 Заявка №{withdrawal_id}\n"
        f"👤 @{user_data['username']} | ID: {user_id}\n"
        f"💫 Сумма: {stars} звезд\n"
        f"📊 Статус: ⏳ Ожидание"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Подтвердить", 
        callback_data=f"withdraw_sent_{withdrawal_id}_{public_msg.message_id}"
    )
    builder.button(
        text="❌ Отклонить", 
        callback_data=f"withdraw_denied_{withdrawal_id}_{public_msg.message_id}"
    )
    
    admin_msg = await bot.send_message(
        config.ADMIN_CHANNEL_ID,
        admin_text,
        reply_markup=builder.as_markup()
    )
    
    withdrawals_table.update(
        {'admin_msg_id': admin_msg.message_id},
        Withdrawal.id == withdrawal_id
    )

@dp.callback_query(F.data.startswith("withdraw_sent_") | F.data.startswith("withdraw_denied_"))
async def withdraw_action_callback(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    parts = callback.data.split("_")
    action = parts[1]
    withdrawal_id = int(parts[2])
    public_msg_id = int(parts[3])
    
    withdrawal = withdrawals_table.search(Withdrawal.id == withdrawal_id)[0]
    status = "✅ Выполнено" if action == "sent" else "❌ Отклонено"
    
    withdrawals_table.update({'status': status}, Withdrawal.id == withdrawal_id)
    user_id = withdrawal['user_id']
    stars = withdrawal['stars']
    
    public_text = (
        f"📌 Заявка №{withdrawal_id}\n"
        f"👤 @{withdrawal['username']} | ID: {user_id}\n"
        f"💫 Сумма: {stars} звезд\n"
        f"📊 Статус: {status}"
    )
    
    await bot.edit_message_text(
        chat_id=config.PUBLIC_CHANNEL_ID,
        message_id=public_msg_id,
        text=public_text
    )
    
    admin_text = (
        f"📌 Заявка №{withdrawal_id}\n"
        f"👤 @{withdrawal['username']} | ID: {user_id}\n"
        f"💫 Сумма: {stars} звезд\n"
        f"📊 Статус: {status}"
    )
    
    await callback.message.edit_text(text=admin_text)
    
    if action == "sent":
        await bot.send_message(
            user_id,
            f"🎉 Заявка №{withdrawal_id} выполнена!\n\n"
            f"{stars} звезд отправлены на ваш счет."
        )
    else:
        await bot.send_message(
            user_id,
            f"⚠️ Заявка №{withdrawal_id} отклонена."
        )
        user = users_table.search(User.user_id == user_id)[0]
        if not user.get('frozen', False):
            new_balance = user['balance'] + stars
            users_table.update({'balance': new_balance}, User.user_id == user_id)

@dp.callback_query(F.data == "slots")
async def slots_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    
    if user_data.get('frozen', False):
        await callback.message.edit_text("❄️ Ваш аккаунт заморожен! Игра невозможна.")
        return
    
    builder = InlineKeyboardBuilder()
    buttons = [
        ("5 ⭐️", "slots_bet_5"),
        ("10 ⭐️", "slots_bet_10"),
        ("25 ⭐️", "slots_bet_25"),
        ("50 ⭐️", "slots_bet_50"),
        ("100 ⭐️", "slots_bet_100"),
        ("200 ⭐️", "slots_bet_200"),
        ("500 ⭐️", "slots_bet_500")
    ]
    
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    
    builder.button(text="🔙 Назад", callback_data="cancel")
    builder.adjust(2, 2, 2, 1)
    
    slots_text = (
        "🎰 <b>Крути рулетку и удвой свой баланс!</b>\n\n"
        f"📊 Онлайн статистика выигрышей: t.me\n\n"
        f"💰 Баланс: {user_data['balance']} ⭐️\n"
        "⬇️ Выбери ставку:"
    )
    
    await callback.message.edit_text(
        text=slots_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("slots_bet_"))
async def slots_bet_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = users_table.search(User.user_id == user_id)
    if not user_data:
        return
    
    user_data = user_data[0]
    
    try:
        bet = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        return
    
    if user_data.get('frozen', False):
        await callback.message.edit_text("❄️ Ваш аккаунт заморожен! Игра невозможна.")
        return
    
    if user_data['balance'] < bet:
        await callback.message.edit_text(
            f"⚠️ Недостаточно звезд!\n\n💫 Ваш баланс: {user_data['balance']} ⭐️"
        )
        return
    
    # 50% chance to win
    if random.random() < 0.5:
        win_amount = bet * 2
        new_balance = user_data['balance'] + win_amount - bet
        users_table.update({'balance': new_balance}, User.user_id == user_id)
        
        result_text = (
            f"🎉 Поздравляем! Вы выиграли {win_amount} ⭐️\n\n"
            f"💫 Ваш баланс: {new_balance} звезд"
        )
    else:
        new_balance = user_data['balance'] - bet
        users_table.update({'balance': new_balance}, User.user_id == user_id)
        
        result_text = (
            f"😢 К сожалению, вы проиграли {bet} ⭐️\n\n"
            f"💫 Ваш баланс: {new_balance} звезд"
        )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🎰 Крутить еще раз", callback_data="slots")
    builder.button(text="🔙 Назад", callback_data="cancel")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text=result_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "instruction")
async def instruction_callback(callback: CallbackQuery):
    instruction_text = (
        "📌 <b>Как набрать много переходов по ссылке?</b>\n\n"
        "• Отправь её друзьям в личные сообщения 🧍‍♂️🧍‍♀️\n"
        "• Поделись ссылкой в истории и в своем ТГ или в Telegram-канале 📣\n"
        "• Оставь её в комментариях или чатах 🗨️\n"
        "• Распространяй ссылку в соцсетях: TikTok, Instagram, WhatsApp и других 🌍\n\n"
        "🤩 <b>Способы, которыми можно заработать до 1000 звёзд в день:</b>\n\n"
        "1️⃣ <b>Первый способ:</b>\n"
        "1. Заходим в TikTok или Лайк\n"
        "2. Ищем видео по запросам: звёзды телеграм, подарки телеграм, тг старсы и т.п.\n"
        "3. Оставляем в комментариях текст типа:\n"
        "Дарю подарки/звезды, пишите в тг @вашюзер\n"
        "4. Отправляете свою личную ссылку тем, кто пишет\n"
        "5. Ждём и выводим звезды 💰\n\n"
        "2️⃣ <b>Второй способ:</b>\n"
        "1. Заходим в бот знакомств @leomatchbot\n"
        "2. Делаем анкету женского пола\n"
        "3. Лайкаем всех подряд и параллельно ждём пока нас пролайкают 💞\n"
        "4. Переходим со всеми в ЛС и пишем:\n"
        "Привет, помоги мне пожалуйста заработать звёзды. Перейди и активируй бота по моей ссылке: «твоя ссылка»\n"
        "5. Ждём и выводим звёзды 🌟"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="cancel")
    
    await callback.message.edit_text(
        text=instruction_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("top_"))
async def top_callback(callback: CallbackQuery):
    period = callback.data.split("_")[1]
    now = datetime.now()
    
    if period == "day":
        time_delta = timedelta(days=1)
        title = "🏆 Топ-5 за сутки"
        other1, other2 = "week", "month"
    elif period == "week":
        time_delta = timedelta(weeks=1)
        title = "🏆 Топ-5 за неделю"
        other1, other2 = "day", "month"
    else:
        time_delta = timedelta(days=30)
        title = "🏆 Топ-5 за месяц"
        other1, other2 = "day", "week"

    all_users = users_table.all()
    top_users = []
    for user in all_users:
        referrals = user.get('referrals', [])
        recent_referrals = [
            r for r in referrals 
            if now - datetime.fromisoformat(users_table.search(User.user_id == r)[0]['registration_date']) <= time_delta
        ]
        if recent_referrals:
            top_users.append((
                f"{user['first_name']} {user['last_name']}".strip(),
                len(recent_referrals),
                user['user_id']
            ))

    top_users.sort(key=lambda x: x[1], reverse=True)
    top_5 = top_users[:5]
    
    top_text = f"{title}\n\n" + "\n".join(
        [f"{i+1}. {name} - {ref} друзей 👥" for i, (name, ref, _) in enumerate(top_5)]
    ) if top_5 else "📊 Пока нет данных для топа!"
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"📅 {'Сутки' if other1 == 'day' else 'Неделя' if other1 == 'week' else 'Месяц'}", 
        callback_data=f"top_{other1}"
    )
    builder.button(
        text=f"📅 {'Сутки' if other2 == 'day' else 'Неделя' if other2 == 'week' else 'Месяц'}", 
        callback_data=f"top_{other2}"
    )
    builder.button(text="🔙 Назад", callback_data="cancel")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        text=top_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌟 <b>Главное меню</b> 🌟\n\nВыберите раздел:",
        reply_markup=main_menu_markup(),
        parse_mode=ParseMode.HTML
    )

# Admin callbacks
@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    now = datetime.now()
    users = users_table.all()
    withdrawals = withdrawals_table.all()
    
    users_day = len([
        u for u in users 
        if now - datetime.fromisoformat(u['registration_date']) <= timedelta(days=1)
    ])
    users_week = len([
        u for u in users 
        if now - datetime.fromisoformat(u['registration_date']) <= timedelta(weeks=1)
    ])
    users_month = len([
        u for u in users 
        if now - datetime.fromisoformat(u['registration_date']) <= timedelta(days=30)
    ])
    users_total = len(users)
    
    stars_day = sum(
        w['stars'] for w in withdrawals 
        if w['status'] == '✅ Выполнено' 
        and now - datetime.fromisoformat(w['timestamp']) <= timedelta(days=1)
    )
    stars_week = sum(
        w['stars'] for w in withdrawals 
        if w['status'] == '✅ Выполнено' 
        and now - datetime.fromisoformat(w['timestamp']) <= timedelta(weeks=1)
    )
    stars_month = sum(
        w['stars'] for w in withdrawals 
        if w['status'] == '✅ Выполнено' 
        and now - datetime.fromisoformat(w['timestamp']) <= timedelta(days=30)
    )
    stars_total = sum(
        w['stars'] for w in withdrawals 
        if w['status'] == '✅ Выполнено'
    )
    
    stats_text = (
        "📊 <b>Статистика бота</b> 📊\n\n"
        "👥 <b>Пользователи:</b>\n"
        f"├ За сутки: {users_day}\n"
        f"├ За неделю: {users_week}\n"
        f"├ За месяц: {users_month}\n"
        f"└ Всего: {users_total}\n\n"
        "💫 <b>Выведено звезд:</b>\n"
        f"├ За сутки: {stars_day} ⭐️\n"
        f"├ За неделю: {stars_week} ⭐️\n"
        f"├ За месяц: {stars_month} ⭐️\n"
        f"└ Всего: {stars_total} ⭐️"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="admin_back")
    await callback.message.edit_text(
        text=stats_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("admin_users_"))
async def admin_users_callback(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    page = int(callback.data.split("_")[2])
    all_users = users_table.all()
    
    if not all_users:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад", callback_data="admin_back")
        await callback.message.edit_text(
            "📭 Пользователей нет!",
            reply_markup=builder.as_markup()
        )
        return
    
    user = all_users[page - 1]
    reg_date = datetime.fromisoformat(user['registration_date']).strftime("%d.%m.%Y")
    status = "❄️ Заморожен" if user.get('frozen', False) else "✅ Активен"
    tasks_count = await get_completed_tasks_count(user['user_id'])
    
    user_text = (
        "👤 <b>Профиль пользователя</b>\n\n"
        f"🆔 ID: {hcode(user['user_id'])}\n"
        f"🔗 @{user['username']}\n\n"
        f"💫 Баланс: {user['balance']} ⭐️\n"
        f"🎯 Заданий: {tasks_count}\n"
        f"👥 Рефералов: {len(user.get('referrals', []))}\n\n"
        f"📅 Регистрация: {reg_date}\n"
        f"📊 Статус: {status}"
    )
    
    builder = InlineKeyboardBuilder()
    
    if page > 1:
        builder.button(text="◀️", callback_data=f"admin_users_{page-1}")
    builder.button(text=f"{page}/{len(all_users)}", callback_data="none")
    if page < len(all_users):
        builder.button(text="▶️", callback_data=f"admin_users_{page+1}")
    
    builder.button(text="❄️ Заморозить", callback_data=f"freeze_{user['user_id']}")
    builder.button(text="🔥 Разморозить", callback_data=f"unfreeze_{user['user_id']}")
    builder.button(text="🔄 Обнулить", callback_data=f"reset_{user['user_id']}")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    
    builder.adjust(3, 2, 1, 1)
    
    await callback.message.edit_text(
        text=user_text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("freeze_"))
async def freeze_user_callback(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    target_id = int(callback.data.split("_")[1])
    users_table.update({'frozen': True}, User.user_id == target_id)
    await callback.answer(f"❄️ Пользователь {target_id} заморожен!")

@dp.callback_query(F.data.startswith("unfreeze_"))
async def unfreeze_user_callback(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    target_id = int(callback.data.split("_")[1])
    users_table.update({'frozen': False}, User.user_id == target_id)
    await callback.answer(f"🔥 Пользователь {target_id} разморожен!")

@dp.callback_query(F.data.startswith("reset_"))
async def reset_user_callback(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    target_id = int(callback.data.split("_")[1])
    users_table.update({
        'balance': 0,
        'referrals': [],
        'used_promo_codes': [],
        'frozen': False,
        'pending_referrer': None
    }, User.user_id == target_id)
    await callback.answer(f"🔄 Аккаунт пользователя {target_id} обнулен!")

@dp.callback_query(F.data == "admin_add_promo")
async def admin_add_promo_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.add_promo_code)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "🎫 Введите текст промокода:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_delete_promo")
async def admin_delete_promo_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    all_promos = promo_table.all()
    if not all_promos:
        await callback.message.answer("📭 Список промокодов пуст!")
        return
    
    promo_list = "\n".join([
        f"{i+1}. {p['code']} - {p['reward']} ⭐️ (Лимит: {p['limit']}, Использовано: {len(p.get('used_by', []))})" 
        for i, p in enumerate(all_promos)
    ])
    
    await state.set_state(AdminStates.delete_promo)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        f"📋 Список промокодов:\n{promo_list}\n\nВведите номер промокода для удаления:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_add_check")
async def admin_add_check_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.add_check_amount)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "💫 Введите количество звезд для чека:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_delete_check")
async def admin_delete_check_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    all_checks = checks_table.all()
    if not all_checks:
        await callback.message.answer("📭 Список чеков пуст!")
        return
    
    checks_list = "\n".join([
        f"{i+1}. {c['code']} - {c['amount']}⭐ (Использовано: {len(c.get('used_by', []))}/{c['limit']})" 
        for i, c in enumerate(all_checks)
    ])
    
    await state.set_state(AdminStates.delete_check)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        f"📋 Список чеков:\n{checks_list}\n\nВведите номер чека для удаления:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_set_min_refs")
async def admin_set_min_refs_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.set_min_refs)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "👥 Введите минимальное количество рефералов для вывода:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_set_min_tasks")
async def admin_set_min_tasks_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.set_min_tasks)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "🎯 Введите минимальное количество заданий для вывода:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_set_ref_reward")
async def admin_set_ref_reward_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.set_ref_reward)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "⭐ Введите количество звезд за приглашенного реферала:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_freeze")
async def admin_freeze_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.freeze_user)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "❄️ Введите ID пользователя для заморозки:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_unfreeze")
async def admin_unfreeze_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.unfreeze_user)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "🔥 Введите ID пользователя для разморозки:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_reset")
async def admin_reset_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.set_state(AdminStates.reset_user)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data="admin_cancel")
    await callback.message.answer(
        "🔄 Введите ID пользователя для обнуления:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    await state.clear()
    await callback.answer("🚫 Действие отменено")
    
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📊 Статистика", "admin_stats"),
        ("👥 Пользователи", "admin_users_1"),
        ("🎫 Создать промокод", "admin_add_promo"),
        ("❌ Удалить промокод", "admin_delete_promo"),
        ("👥 Мин. рефералов", "admin_set_min_refs"),
        ("🎯 Мин. заданий", "admin_set_min_tasks"),
        ("⭐ Награда за реферала", "admin_set_ref_reward"),
        ("❄️ Заморозить", "admin_freeze"),
        ("🔥 Разморозить", "admin_unfreeze"),
        ("🔄 Обнулить", "admin_reset"),
        ("🧾 Создать чек", "admin_add_check"),
        ("🗑 Удалить чек", "admin_delete_check")
    ]
    
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    
    builder.adjust(2, 2, 2, 2, 2, 1)
    
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b> 🔧",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "admin_back")
async def admin_back_callback(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return
    
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📊 Статистика", "admin_stats"),
        ("👥 Пользователи", "admin_users_1"),
        ("🎫 Создать промокод", "admin_add_promo"),
        ("❌ Удалить промокод", "admin_delete_promo"),
        ("👥 Мин. рефералов", "admin_set_min_refs"),
        ("🎯 Мин. заданий", "admin_set_min_tasks"),
        ("⭐ Награда за реферала", "admin_set_ref_reward"),
        ("❄️ Заморозить", "admin_freeze"),
        ("🔥 Разморозить", "admin_unfreeze"),
        ("🔄 Обнулить", "admin_reset"),
        ("🧾 Создать чек", "admin_add_check"),
        ("🗑 Удалить чек", "admin_delete_check")
    ]
    
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    
    builder.adjust(2, 2, 2, 2, 2, 1)
    
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b> 🔧",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())