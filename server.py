import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events, Button
import logging

# Конфигурация
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'
BOT_TOKEN = '8274874473:AAGQTVHI3CkwzotIuqiS6M2Whptcp-EpTnY'
OWNER_ID = 8524326478
SESSION_NAME = '+380962151936'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Файл для хранения данных
CONFIG_FILE = 'bot_config.json'

class AutoDeleteBot:
    def __init__(self):
        self.config = self.load_config()
        self.active_monitoring = True
        self.deletion_count = 0
        
        # Клиент для бота (кнопки, меню)
        self.bot_client = TelegramClient(
            'bot_session',
            API_ID,
            API_HASH
        )
        
        # Клиент для сессии пользователя (удаление)
        self.user_client = TelegramClient(
            SESSION_NAME,
            API_ID,
            API_HASH
        )
        
    def load_config(self):
        """Загрузка конфигурации"""
        default_config = {
            'blacklist': [],  # Список пользователей
            'enabled_chats': [],  # Список чатов
            'enabled_for_all': True,  # Работать во всех чатах
            'delete_notifications': False  # Выключить уведомления
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
    
    def is_user_in_blacklist(self, user_id, username=None):
        """Проверка, находится ли пользователь в черном списке"""
        for user in self.config['blacklist']:
            # Проверка по ID
            if user['id'] == user_id:
                return True, user
            
            # Проверка по username
            if username and user.get('username'):
                if user['username'].lower() == username.lower():
                    return True, user
        
        return False, None
    
    async def start(self):
        """Запуск бота"""
        logger.info("Запуск бота для автоматического удаления сообщений...")
        
        # Запускаем бота (для кнопок и меню)
        await self.bot_client.start(bot_token=BOT_TOKEN)
        bot_me = await self.bot_client.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_me.username}")
        
        # Запускаем сессию пользователя (для удаления сообщений)
        await self.user_client.start()
        user_me = await self.user_client.get_me()
        logger.info(f"👤 Сессия пользователя: {user_me.first_name} (ID: {user_me.id})")
        
        # Регистрируем обработчики для бота (меню, команды)
        self.register_bot_handlers()
        
        # Регистрируем обработчики для сессии пользователя (удаление)
        self.register_user_handlers()
        
        # Отправляем приветственное сообщение
        await self.send_welcome_message()
        
        logger.info("✅ Бот готов к работе!")
        logger.info(f"👥 Пользователей в черном списке: {len(self.config['blacklist'])}")
        
        # Запускаем оба клиента параллельно
        await asyncio.gather(
            self.bot_client.run_until_disconnected(),
            self.user_client.run_until_disconnected()
        )
    
    def register_bot_handlers(self):
        """Регистрация обработчиков для бота (меню, команды)"""
        
        @self.bot_client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_main_menu(event)
        
        @self.bot_client.on(events.NewMessage(pattern='/menu'))
        async def menu_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_main_menu(event)
        
        @self.bot_client.on(events.NewMessage(pattern='/add'))
        async def add_handler(event):
            if event.sender_id == OWNER_ID:
                args = event.message.text.split()
                if len(args) > 1:
                    user_input = ' '.join(args[1:])
                    await self.add_user_command(event, user_input)
                else:
                    await self.show_add_menu(event)
        
        @self.bot_client.on(events.NewMessage(pattern='/remove'))
        async def remove_handler(event):
            if event.sender_id == OWNER_ID:
                args = event.message.text.split()
                if len(args) > 1:
                    user_input = ' '.join(args[1:])
                    await self.remove_user_command(event, user_input)
                else:
                    await self.show_remove_menu(event)
        
        @self.bot_client.on(events.NewMessage(pattern='/list'))
        async def list_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_blacklist(event)
        
        @self.bot_client.on(events.NewMessage(pattern='/stats'))
        async def stats_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_stats(event)
        
        @self.bot_client.on(events.NewMessage(pattern='/toggle'))
        async def toggle_handler(event):
            if event.sender_id == OWNER_ID:
                self.active_monitoring = not self.active_monitoring
                status = "✅ Включен" if self.active_monitoring else "⏸️ Приостановлен"
                await event.reply(f"**Мониторинг:** {status}")
        
        @self.bot_client.on(events.NewMessage(pattern='/help'))
        async def help_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_help(event)
        
        # Обработка пересланных сообщений
        @self.bot_client.on(events.NewMessage)
        async def forwarded_handler(event):
            if event.sender_id == OWNER_ID and event.message.forward:
                await self.handle_forwarded_message(event)
        
        # Обработчик callback запросов (кнопки)
        @self.bot_client.on(events.CallbackQuery)
        async def callback_handler(event):
            await self.handle_callback(event)
    
    def register_user_handlers(self):
        """Регистрация обработчиков для сессии пользователя (удаление)"""
        
        @self.user_client.on(events.NewMessage())
        async def message_handler(event):
            """Обработчик ВСЕХ сообщений для удаления"""
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
            is_blacklisted, user_info = self.is_user_in_blacklist(sender_id, sender_username)
            
            if not is_blacklisted:
                return
            
            # Удаляем сообщение владельца
            try:
                await replied_msg.delete()
                
                # Обновляем счетчик
                self.deletion_count += 1
                
                # Логируем удаление (в консоль, без отправки в Telegram)
                logger.info(f"🗑️ Удалено сообщение {replied_msg.id} в чате {chat_id}")
                logger.info(f"👤 Отправитель реплая: {sender_id} ({sender_username})")
                
            except Exception as e:
                logger.error(f"❌ Ошибка при удалении: {str(e)}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки реплая: {e}")
    
    async def send_welcome_message(self):
        """Отправка приветственного сообщения"""
        welcome_text = (
            f"🤖 **Бот для автоматического удаления сообщений запущен!**\n\n"
            f"👤 **Владелец:** {OWNER_ID}\n"
            f"👥 **Пользователей в черном списке:** {len(self.config['blacklist'])}\n"
            f"💬 **Мониторинг чатов:** {'🌐 Все чаты' if self.config['enabled_for_all'] else f'💬 {len(self.config['enabled_chats'])} чатов'}\n"
            f"⚡ **Режим:** {'Активный мониторинг' if self.active_monitoring else 'Приостановлен'}\n\n"
            f"📋 **Используйте команды:**\n"
            f"/menu - Главное меню\n"
            f"/add - Добавить пользователя\n"
            f"/list - Черный список\n"
            f"/stats - Статистика\n"
            f"/help - Помощь"
        )
        
        try:
            await self.bot_client.send_message(OWNER_ID, welcome_text, parse_mode='md')
        except:
            pass
    
    async def show_main_menu(self, event):
        """Показать главное меню"""
        menu_text = (
            f"🤖 **Главное меню - Автоудаление сообщений**\n\n"
            f"📊 **Статистика:**\n"
            f"• 👤 Пользователей в черном списке: **{len(self.config['blacklist'])}**\n"
            f"• 💬 Активных чатов: **{len(self.config['enabled_chats'])}**\n"
            f"• 🗑️ Всего удалено: **{self.deletion_count}**\n"
            f"• ⚡ Мониторинг: **{'✅ Активен' if self.active_monitoring else '⏸️ Приостановлен'}**\n\n"
            f"🌐 **Режим:** {'Все чаты' if self.config['enabled_for_all'] else 'Только выбранные'}"
        )
        
        buttons = [
            [Button.inline("👤 Управление пользователями", b"user_mgmt"),
             Button.inline("📊 Статистика", b"stats_menu")],
            [Button.inline("⚙️ Настройки", b"settings"),
             Button.inline("📋 Помощь", b"help_menu")]
        ]
        
        await event.reply(menu_text, buttons=buttons, parse_mode='md')
    
    async def show_add_menu(self, event):
        """Показать меню добавления"""
        text = (
            "👤 **Добавление пользователя в черный список**\n\n"
            "**Способы добавления:**\n"
            "1. **Командой:** `/add @username` или `/add 123456789`\n"
            "2. **Пересылкой:** Перешлите сообщение от пользователя\n"
            "3. **По ссылке:** `/add https://t.me/username`\n\n"
            "**Форматы поддерживаются:**\n"
            "• ID пользователя (123456789)\n"
            "• @username\n"
            "• t.me/username\n"
            "• Пересланные сообщения"
        )
        
        buttons = [
            [Button.inline("📋 Примеры команд", b"examples")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(text, buttons=buttons, parse_mode='md')
    
    async def add_user_command(self, event, user_input):
        """Команда добавления пользователя"""
        if not user_input:
            await event.reply("❌ Укажите пользователя для добавления.\nПример: `/add @username`")
            return
        
        status_msg = await event.reply("🔄 Обработка...")
        
        # Получаем информацию о пользователе
        user_info = await self.get_user_info(user_input)
        
        if not user_info:
            await status_msg.edit("❌ Не удалось найти пользователя.")
            return
        
        # Проверяем, есть ли уже пользователь
        is_blacklisted, existing_user = self.is_user_in_blacklist(user_info['id'], user_info.get('username'))
        
        if is_blacklisted:
            user_display = self.format_user_display(existing_user)
            await status_msg.edit(f"⚠️ Пользователь уже в черном списке:\n{user_display}")
            return
        
        # Добавляем пользователя
        self.config['blacklist'].append(user_info)
        self.save_config()
        
        user_display = self.format_user_display(user_info)
        
        await status_msg.edit(
            f"✅ **Пользователь добавлен в черный список!**\n\n"
            f"{user_display}\n"
            f"🆔 ID: `{user_info['id']}`\n\n"
            f"Теперь при ЛЮБЫХ реплаях от этого пользователя ваши сообщения будут автоматически удаляться."
        )
        
        logger.info(f"Добавлен пользователь: {user_display} (ID: {user_info['id']})")
    
    async def get_user_info(self, user_input):
        """Получение информации о пользователе"""
        try:
            user_input = user_input.strip()
            
            # Если это ID
            if user_input.isdigit():
                user_id = int(user_input)
                try:
                    user = await self.bot_client.get_entity(user_id)
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
                user = await self.bot_client.get_entity(username)
                return {
                    'id': user.id,
                    'username': username,
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', '')
                }
            
            # Если это ссылка
            elif 't.me/' in user_input:
                username = user_input.split('t.me/')[-1]
                user = await self.bot_client.get_entity(username)
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
    
    async def show_remove_menu(self, event):
        """Показать меню удаления"""
        if not self.config['blacklist']:
            await event.reply("📋 **Черный список пуст.**", parse_mode='md')
            return
        
        text = "👤 **Выберите пользователя для удаления:**\n\n"
        buttons = []
        
        for user in self.config['blacklist']:
            user_display = self.format_user_display(user)[:30]
            buttons.append([Button.inline(f"❌ {user_display}", f"remove_{user['id']}")])
        
        buttons.append([Button.inline("↩️ Назад", b"user_mgmt")])
        
        await event.reply(text, buttons=buttons)
    
    async def remove_user_command(self, event, user_input):
        """Команда удаления пользователя"""
        if not user_input:
            await self.show_remove_menu(event)
            return
        
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
    
    async def show_blacklist(self, event):
        """Показать черный список"""
        if not self.config['blacklist']:
            await event.reply("📋 **Черный список пуст.**\n\nИспользуйте `/add @username` для добавления пользователей.", parse_mode='md')
            return
        
        text = "📋 **Черный список пользователей:**\n\n"
        
        for i, user in enumerate(self.config['blacklist'], 1):
            user_display = self.format_user_display(user)
            text += f"{i}. {user_display}\n"
            text += f"   🆔 `{user['id']}`\n\n"
        
        buttons = [
            [Button.inline("➖ Удалить пользователя", b"remove_menu")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(text, buttons=buttons, parse_mode='md')
    
    async def show_stats(self, event):
        """Показать статистику"""
        stats_text = (
            f"📊 **Статистика бота**\n\n"
            f"🗑️ **Всего удалено сообщений:** {self.deletion_count}\n"
            f"👤 **Пользователей в черном списке:** {len(self.config['blacklist'])}\n"
            f"💬 **Мониторится чатов:** {'Все' if self.config['enabled_for_all'] else len(self.config['enabled_chats'])}\n"
            f"⚡ **Статус мониторинга:** {'✅ Активен' if self.active_monitoring else '⏸️ Приостановлен'}"
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
        2. Бот мониторит ВСЕ чаты
        3. Когда пользователь из черного списка отвечает (реплаит) на ЛЮБОЕ ваше сообщение
        4. Ваше сообщение моментально удаляется
        5. Удаляются ВСЕ ваши сообщения, на которые он отвечает\n\n
        **👤 Добавление пользователей:**
        • По ID: `/add 123456789`
        • По @username: `/add @username`
        • По ссылке: `/add t.me/username`
        • Пересылкой: Просто перешлите сообщение от пользователя
        """
        
        buttons = [
            [Button.inline("📚 Примеры команд", b"examples")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(help_text, buttons=buttons, parse_mode='md')
    
    async def handle_forwarded_message(self, event):
        """Обработка пересланных сообщений"""
        try:
            forwarded = event.message.forward
            if forwarded:
                sender_id = forwarded.sender_id
                
                # Получаем информацию о пользователе
                try:
                    user = await self.bot_client.get_entity(sender_id)
                    user_info = {
                        'id': user.id,
                        'username': getattr(user, 'username', None),
                        'first_name': getattr(user, 'first_name', ''),
                        'last_name': getattr(user, 'last_name', '')
                    }
                    
                    # Проверяем, есть ли уже пользователь
                    is_blacklisted, existing_user = self.is_user_in_blacklist(user_info['id'], user_info.get('username'))
                    
                    if is_blacklisted:
                        user_display = self.format_user_display(existing_user)
                        await event.reply(f"⚠️ Пользователь уже в черном списке:\n{user_display}")
                        return
                    
                    # Добавляем пользователя
                    self.config['blacklist'].append(user_info)
                    self.save_config()
                    
                    user_display = self.format_user_display(user_info)
                    
                    await event.reply(
                        f"✅ **Пользователь добавлен из пересланного сообщения!**\n\n"
                        f"{user_display}\n"
                        f"🆔 ID: `{user_info['id']}`\n\n"
                        f"Теперь при любых реплаях от этого пользователя ваши сообщения будут автоматически удаляться."
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
                await self.show_main_menu(event)
            
            elif data == 'user_mgmt':
                await event.edit(
                    "👤 **Управление пользователями**\n\n"
                    "Выберите действие:",
                    buttons=[
                        [Button.inline("➕ Добавить пользователя", b"add_menu")],
                        [Button.inline("➖ Удалить пользователя", b"remove_menu")],
                        [Button.inline("📋 Показать черный список", b"show_list")],
                        [Button.inline("↩️ Назад", b"main_menu")]
                    ]
                )
            
            elif data == 'stats_menu':
                await self.show_stats(event)
            
            elif data == 'help_menu':
                await self.show_help(event)
            
            elif data == 'settings':
                await self.show_settings(event)
            
            elif data == 'add_menu':
                await self.show_add_menu(event)
            
            elif data == 'remove_menu':
                await self.show_remove_menu(event)
            
            elif data == 'show_list':
                await self.show_blacklist(event)
            
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
                    buttons=[[Button.inline("↩️ Назад", b"add_menu")]]
                )
            
            elif data == 'refresh_stats':
                await self.show_stats(event)
            
            elif data.startswith('remove_'):
                user_id = int(data.split('_')[1])
                await self.remove_user_by_id(event, user_id)
            
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
                await self.show_remove_menu(event)
                return
        
        await event.answer("❌ Пользователь не найден", alert=True)
    
    async def show_settings(self, event):
        """Показать настройки"""
        notifications = "✅ Включены" if self.config['delete_notifications'] else "❌ Выключены"
        
        text = (
            f"⚙️ **Настройки**\n\n"
            f"**Текущие настройки:**\n"
            f"• 🔔 Уведомления: {notifications}\n"
            f"• 🌐 Режим чатов: {'Все чаты' if self.config['enabled_for_all'] else 'Только выбранные'}\n\n"
            f"Выберите настройку для изменения:"
        )
        
        buttons = [
            [Button.inline("🔔 Уведомления", b"toggle_notifs")],
            [Button.inline("🌐 Режим чатов", b"toggle_chat_mode")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def run(self):
        """Основной метод запуска"""
        try:
            await self.start()
        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            raise


# Запуск бота
async def main():
    print("=" * 60)
    print("🤖 БОТ ДЛЯ АВТОМАТИЧЕСКОГО УДАЛЕНИЯ СООБЩЕНИЙ")
    print("=" * 60)
    print(f"👤 Владелец: {OWNER_ID}")
    print(f"🔑 Токен бота: {BOT_TOKEN[:15]}...")
    print(f"💾 Файл конфигурации: {CONFIG_FILE}")
    print("=" * 60)
    print("⚡ ВОЗМОЖНОСТИ:")
    print("• 🗑️ УДАЛЯЕТ ВСЕ ВАШИ СООБЩЕНИЯ при реплаях")
    print("• ⚡ РАБОТАЕТ ВО ВСЕХ ЧАТАХ автоматически")
    print("• 🔕 БЕЗ УВЕДОМЛЕНИЙ - тихое удаление")
    print("• 📱 УДОБНОЕ МЕНЮ с кнопками")
    print("• 👤 ПОДДЕРЖКА USERNAME")
    print("=" * 60)
    print("🚀 Запуск...")
    
    bot = AutoDeleteBot()
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
