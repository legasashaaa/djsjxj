import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.tl.types import PeerUser, PeerChannel, PeerChat
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
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
        self.client = TelegramClient(
            SESSION_NAME,
            API_ID,
            API_HASH
        )
        self.bot = None
        self.config = self.load_config()
        
    def load_config(self):
        """Загрузка конфигурации из файла"""
        default_config = {
            'blacklist': [],  # Список пользователей (ID или username)
            'enabled_chats': [],  # Список чатов, где включено удаление
            'enabled_for_all': False,  # Удалять во всех чатах
            'delete_notifications': True  # Отправлять уведомления об удалении
        }
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
        
        return default_config
    
    def save_config(self):
        """Сохранение конфигурации в файл"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    async def resolve_username(self, username):
        """Преобразование username в ID"""
        try:
            if username.startswith('@'):
                username = username[1:]
            
            user = await self.bot.get_entity(username)
            return user.id
        except Exception as e:
            logger.error(f"Ошибка при получении ID пользователя {username}: {e}")
            return None
    
    async def get_user_info(self, user_input):
        """Получение информации о пользователе"""
        try:
            # Если это ID
            if user_input.isdigit():
                user_id = int(user_input)
                try:
                    user = await self.bot.get_entity(PeerUser(user_id))
                    return {
                        'id': user.id,
                        'username': getattr(user, 'username', None),
                        'first_name': getattr(user, 'first_name', ''),
                        'last_name': getattr(user, 'last_name', '')
                    }
                except:
                    return {'id': user_id, 'username': None}
            
            # Если это username
            elif user_input.startswith('@'):
                username = user_input[1:]
                user = await self.bot.get_entity(username)
                return {
                    'id': user.id,
                    'username': username,
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', '')
                }
            
            # Если это упоминание
            elif user_input.startswith('https://t.me/'):
                username = user_input.split('/')[-1]
                user = await self.bot.get_entity(username)
                return {
                    'id': user.id,
                    'username': username,
                    'first_name': getattr(user, 'first_name', ''),
                    'last_name': getattr(user, 'last_name', '')
                }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе {user_input}: {e}")
            return None
    
    async def start(self):
        """Запуск бота"""
        logger.info("Запуск бота...")
        
        await self.client.start(bot_token=BOT_TOKEN)
        self.bot = self.client
        
        me = await self.bot.get_me()
        logger.info(f"Бот запущен как @{me.username}")
        
        self.register_handlers()
        
        logger.info("Бот готов к работе")
        await self.bot.run_until_disconnected()
    
    def register_handlers(self):
        """Регистрация обработчиков событий"""
        
        @self.bot.on(events.NewMessage(incoming=True))
        async def message_handler(event):
            """Обработчик новых сообщений"""
            try:
                # Проверяем, является ли сообщение реплаем
                if event.message.reply_to_msg_id:
                    replied_msg = await event.get_reply_message()
                    
                    # Проверяем, что реплай сделан на наше сообщение
                    if replied_msg and replied_msg.sender_id == OWNER_ID:
                        chat_id = event.chat_id
                        
                        # Проверяем, включено ли удаление в этом чате
                        if (self.config['enabled_for_all'] or 
                            chat_id in self.config['enabled_chats']):
                            
                            sender_id = event.sender_id
                            sender_username = None
                            
                            # Получаем информацию об отправителе
                            try:
                                sender = await event.get_sender()
                                sender_username = getattr(sender, 'username', None)
                            except:
                                pass
                            
                            # Проверяем, есть ли отправитель в черном списке
                            should_delete = False
                            user_in_blacklist = None
            
                            for user in self.config['blacklist']:
                                # Проверяем по ID
                                if user.get('id') == sender_id:
                                    should_delete = True
                                    user_in_blacklist = user
                                    break
                                # Проверяем по username
                                elif (sender_username and 
                                      user.get('username') and 
                                      user['username'].lower() == sender_username.lower()):
                                    should_delete = True
                                    user_in_blacklist = user
                                    break
                            
                            if should_delete:
                                logger.info(f"Обнаружен реплай от {sender_id} ({sender_username}) в чате {chat_id}")
                                
                                try:
                                    await replied_msg.delete()
                                    logger.info(f"Сообщение {replied_msg.id} удалено")
                                    
                                    if self.config['delete_notifications']:
                                        user_info = f"{user_in_blacklist.get('first_name', '')} {user_in_blacklist.get('last_name', '')}".strip()
                                        username_info = f"(@{user_in_blacklist.get('username')})" if user_in_blacklist.get('username') else ""
                                        
                                        await self.bot.send_message(
                                            OWNER_ID,
                                            f"🗑️ **Сообщение удалено!**\n\n"
                                            f"👤 **Отправитель:** {user_info} {username_info}\n"
                                            f"🆔 **ID:** `{sender_id}`\n"
                                            f"💬 **Чат:** `{chat_id}`\n"
                                            f"📝 **ID сообщения:** `{replied_msg.id}`\n"
                                            f"⏰ **Время:** {datetime.now().strftime('%H:%M:%S')}",
                                            parse_mode='md'
                                        )
                                except Exception as e:
                                    logger.error(f"Ошибка при удалении: {e}")
                
                # Обработка команд от владельца
                if event.message.sender_id == OWNER_ID and event.message.text:
                    await self.handle_owner_commands(event)
            
            except Exception as e:
                logger.error(f"Ошибка в обработчике: {e}")
    
    async def handle_owner_commands(self, event):
        """Обработка команд от владельца"""
        text = event.message.text.strip()
        
        if text == '/start':
            await self.show_main_menu(event)
        
        elif text == '/menu':
            await self.show_main_menu(event)
        
        elif text == '/add_user':
            await event.reply(
                "👤 **Добавление пользователя в черный список**\n\n"
                "Отправьте:\n"
                "• ID пользователя (например: 123456789)\n"
                "• Username (например: @username)\n"
                "• Ссылку (например: https://t.me/username)\n\n"
                "Или используйте кнопки ниже:",
                buttons=[
                    [Button.inline("📋 Список участников чата", b"list_chat_members")],
                    [Button.inline("↩️ Назад", b"main_menu")]
                ]
            )
        
        elif text.startswith('/add '):
            user_input = text[5:].strip()
            await self.add_user_to_blacklist(event, user_input)
        
        elif text == '/remove_user':
            await self.show_blacklist_for_removal(event)
        
        elif text.startswith('/remove '):
            user_input = text[8:].strip()
            await self.remove_user_from_blacklist(event, user_input)
        
        elif text == '/list':
            await self.show_blacklist(event)
        
        elif text == '/chats':
            await self.show_chat_management(event)
        
        elif text == '/add_chat':
            await event.reply(
                "💬 **Добавление чата**\n\n"
                "Чтобы добавить чат, отправьте:\n"
                "1. Перешлите любое сообщение из чата\n"
                "2. Или укажите ID чата (например: -1001234567890)\n"
                "3. Или username чата (например: @chat_username)\n\n"
                "Или используйте кнопки:",
                buttons=[
                    [Button.inline("📊 Мои чаты", b"list_my_chats")],
                    [Button.inline("↩️ Назад", b"chat_management")]
                ]
            )
        
        elif text == '/remove_chat':
            await self.show_enabled_chats_for_removal(event)
        
        elif text == '/settings':
            await self.show_settings(event)
        
        elif text == '/help':
            await self.show_help(event)
    
    async def show_main_menu(self, event):
        """Показать главное меню"""
        blacklist_count = len(self.config['blacklist'])
        enabled_chats_count = len(self.config['enabled_chats'])
        mode = "🌐 Во всех чатах" if self.config['enabled_for_all'] else f"💬 В {enabled_chats_count} чате(ах)"
        
        await event.reply(
            f"🤖 **Главное меню**\n\n"
            f"📊 **Статистика:**\n"
            f"• 👤 Пользователей в черном списке: {blacklist_count}\n"
            f"• 💬 Активных чатов: {enabled_chats_count}\n"
            f"• ⚙️ Режим работы: {mode}\n\n"
            f"**Выберите действие:**",
            buttons=[
                [Button.inline("👤 Управление пользователями", b"user_management")],
                [Button.inline("💬 Управление чатами", b"chat_management")],
                [Button.inline("⚙️ Настройки", b"settings")],
                [Button.inline("📋 Справка", b"help")]
            ]
        )
    
    async def show_user_management(self, event):
        """Показать меню управления пользователями"""
        await event.edit(
            "👤 **Управление пользователями**\n\n"
            "Выберите действие:",
            buttons=[
                [Button.inline("➕ Добавить пользователя", b"add_user")],
                [Button.inline("➖ Удалить пользователя", b"remove_user")],
                [Button.inline("📋 Показать черный список", b"show_blacklist")],
                [Button.inline("↩️ Назад", b"main_menu")]
            ]
        )
    
    async def show_chat_management(self, event):
        """Показать меню управления чатами"""
        mode = "🌐 Удалять во всех чатах" if self.config['enabled_for_all'] else "💬 Удалять только в выбранных чатах"
        
        await event.edit(
            f"💬 **Управление чатами**\n\n"
            f"Текущий режим: {mode}\n\n"
            f"Выберите действие:",
            buttons=[
                [Button.inline("➕ Добавить чат", b"add_chat")],
                [Button.inline("➖ Удалить чат", b"remove_chat")],
                [Button.inline("📋 Список чатов", b"list_enabled_chats")],
                [Button.inline("🌐 Все чаты", b"toggle_all_chats")],
                [Button.inline("↩️ Назад", b"main_menu")]
            ]
        )
    
    async def show_settings(self, event):
        """Показать настройки"""
        notifications = "✅ Включены" if self.config['delete_notifications'] else "❌ Выключены"
        
        await event.edit(
            f"⚙️ **Настройки**\n\n"
            f"Текущие настройки:\n"
            f"• 🔔 Уведомления: {notifications}\n\n"
            f"Выберите настройку для изменения:",
            buttons=[
                [Button.inline("🔔 Уведомления", b"toggle_notifications")],
                [Button.inline("↩️ Назад", b"main_menu")]
            ]
        )
    
    async def show_help(self, event):
        """Показать справку"""
        help_text = """
        🤖 **Справка по боту**\n\n
        **Основные команды:**
        `/start` или `/menu` - Главное меню
        `/add_user` - Добавить пользователя
        `/remove_user` - Удалить пользователя
        `/list` - Показать черный список
        `/chats` - Управление чатами
        `/settings` - Настройки
        `/help` - Эта справка\n\n
        **Как добавить пользователя:**
        1. Используйте команду `/add_user`
        2. Или отправьте `/add <user_id/@username/ссылка>`
        3. Или используйте кнопку "Список участников чата"\n\n
        **Формат добавления:**
        • ID: `123456789`
        • Username: `@username`
        • Ссылка: `https://t.me/username`\n\n
        **Как добавить чат:**
        1. Перешлите сообщение из чата боту
        2. Или используйте команду `/add_chat`
        """
        
        await event.edit(
            help_text,
            buttons=[
                [Button.inline("↩️ Назад", b"main_menu")]
            ]
        )
    
    async def add_user_to_blacklist(self, event, user_input):
        """Добавить пользователя в черный список"""
        user_info = await self.get_user_info(user_input)
        
        if not user_info:
            await event.reply("❌ Не удалось найти пользователя. Проверьте введенные данные.")
            return
        
        # Проверяем, есть ли уже пользователь в черном списке
        for user in self.config['blacklist']:
            if user['id'] == user_info['id']:
                await event.reply(f"⚠️ Пользователь уже находится в черном списке!")
                return
        
        # Добавляем пользователя
        self.config['blacklist'].append(user_info)
        self.save_config()
        
        user_display = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        if user_info.get('username'):
            user_display += f" (@{user_info['username']})"
        
        await event.reply(
            f"✅ **Пользователь добавлен в черный список!**\n\n"
            f"👤 **Имя:** {user_display}\n"
            f"🆔 **ID:** `{user_info['id']}`\n\n"
            f"Теперь при реплаях от этого пользователя ваши сообщения будут автоматически удаляться."
        )
    
    async def remove_user_from_blacklist(self, event, user_input):
        """Удалить пользователя из черного списка"""
        user_info = await self.get_user_info(user_input)
        
        if not user_info:
            await event.reply("❌ Не удалось найти пользователя. Проверьте введенные данные.")
            return
        
        # Ищем пользователя в черном списке
        for i, user in enumerate(self.config['blacklist']):
            if user['id'] == user_info['id']:
                removed_user = self.config['blacklist'].pop(i)
                self.save_config()
                
                user_display = f"{removed_user.get('first_name', '')} {removed_user.get('last_name', '')}".strip()
                if removed_user.get('username'):
                    user_display += f" (@{removed_user['username']})"
                
                await event.reply(f"✅ **Пользователь удален из черного списка!**\n\n👤 {user_display}")
                return
        
        await event.reply("❌ Пользователь не найден в черном списке.")
    
    async def show_blacklist(self, event):
        """Показать черный список"""
        if not self.config['blacklist']:
            await event.reply("📋 **Черный список пуст.**\n\nДобавьте пользователей через меню управления.")
            return
        
        message = "📋 **Черный список пользователей:**\n\n"
        
        for i, user in enumerate(self.config['blacklist'], 1):
            user_display = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            if user.get('username'):
                user_display += f" (@{user['username']})"
            
            message += f"{i}. {user_display}\n"
            message += f"   🆔 `{user['id']}`\n\n"
        
        await event.reply(message, parse_mode='md')
    
    async def show_blacklist_for_removal(self, event):
        """Показать черный список для удаления"""
        if not self.config['blacklist']:
            await event.reply("📋 Черный список пуст.")
            return
        
        buttons = []
        for user in self.config['blacklist']:
            user_display = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()[:20]
            if not user_display:
                user_display = f"ID: {user['id']}"
            
            if user.get('username'):
                user_display += f" (@{user['username'][:10]})"
            
            buttons.append([Button.inline(
                f"❌ {user_display}", 
                f"remove_user_{user['id']}"
            )])
        
        buttons.append([Button.inline("↩️ Назад", b"user_management")])
        
        await event.edit(
            "👤 **Выберите пользователя для удаления:**",
            buttons=buttons
        )
    
    async def add_chat_to_list(self, event, chat_id, chat_title):
        """Добавить чат в список разрешенных"""
        if chat_id in self.config['enabled_chats']:
            await event.reply(f"⚠️ Чат '{chat_title}' уже в списке!")
            return
        
        self.config['enabled_chats'].append(chat_id)
        self.save_config()
        
        await event.reply(f"✅ **Чат добавлен!**\n\n💬 {chat_title}\n🆔 `{chat_id}`")
    
    async def show_enabled_chats(self, event):
        """Показать список разрешенных чатов"""
        if not self.config['enabled_chats']:
            await event.reply("📋 **Список чатов пуст.**\n\nДобавьте чаты через меню управления.")
            return
        
        message = "💬 **Список активных чатов:**\n\n"
        
        for i, chat_id in enumerate(self.config['enabled_chats'], 1):
            try:
                chat = await self.bot.get_entity(chat_id)
                chat_title = getattr(chat, 'title', 'Неизвестный чат')
                message += f"{i}. {chat_title}\n   🆔 `{chat_id}`\n\n"
            except:
                message += f"{i}. Неизвестный чат\n   🆔 `{chat_id}`\n\n"
        
        await event.reply(message, parse_mode='md')
    
    async def show_enabled_chats_for_removal(self, event):
        """Показать список чатов для удаления"""
        if not self.config['enabled_chats']:
            await event.reply("📋 Список чатов пуст.")
            return
        
        buttons = []
        for chat_id in self.config['enabled_chats']:
            try:
                chat = await self.bot.get_entity(chat_id)
                chat_title = getattr(chat, 'title', f'Чат {chat_id}')[:30]
            except:
                chat_title = f'Чат {chat_id}'[:30]
            
            buttons.append([Button.inline(
                f"❌ {chat_title}", 
                f"remove_chat_{chat_id}"
            )])
        
        buttons.append([Button.inline("↩️ Назад", b"chat_management")])
        
        await event.edit(
            "💬 **Выберите чат для удаления:**",
            buttons=buttons
        )
    
    @self.bot.on(events.CallbackQuery)
    async def callback_handler(event):
        """Обработчик callback запросов"""
        try:
            data = event.data.decode('utf-8')
            
            if data == 'main_menu':
                await self.show_main_menu(event)
            
            elif data == 'user_management':
                await self.show_user_management(event)
            
            elif data == 'chat_management':
                await self.show_chat_management(event)
            
            elif data == 'settings':
                await self.show_settings(event)
            
            elif data == 'help':
                await self.show_help(event)
            
            elif data == 'add_user':
                await event.edit(
                    "👤 **Добавление пользователя**\n\n"
                    "Отправьте мне:\n"
                    "• ID пользователя\n"
                    "• @username\n"
                    "• Или ссылку на профиль",
                    buttons=[[Button.inline("↩️ Назад", b"user_management")]]
                )
            
            elif data == 'remove_user':
                await self.show_blacklist_for_removal(event)
            
            elif data == 'show_blacklist':
                await self.show_blacklist(event)
                await event.answer()
                return
            
            elif data == 'add_chat':
                await event.edit(
                    "💬 **Добавление чата**\n\n"
                    "Перешлите мне сообщение из чата или отправьте ID чата",
                    buttons=[[Button.inline("↩️ Назад", b"chat_management")]]
                )
            
            elif data == 'remove_chat':
                await self.show_enabled_chats_for_removal(event)
            
            elif data == 'list_enabled_chats':
                await self.show_enabled_chats(event)
                await event.answer()
                return
            
            elif data == 'toggle_all_chats':
                self.config['enabled_for_all'] = not self.config['enabled_for_all']
                self.save_config()
                
                mode = "🌐 Удалять во всех чатах" if self.config['enabled_for_all'] else "💬 Удалять только в выбранных чатах"
                await event.edit(f"✅ Режим изменен: {mode}")
                await asyncio.sleep(2)
                await self.show_chat_management(event)
            
            elif data == 'toggle_notifications':
                self.config['delete_notifications'] = not self.config['delete_notifications']
                self.save_config()
                
                status = "✅ Включены" if self.config['delete_notifications'] else "❌ Выключены"
                await event.edit(f"✅ Уведомления: {status}")
                await asyncio.sleep(2)
                await self.show_settings(event)
            
            elif data.startswith('remove_user_'):
                user_id = int(data[12:])
                
                for i, user in enumerate(self.config['blacklist']):
                    if user['id'] == user_id:
                        removed_user = self.config['blacklist'].pop(i)
                        self.save_config()
                        
                        user_display = f"{removed_user.get('first_name', '')} {removed_user.get('last_name', '')}".strip()
                        if removed_user.get('username'):
                            user_display += f" (@{removed_user['username']})"
                        
                        await event.edit(f"✅ **Пользователь удален:** {user_display}")
                        await asyncio.sleep(2)
                        await self.show_user_management(event)
                        break
            
            elif data.startswith('remove_chat_'):
                chat_id = int(data[12:])
                
                if chat_id in self.config['enabled_chats']:
                    self.config['enabled_chats'].remove(chat_id)
                    self.save_config()
                    
                    try:
                        chat = await self.bot.get_entity(chat_id)
                        chat_title = getattr(chat, 'title', f'Чат {chat_id}')
                    except:
                        chat_title = f'Чат {chat_id}'
                    
                    await event.edit(f"✅ **Чат удален:** {chat_title}")
                    await asyncio.sleep(2)
                    await self.show_chat_management(event)
            
            elif data == 'list_chat_members':
                await event.edit(
                    "📋 **Получение списка участников**\n\n"
                    "Перешлите мне сообщение из чата, участников которого хотите увидеть",
                    buttons=[[Button.inline("↩️ Назад", b"add_user")]]
                )
            
            elif data == 'list_my_chats':
                await event.edit(
                    "📊 **Получение списка чатов**\n\n"
                    "Перешлите мне сообщение из чата, который хотите добавить",
                    buttons=[[Button.inline("↩️ Назад", b"add_chat")]]
                )
            
            await event.answer()
            
        except Exception as e:
            logger.error(f"Ошибка в callback обработчике: {e}")
            await event.answer("❌ Произошла ошибка", alert=True)
    
    async def run(self):
        """Основной метод запуска"""
        try:
            await self.start()
        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            raise

# Обработчик пересланных сообщений для добавления чатов
async def forwarded_message_handler(event):
    """Обработка пересланных сообщений для добавления чатов"""
    if event.message.sender_id == OWNER_ID and event.message.is_reply:
        replied_msg = await event.get_reply_message()
        
        if replied_msg and replied_msg.text:
            # Проверяем, был ли это запрос на добавление чата
            if "добавление чата" in replied_msg.text.lower() or "перешлите мне" in replied_msg.text.lower():
                chat_id = event.chat_id
                
                try:
                    chat = await event.get_chat()
                    chat_title = getattr(chat, 'title', 'Личный чат')
                    
                    # Добавляем чат в конфигурацию
                    bot_instance = AutoDeleteBot()
                    await bot_instance.add_chat_to_list(event, chat_id, chat_title)
                except Exception as e:
                    logger.error(f"Ошибка при добавлении чата: {e}")
                    await event.reply(f"❌ Ошибка: {str(e)}")

# Запуск бота
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Бот для автоматического удаления сообщений v2.0")
    print("=" * 50)
    print(f"👤 Владелец: {OWNER_ID}")
    print(f"📁 Файл конфигурации: {CONFIG_FILE}")
    print("=" * 50)
    print("⚙️  Возможности:")
    print("• 📋 Управление через кнопки")
    print("• 👤 Добавление по ID/username/ссылке")
    print("• 💬 Выбор конкретных чатов")
    print("• 🔔 Настройка уведомлений")
    print("=" * 50)
    
    bot = AutoDeleteBot()
    
    # Добавляем обработчик пересланных сообщений
    bot.client.add_event_handler(forwarded_message_handler, events.NewMessage(incoming=True))
    
    # Запускаем бота
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    finally:
        loop.close()
