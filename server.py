import asyncio
import json
import os
import re
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
import logging

# Конфигурация - ОБА: и бот, и сессия
API_ID = 2040  # Телеграм API ID
API_HASH = 'b18441a1ff607e10a989891a5462e627'  # Телеграм API Hash
BOT_TOKEN = '8274874473:AAGQTVHI3CkwzotIuqiS6M2Whptcp-EpTnY'  # Ваш токен бота
OWNER_ID = 8524326478  # Ваш ID
SESSION_NAME = '+380962151936'  # Имя сессии вашего аккаунта

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Файлы для хранения данных
CONFIG_FILE = 'bot_config.json'
CACHE_FILE = 'cache.json'

class BotInterface:
    """Класс для работы с ботом (кнопки, меню)"""
    
    def __init__(self, token):
        self.token = token
        self.bot = None
        self.user_client = None  # Клиент для сессии пользователя
        self.config = {}
        self.active_monitoring = True
        self.deletion_stats = {
            'total_deleted': 0,
            'deleted_today': 0,
            'by_user': {},
            'by_chat': {}
        }
        
    async def initialize(self):
        """Инициализация бота"""
        logger.info("Инициализация бота...")
        
        # Загружаем конфигурацию
        self.config = self.load_config()
        
        # Создаем клиент для бота
        self.bot = TelegramClient(
            'bot_session',
            API_ID,
            API_HASH
        )
        
        # Запускаем бота с токеном
        await self.bot.start(bot_token=self.token)
        
        # Получаем информацию о боте
        me = await self.bot.get_me()
        logger.info(f"🤖 Бот запущен как @{me.username}")
        
        # Регистрируем обработчики команд бота
        await self.register_bot_handlers()
        
        return self.bot
    
    async def start_user_session(self):
        """Запуск сессии пользователя для удаления сообщений"""
        logger.info("Запуск сессии пользователя...")
        
        # Создаем клиент для сессии пользователя
        self.user_client = TelegramClient(
            SESSION_NAME,
            API_ID,
            API_HASH
        )
        
        # Запускаем сессию пользователя
        await self.user_client.start()
        
        # Получаем информацию о пользователе
        user_me = await self.user_client.get_me()
        logger.info(f"👤 Сессия пользователя: {user_me.first_name} (ID: {user_me.id})")
        
        # Регистрируем обработчик для удаления сообщений
        await self.register_user_handlers()
        
        return self.user_client
    
    def load_config(self):
        """Загрузка конфигурации"""
        default_config = {
            'blacklist': [],  # Список пользователей
            'enabled_chats': [],  # Список чатов
            'enabled_for_all': True,  # Работать во всех чатах
            'delete_notifications': True,  # Уведомления
            'delete_delay': 0  # Задержка удаления
        }
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
        
        return default_config
    
    def save_config(self):
        """Сохранение конфигурации"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    async def register_bot_handlers(self):
        """Регистрация обработчиков для бота (меню, команды)"""
        
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            """Обработчик команды /start"""
            if event.sender_id == OWNER_ID:
                await self.send_main_menu(event)
        
        @self.bot.on(events.NewMessage(pattern='/menu'))
        async def menu_handler(event):
            """Обработчик команды /menu"""
            if event.sender_id == OWNER_ID:
                await self.send_main_menu(event)
        
        @self.bot.on(events.NewMessage(pattern='/add'))
        async def add_handler(event):
            """Обработчик команды /add"""
            if event.sender_id == OWNER_ID:
                await self.handle_add_command(event)
        
        @self.bot.on(events.NewMessage(pattern='/remove'))
        async def remove_handler(event):
            """Обработчик команды /remove"""
            if event.sender_id == OWNER_ID:
                await self.handle_remove_command(event)
        
        @self.bot.on(events.NewMessage(pattern='/list'))
        async def list_handler(event):
            """Обработчик команды /list"""
            if event.sender_id == OWNER_ID:
                await self.show_blacklist(event)
        
        @self.bot.on(events.NewMessage(pattern='/stats'))
        async def stats_handler(event):
            """Обработчик команды /stats"""
            if event.sender_id == OWNER_ID:
                await self.show_stats(event)
        
        @self.bot.on(events.NewMessage(pattern='/toggle'))
        async def toggle_handler(event):
            """Обработчик команды /toggle"""
            if event.sender_id == OWNER_ID:
                self.active_monitoring = not self.active_monitoring
                status = "✅ Включен" if self.active_monitoring else "⏸️ Приостановлен"
                await event.reply(f"**Мониторинг:** {status}")
        
        @self.bot.on(events.NewMessage(pattern='/help'))
        async def help_handler(event):
            """Обработчик команды /help"""
            if event.sender_id == OWNER_ID:
                await self.show_help(event)
        
        @self.bot.on(events.NewMessage(pattern='/chats'))
        async def chats_handler(event):
            """Обработчик команды /chats"""
            if event.sender_id == OWNER_ID:
                await self.show_chat_menu(event)
        
        # Обработчик пересланных сообщений для добавления пользователей
        @self.bot.on(events.NewMessage)
        async def forwarded_handler(event):
            """Обработка пересланных сообщений"""
            if event.sender_id == OWNER_ID and event.message.forward:
                await self.handle_forwarded_message(event)
        
        # Обработчик callback запросов (кнопки)
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            """Обработчик нажатий на кнопки"""
            await self.handle_callback(event)
    
    async def register_user_handlers(self):
        """Регистрация обработчиков для сессии пользователя (удаление)"""
        
        @self.user_client.on(events.NewMessage())
        async def message_handler(event):
            """Обработчик сообщений для удаления"""
            if not self.active_monitoring:
                return
            
            try:
                # Проверяем, является ли сообщение реплаем
                if event.message.reply_to_msg_id:
                    await self.handle_reply_for_deletion(event)
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")
    
    async def handle_reply_for_deletion(self, event):
        """Обработка реплаев для удаления сообщений"""
        try:
            # Получаем сообщение, на которое сделан реплай
            chat_id = event.chat_id
            replied_msg = await event.get_reply_message()
            
            if not replied_msg:
                return
            
            # Проверяем, что реплай сделан на сообщение владельца
            if replied_msg.sender_id != OWNER_ID:
                return
            
            # Проверяем, включен ли мониторинг для этого чата
            if not self.config['enabled_for_all'] and chat_id not in self.config['enabled_chats']:
                return
            
            # Получаем информацию об отправителе реплая
            sender_id = event.sender_id
            sender = await event.get_sender()
            sender_username = getattr(sender, 'username', None)
            
            # Проверяем, находится ли отправитель в черном списке
            is_blacklisted = self.is_user_in_blacklist(sender_id, sender_username)
            
            if not is_blacklisted:
                return
            
            # Удаляем сообщение владельца
            try:
                # Небольшая задержка для надежности
                if self.config['delete_delay'] > 0:
                    await asyncio.sleep(self.config['delete_delay'])
                
                await replied_msg.delete()
                
                # Обновляем статистику
                self.deletion_stats['total_deleted'] += 1
                self.deletion_stats['deleted_today'] += 1
                
                user_id_str = str(sender_id)
                chat_id_str = str(chat_id)
                
                if user_id_str not in self.deletion_stats['by_user']:
                    self.deletion_stats['by_user'][user_id_str] = 0
                self.deletion_stats['by_user'][user_id_str] += 1
                
                if chat_id_str not in self.deletion_stats['by_chat']:
                    self.deletion_stats['by_chat'][chat_id_str] = 0
                self.deletion_stats['by_chat'][chat_id_str] += 1
                
                # Логируем удаление
                logger.info(f"✅ Удалено сообщение {replied_msg.id} в чате {chat_id}")
                
                # Отправляем уведомление через бота
                if self.config['delete_notifications']:
                    notification = (
                        f"🗑️ **Сообщение удалено!**\n\n"
                        f"👤 **Отправитель реплая:** {sender_id}\n"
                        f"💬 **Чат:** `{chat_id}`\n"
                        f"📝 **ID сообщения:** `{replied_msg.id}`\n"
                        f"⏰ **Время:** {datetime.now().strftime('%H:%M:%S')}"
                    )
                    
                    await self.bot.send_message(OWNER_ID, notification, parse_mode='md')
                    
            except Exception as e:
                error_msg = f"❌ Ошибка при удалении: {str(e)}"
                logger.error(error_msg)
                
                if "MESSAGE_DELETE_FORBIDDEN" in str(e):
                    error_msg += "\n\n⚠️ Нет прав на удаление в этом чате!"
                
                await self.bot.send_message(OWNER_ID, error_msg)
                
        except Exception as e:
            logger.error(f"Ошибка обработки реплая: {e}")
    
    def is_user_in_blacklist(self, user_id, username=None):
        """Проверка, находится ли пользователь в черном списке"""
        for user in self.config['blacklist']:
            # Проверка по ID
            if user['id'] == user_id:
                return True
            
            # Проверка по username
            if username and user.get('username'):
                if user['username'].lower() == username.lower():
                    return True
        
        return False
    
    async def send_main_menu(self, event):
        """Отправка главного меню"""
        menu_text = (
            f"🤖 **Главное меню - Автоудаление сообщений**\n\n"
            f"📊 **Статистика:**\n"
            f"• 👤 Пользователей в черном списке: **{len(self.config['blacklist'])}**\n"
            f"• 💬 Активных чатов: **{len(self.config['enabled_chats'])}**\n"
            f"• 🗑️ Всего удалено: **{self.deletion_stats['total_deleted']}**\n"
            f"• 🗑️ Удалено сегодня: **{self.deletion_stats['deleted_today']}**\n"
            f"• ⚡ Мониторинг: **{'✅ Активен' if self.active_monitoring else '⏸️ Приостановлен'}**\n\n"
            f"🌐 **Режим:** {'Все чаты' if self.config['enabled_for_all'] else 'Только выбранные'}"
        )
        
        buttons = [
            [Button.inline("👤 Управление пользователями", b"user_management"),
             Button.inline("💬 Управление чатами", b"chat_management")],
            [Button.inline("📊 Статистика", b"stats_menu"),
             Button.inline("⚙️ Настройки", b"settings_menu")],
            [Button.inline("➕ Быстрое добавление", b"quick_add"),
             Button.inline("📋 Помощь", b"help_menu")]
        ]
        
        await event.reply(menu_text, buttons=buttons, parse_mode='md')
    
    async def handle_add_command(self, event):
        """Обработка команды добавления"""
        args = event.message.text.split()
        
        if len(args) < 2:
            # Показываем меню добавления
            await event.reply(
                "👤 **Добавление пользователя**\n\n"
                "Отправьте:\n"
                "• ID пользователя\n"
                "• @username\n"
                "• Или перешлите сообщение от пользователя\n\n"
                "Пример: `/add @username`",
                buttons=[
                    [Button.inline("📋 Способы добавления", b"add_methods")],
                    [Button.inline("↩️ Назад", b"main_menu")]
                ]
            )
        else:
            user_input = ' '.join(args[1:])
            await self.add_user(event, user_input)
    
    async def handle_remove_command(self, event):
        """Обработка команды удаления"""
        args = event.message.text.split()
        
        if len(args) < 2:
            # Показываем черный список для удаления
            await self.show_blacklist_for_removal(event)
        else:
            user_input = ' '.join(args[1:])
            await self.remove_user(event, user_input)
    
    async def add_user(self, event, user_input):
        """Добавление пользователя в черный список"""
        status_msg = await event.reply("🔄 Обработка...")
        
        # Получаем информацию о пользователе
        user_info = await self.get_user_info(user_input)
        
        if not user_info:
            await status_msg.edit("❌ Не удалось найти пользователя.")
            return
        
        # Проверяем, есть ли уже пользователь
        if self.is_user_in_blacklist(user_info['id'], user_info.get('username')):
            await status_msg.edit("⚠️ Пользователь уже в черном списке!")
            return
        
        # Добавляем пользователя
        self.config['blacklist'].append(user_info)
        self.save_config()
        
        user_display = self.format_user_display(user_info)
        
        await status_msg.edit(
            f"✅ **Пользователь добавлен!**\n\n"
            f"{user_display}\n"
            f"🆔 ID: `{user_info['id']}`"
        )
        
        logger.info(f"Добавлен пользователь: {user_display}")
    
    async def remove_user(self, event, user_input):
        """Удаление пользователя из черного списка"""
        status_msg = await event.reply("🔄 Обработка...")
        
        # Получаем информацию о пользователе
        user_info = await self.get_user_info(user_input)
        
        if not user_info:
            await status_msg.edit("❌ Не удалось найти пользователя.")
            return
        
        # Ищем пользователя в черном списке
        for i, user in enumerate(self.config['blacklist']):
            if user['id'] == user_info['id']:
                # Удаляем пользователя
                removed_user = self.config['blacklist'].pop(i)
                self.save_config()
                
                user_display = self.format_user_display(removed_user)
                await status_msg.edit(f"✅ **Пользователь удален:**\n{user_display}")
                return
        
        await status_msg.edit("❌ Пользователь не найден в черном списке.")
    
    async def get_user_info(self, user_input):
        """Получение информации о пользователе"""
        try:
            # Убираем пробелы
            user_input = user_input.strip()
            
            # Если это ID
            if user_input.isdigit():
                user_id = int(user_input)
                try:
                    # Пробуем получить через бота
                    user = await self.bot.get_entity(user_id)
                    return {
                        'id': user.id,
                        'username': getattr(user, 'username', None),
                        'first_name': getattr(user, 'first_name', ''),
                        'last_name': getattr(user, 'last_name', '')
                    }
                except:
                    return {'id': user_id, 'username': None}
            
            # Если это @username
            elif user_input.startswith('@'):
                username = user_input[1:]
                user = await self.bot.get_entity(username)
                return {
                    'id': user.id,
                    'username': username,
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', '')
                }
            
            # Если это ссылка
            elif 't.me/' in user_input:
                username = user_input.split('t.me/')[-1]
                user = await self.bot.get_entity(username)
                return {
                    'id': user.id,
                    'username': username,
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', '')
                }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе: {e}")
        
        return None
    
    def format_user_display(self, user_info):
        """Форматирование отображения пользователя"""
        parts = []
        if user_info.get('first_name'):
            parts.append(user_info['first_name'])
        if user_info.get('last_name'):
            parts.append(user_info['last_name'])
        
        display = ' '.join(parts) if parts else f"ID: {user_info['id']}"
        
        if user_info.get('username'):
            display += f" (@{user_info['username']})"
        
        return display
    
    async def show_blacklist(self, event):
        """Показать черный список"""
        if not self.config['blacklist']:
            await event.reply("📋 **Черный список пуст.**", parse_mode='md')
            return
        
        text = "📋 **Черный список пользователей:**\n\n"
        
        for i, user in enumerate(self.config['blacklist'], 1):
            user_display = self.format_user_display(user)
            text += f"{i}. {user_display}\n"
            text += f"   🆔 `{user['id']}`\n\n"
        
        buttons = [
            [Button.inline("➖ Удалить пользователя", b"remove_user_menu")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(text, buttons=buttons, parse_mode='md')
    
    async def show_blacklist_for_removal(self, event):
        """Показать черный список для удаления"""
        if not self.config['blacklist']:
            await event.reply("📋 **Черный список пуст.**", parse_mode='md')
            return
        
        text = "👤 **Выберите пользователя для удаления:**\n\n"
        buttons = []
        
        for user in self.config['blacklist']:
            user_display = self.format_user_display(user)[:30]
            buttons.append([Button.inline(f"❌ {user_display}", f"remove_{user['id']}")])
        
        buttons.append([Button.inline("↩️ Назад", b"main_menu")])
        
        await event.reply(text, buttons=buttons)
    
    async def show_stats(self, event):
        """Показать статистику"""
        stats_text = (
            f"📊 **Статистика бота**\n\n"
            f"📅 **Дата:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"**Общая статистика:**\n"
            f"• 🗑️ Всего удалено сообщений: **{self.deletion_stats['total_deleted']}**\n"
            f"• 🗑️ Удалено сегодня: **{self.deletion_stats['deleted_today']}**\n"
            f"• 👤 Пользователей в черном списке: **{len(self.config['blacklist'])}**\n"
            f"• 💬 Мониторится чатов: **{'Все' if self.config['enabled_for_all'] else len(self.config['enabled_chats'])}**\n"
            f"• ⚡ Статус мониторинга: **{'✅ Активен' if self.active_monitoring else '⏸️ Приостановлен'}**"
        )
        
        buttons = [
            [Button.inline("🔄 Обновить", b"refresh_stats")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(stats_text, buttons=buttons, parse_mode='md')
    
    async def show_help(self, event):
        """Показать помощь"""
        help_text = """
        🤖 **Помощь по боту**\n\n
        **📋 Основные команды:**
        `/menu` - Главное меню
        `/add @username` - Добавить пользователя
        `/remove @username` - Удалить пользователя
        `/list` - Показать черный список
        `/stats` - Статистика
        `/toggle` - Вкл/выкл мониторинг
        `/help` - Эта справка\n\n
        **⚡ Как это работает:**
        1. Добавьте пользователей в черный список
        2. Бот мониторит все чаты
        3. При реплае от пользователя из черного списка
        4. Ваше сообщение моментально удаляется
        5. Вы получаете уведомление\n\n
        **👤 Добавление пользователей:**
        • По ID: `/add 123456789`
        • По @username: `/add @username`
        • По ссылке: `/add t.me/username`
        • Пересылкой: Просто перешлите сообщение
        """
        
        buttons = [
            [Button.inline("📚 Примеры команд", b"examples")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(help_text, buttons=buttons, parse_mode='md')
    
    async def show_chat_menu(self, event):
        """Показать меню управления чатами"""
        mode = "🌐 Все чаты" if self.config['enabled_for_all'] else "💬 Только выбранные"
        
        text = (
            f"💬 **Управление чатами**\n\n"
            f"Текущий режим: **{mode}**\n"
            f"Активных чатов: **{len(self.config['enabled_chats'])}**\n\n"
            f"Выберите действие:"
        )
        
        buttons = [
            [Button.inline("🌐 Переключить режим", b"toggle_chat_mode")],
            [Button.inline("➕ Добавить чат", b"add_chat")],
            [Button.inline("➖ Удалить чат", b"remove_chat")],
            [Button.inline("📋 Список чатов", b"list_chats")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(text, buttons=buttons, parse_mode='md')
    
    async def handle_forwarded_message(self, event):
        """Обработка пересланных сообщений"""
        try:
            forwarded = event.message.forward
            if forwarded:
                sender_id = forwarded.sender_id
                
                # Получаем информацию о пользователе
                try:
                    user = await self.bot.get_entity(sender_id)
                    user_info = {
                        'id': user.id,
                        'username': getattr(user, 'username', None),
                        'first_name': getattr(user, 'first_name', ''),
                        'last_name': getattr(user, 'last_name', '')
                    }
                    
                    # Проверяем, есть ли уже пользователь
                    if self.is_user_in_blacklist(user_info['id'], user_info.get('username')):
                        await event.reply("⚠️ Пользователь уже в черном списке!")
                        return
                    
                    # Добавляем пользователя
                    self.config['blacklist'].append(user_info)
                    self.save_config()
                    
                    user_display = self.format_user_display(user_info)
                    
                    await event.reply(
                        f"✅ **Пользователь добавлен из пересланного сообщения!**\n\n"
                        f"{user_display}\n"
                        f"🆔 ID: `{user_info['id']}`"
                    )
                    
                except Exception as e:
                    await event.reply(f"❌ Ошибка: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки пересланного сообщения: {e}")
    
    async def handle_callback(self, event):
        """Обработка нажатий на кнопки"""
        try:
            data = event.data.decode('utf-8')
            
            if data == 'main_menu':
                await self.send_main_menu(event)
            
            elif data == 'user_management':
                await event.edit(
                    "👤 **Управление пользователями**\n\n"
                    "Выберите действие:",
                    buttons=[
                        [Button.inline("➕ Добавить пользователя", b"add_user_menu")],
                        [Button.inline("➖ Удалить пользователя", b"remove_user_menu")],
                        [Button.inline("📋 Показать черный список", b"show_blacklist")],
                        [Button.inline("↩️ Назад", b"main_menu")]
                    ]
                )
            
            elif data == 'chat_management':
                await self.show_chat_menu(event)
            
            elif data == 'stats_menu':
                await self.show_stats(event)
            
            elif data == 'settings_menu':
                await self.show_settings(event)
            
            elif data == 'help_menu':
                await self.show_help(event)
            
            elif data == 'quick_add':
                await event.edit(
                    "➕ **Быстрое добавление**\n\n"
                    "Просто перешлите любое сообщение от пользователя, "
                    "которого хотите добавить в черный список.",
                    buttons=[[Button.inline("↩️ Назад", b"main_menu")]]
                )
            
            elif data == 'add_user_menu':
                await event.edit(
                    "👤 **Добавление пользователя**\n\n"
                    "Отправьте команду:\n"
                    "`/add @username`\n\n"
                    "Или перешлите сообщение от пользователя.",
                    buttons=[[Button.inline("↩️ Назад", b"user_management")]]
                )
            
            elif data == 'remove_user_menu':
                await self.show_blacklist_for_removal(event)
            
            elif data == 'show_blacklist':
                await self.show_blacklist(event)
            
            elif data == 'refresh_stats':
                await self.show_stats(event)
            
            elif data == 'examples':
                await event.edit(
                    "📚 **Примеры команд:**\n\n"
                    "`/add @username`\n"
                    "`/add 123456789`\n"
                    "`/add t.me/username`\n"
                    "`/remove @username`\n"
                    "`/list`\n"
                    "`/stats`\n"
                    "`/toggle`",
                    buttons=[[Button.inline("↩️ Назад", b"help_menu")]]
                )
            
            elif data == 'toggle_chat_mode':
                self.config['enabled_for_all'] = not self.config['enabled_for_all']
                self.save_config()
                
                mode = "🌐 Все чаты" if self.config['enabled_for_all'] else "💬 Только выбранные"
                await event.answer(f"Режим изменен: {mode}", alert=False)
                await self.show_chat_menu(event)
            
            elif data == 'add_chat':
                await event.edit(
                    "➕ **Добавление чата**\n\n"
                    "Перешлите сообщение из чата или отправьте ID чата.",
                    buttons=[[Button.inline("↩️ Назад", b"chat_management")]]
                )
            
            elif data == 'remove_chat':
                await event.edit(
                    "➖ **Удаление чата**\n\n"
                    "Эта функция в разработке.",
                    buttons=[[Button.inline("↩️ Назад", b"chat_management")]]
                )
            
            elif data == 'list_chats':
                await event.edit(
                    "📋 **Список чатов**\n\n"
                    "Активных чатов: 0",
                    buttons=[[Button.inline("↩️ Назад", b"chat_management")]]
                )
            
            elif data.startswith('remove_'):
                user_id = int(data.split('_')[1])
                await self.remove_user_by_id(event, user_id)
            
            elif data == 'add_methods':
                await event.edit(
                    "📋 **Способы добавления:**\n\n"
                    "1. **Командой:** `/add @username`\n"
                    "2. **По ID:** `/add 123456789`\n"
                    "3. **По ссылке:** `/add t.me/username`\n"
                    "4. **Пересылкой:** Просто перешлите сообщение",
                    buttons=[[Button.inline("↩️ Назад", b"add_user_menu")]]
                )
            
            await event.answer()
            
        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            await event.answer("❌ Ошибка", alert=True)
    
    async def remove_user_by_id(self, event, user_id):
        """Удаление пользователя по ID"""
        for i, user in enumerate(self.config['blacklist']):
            if user['id'] == user_id:
                # Удаляем пользователя
                removed_user = self.config['blacklist'].pop(i)
                self.save_config()
                
                user_display = self.format_user_display(removed_user)
                await event.edit(f"✅ **Пользователь удален:**\n{user_display}")
                
                # Ждем и возвращаемся в меню
                await asyncio.sleep(2)
                await self.show_blacklist_for_removal(event)
                return
        
        await event.answer("❌ Пользователь не найден", alert=True)
    
    async def show_settings(self, event):
        """Показать настройки"""
        notifications = "✅ Включены" if self.config['delete_notifications'] else "❌ Выключены"
        
        text = (
            f"⚙️ **Настройки**\n\n"
            f"**Текущие настройки:**\n"
            f"• 🔔 Уведомления: {notifications}\n"
            f"• ⏱️ Задержка удаления: {self.config['delete_delay']} сек.\n\n"
            f"Выберите настройку для изменения:"
        )
        
        buttons = [
            [Button.inline("🔔 Уведомления", b"toggle_notifications")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def run(self):
        """Основной метод запуска"""
        try:
            # Инициализируем бота
            await self.initialize()
            
            # Запускаем сессию пользователя
            await self.start_user_session()
            
            # Отправляем приветственное сообщение
            await self.send_welcome_message()
            
            logger.info("✅ Бот полностью запущен и готов к работе!")
            
            # Запускаем оба клиента
            await asyncio.gather(
                self.bot.run_until_disconnected(),
                self.user_client.run_until_disconnected()
            )
            
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            raise
    
    async def send_welcome_message(self):
        """Отправить приветственное сообщение"""
        welcome_text = (
            f"🤖 **Бот для автоматического удаления сообщений запущен!**\n\n"
            f"👤 **Владелец:** {OWNER_ID}\n"
            f"👥 **Пользователей в черном списке:** {len(self.config['blacklist'])}\n"
            f"💬 **Мониторинг чатов:** {'🌐 Все чаты' if self.config['enabled_for_all'] else f'💬 {len(self.config['enabled_chats'])} чатов'}\n"
            f"⚡ **Режим:** {'Активный мониторинг' if self.active_monitoring else 'Приостановлен'}\n\n"
            f"📋 **Используйте /menu для управления**"
        )
        
        try:
            await self.bot.send_message(OWNER_ID, welcome_text, parse_mode='md')
        except:
            pass


# Запуск бота
async def main():
    print("=" * 60)
    print("🤖 БОТ ДЛЯ АВТОМАТИЧЕСКОГО УДАЛЕНИЯ СООБЩЕНИЙ")
    print("=" * 60)
    print(f"👤 Владелец: {OWNER_ID}")
    print(f"🔑 Токен бота: {BOT_TOKEN[:15]}...")
    print(f"💾 Файл конфигурации: {CONFIG_FILE}")
    print("=" * 60)
    print("⚡ РАБОТАЕТ КАК:")
    print("• 🤖 Бот (BotFather) - отправка сообщений и кнопок")
    print("• 👤 Ваша сессия - удаление сообщений при реплаях")
    print("• ⚡ Разделение логики - интерфейс и удаление отдельно")
    print("=" * 60)
    print("🚀 Запуск...")
    
    bot = BotInterface(BOT_TOKEN)
    await bot.run()


if __name__ == "__main__":
    # Создаем event loop
    loop = asyncio.get_event_loop()
    
    try:
        # Запускаем бота
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    finally:
        loop.close()
