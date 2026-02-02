import asyncio
import json
import os
import re
from datetime import datetime
from telethon import TelegramClient, events, Button, functions, types
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
import logging

# Конфигурация
API_ID = 29238968
API_HASH = '693fa412a819664c59ec5f1989755842'
BOT_TOKEN = '8274874473:AAGQTVHI3CkwzotIuqiS6M2Whptcp-EpTnY'
OWNER_ID = 8524326478
SESSION_NAME = '+380962151936.session'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Файлы для хранения данных
CONFIG_FILE = 'bot_config_v2.json'
CHATS_CACHE_FILE = 'chats_cache.json'

class AdvancedAutoDeleteBot:
    def __init__(self):
        self.client = TelegramClient(
            SESSION_NAME,
            API_ID,
            API_HASH,
            device_model="AutoDelete Bot",
            system_version="4.0",
            app_version="2.0"
        )
        self.bot = None
        self.config = self.load_config()
        self.chats_cache = self.load_chats_cache()
        self.active_monitoring = True
        self.deletion_stats = {
            'total_deleted': 0,
            'deleted_today': 0,
            'by_user': {},
            'by_chat': {}
        }
        
    def load_config(self):
        """Загрузка конфигурации"""
        default_config = {
            'blacklist': [],
            'enabled_chats': [],
            'enabled_for_all': True,
            'delete_notifications': True,
            'monitor_all_chats': True,
            'auto_add_new_chats': False,
            'delete_delay': 0,
            'advanced_mode': True
        }
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
        
        return default_config
    
    def load_chats_cache(self):
        """Загрузка кэша чатов"""
        default_cache = {
            'chats': {},
            'last_update': None
        }
        
        try:
            if os.path.exists(CHATS_CACHE_FILE):
                with open(CHATS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша чатов: {e}")
        
        return default_cache
    
    def save_config(self):
        """Сохранение конфигурации"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    def save_chats_cache(self):
        """Сохранение кэша чатов"""
        try:
            self.chats_cache['last_update'] = datetime.now().isoformat()
            with open(CHATS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.chats_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша чатов: {e}")
    
    async def get_all_chats(self):
        """Получение всех доступных чатов"""
        chats = []
        
        try:
            result = await self.bot(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))
            
            for dialog in result.dialogs:
                entity = dialog.entity
                if hasattr(entity, 'id'):
                    chats.append({
                        'id': entity.id,
                        'title': getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown')),
                        'type': 'channel' if hasattr(entity, 'broadcast') else 'group' if hasattr(entity, 'megagroup') else 'private'
                    })
            
            # Сохраняем в кэш
            for chat in chats:
                chat_id_str = str(chat['id'])
                if chat_id_str not in self.chats_cache['chats']:
                    self.chats_cache['chats'][chat_id_str] = chat
            
            self.save_chats_cache()
            
        except Exception as e:
            logger.error(f"Ошибка получения чатов: {e}")
        
        return chats
    
    async def resolve_user_input(self, user_input):
        """Разрешение ввода пользователя в информацию о пользователе"""
        try:
            # Убираем пробелы и лишние символы
            user_input = user_input.strip()
            
            # Если это ID
            if user_input.isdigit() or (user_input.startswith('-') and user_input[1:].isdigit()):
                user_id = int(user_input)
                try:
                    user = await self.bot.get_entity(user_id)
                    return self.format_user_info(user)
                except:
                    return {'id': user_id, 'username': None, 'resolved': False}
            
            # Если это @username
            elif user_input.startswith('@'):
                username = user_input[1:]
                user = await self.bot.get_entity(username)
                return self.format_user_info(user)
            
            # Если это ссылка t.me/
            elif 't.me/' in user_input:
                username = user_input.split('t.me/')[-1].split('/')[0].split('?')[0]
                if username.startswith('@'):
                    username = username[1:]
                user = await self.bot.get_entity(username)
                return self.format_user_info(user)
            
            # Если это пересланное сообщение
            elif user_input == 'forwarded':
                return None
            
            # Если это обычный текст, пробуем как username
            else:
                try:
                    if not user_input.startswith('@'):
                        user_input = '@' + user_input
                    user = await self.bot.get_entity(user_input)
                    return self.format_user_info(user)
                except:
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка разрешения пользователя {user_input}: {e}")
            return None
    
    def format_user_info(self, user):
        """Форматирование информации о пользователе"""
        return {
            'id': user.id,
            'username': getattr(user, 'username', None),
            'first_name': getattr(user, 'first_name', ''),
            'last_name': getattr(user, 'last_name', ''),
            'resolved': True,
            'added_date': datetime.now().isoformat()
        }
    
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
    
    async def monitor_all_chats(self):
        """Мониторинг всех чатов для удаления сообщений"""
        logger.info("Запуск мониторинга всех чатов...")
        
        @self.bot.on(events.NewMessage())
        async def global_message_handler(event):
            """Глобальный обработчик сообщений для всех чатов"""
            if not self.active_monitoring:
                return
            
            try:
                # Пропускаем служебные сообщения
                if not event.message.message:
                    return
                
                # Пропускаем собственные сообщения бота
                if event.message.sender_id == (await self.bot.get_me()).id:
                    return
                
                # Проверяем, является ли сообщение реплаем
                if event.message.reply_to_msg_id:
                    await self.handle_reply_message(event)
                
                # Также обрабатываем команды от владельца
                if event.message.sender_id == OWNER_ID:
                    await self.handle_owner_command(event)
                    
            except Exception as e:
                logger.error(f"Ошибка в глобальном обработчике: {e}")
        
        logger.info("Глобальный мониторинг активен!")
    
    async def handle_reply_message(self, event):
        """Обработка реплай-сообщений"""
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
                logger.info(f"✅ Удалено сообщение {replied_msg.id} в чате {chat_id} от пользователя {sender_id} ({sender_username})")
                
                # Отправляем уведомление владельцу
                if self.config['delete_notifications']:
                    user_display = self.format_user_display(user_info)
                    chat_info = await self.get_chat_info(chat_id)
                    
                    notification = (
                        f"🗑️ **Сообщение удалено!**\n\n"
                        f"👤 **Отправитель реплая:** {user_display}\n"
                        f"🆔 **ID отправителя:** `{sender_id}`\n"
                        f"💬 **Чат:** {chat_info}\n"
                        f"🆔 **ID чата:** `{chat_id}`\n"
                        f"📝 **ID сообщения:** `{replied_msg.id}`\n"
                        f"⏰ **Время:** {datetime.now().strftime('%H:%M:%S')}\n"
                        f"📊 **Всего удалено:** {self.deletion_stats['total_deleted']}"
                    )
                    
                    await self.bot.send_message(OWNER_ID, notification, parse_mode='md')
                    
            except Exception as e:
                error_msg = f"❌ Ошибка при удалении сообщения: {str(e)}"
                logger.error(error_msg)
                
                if "MESSAGE_DELETE_FORBIDDEN" in str(e):
                    error_msg += "\n\n⚠️ У бота нет прав на удаление сообщений в этом чате!"
                
                await self.bot.send_message(OWNER_ID, error_msg)
                
        except Exception as e:
            logger.error(f"Ошибка обработки реплая: {e}")
    
    async def get_chat_info(self, chat_id):
        """Получение информации о чате"""
        try:
            chat = await self.bot.get_entity(chat_id)
            if hasattr(chat, 'title'):
                return f"{chat.title} (ID: {chat_id})"
            elif hasattr(chat, 'first_name'):
                return f"{chat.first_name} {getattr(chat, 'last_name', '')} (ID: {chat_id})"
        except:
            pass
        
        return f"Чат ID: {chat_id}"
    
    def format_user_display(self, user_info):
        """Форматирование отображения пользователя"""
        if not user_info:
            return "Неизвестный пользователь"
        
        parts = []
        if user_info.get('first_name'):
            parts.append(user_info['first_name'])
        if user_info.get('last_name'):
            parts.append(user_info['last_name'])
        
        display = ' '.join(parts) if parts else f"Пользователь {user_info['id']}"
        
        if user_info.get('username'):
            display += f" (@{user_info['username']})"
        
        return display
    
    async def start(self):
        """Запуск бота"""
        logger.info("Запуск продвинутого бота для удаления сообщений...")
        
        await self.client.start(bot_token=BOT_TOKEN)
        self.bot = self.client
        
        me = await self.bot.get_me()
        logger.info(f"Бот запущен как @{me.username}")
        logger.info(f"ID владельца: {OWNER_ID}")
        
        # Запускаем мониторинг всех чатов
        await self.monitor_all_chats()
        
        # Регистрируем обработчики команд
        self.register_command_handlers()
        
        # Регистрируем обработчик callback запросов
        self.register_callback_handler()
        
        # Отправляем приветственное сообщение
        await self.send_welcome_message()
        
        logger.info("Бот полностью запущен и готов к работе!")
        logger.info(f"Черный список: {len(self.config['blacklist'])} пользователей")
        logger.info(f"Мониторинг чатов: {'Все чаты' if self.config['enabled_for_all'] else f'{len(self.config['enabled_chats'])} чатов'}")
        
        await self.bot.run_until_disconnected()
    
    async def send_welcome_message(self):
        """Отправка приветственного сообщения"""
        welcome_text = (
            f"🤖 **Продвинутый бот для удаления сообщений запущен!**\n\n"
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
            await self.bot.send_message(OWNER_ID, welcome_text, parse_mode='md')
        except:
            pass
    
    def register_command_handlers(self):
        """Регистрация обработчиков команд"""
        
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_main_menu(event)
        
        @self.bot.on(events.NewMessage(pattern='/menu'))
        async def menu_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_main_menu(event)
        
        @self.bot.on(events.NewMessage(pattern='/add'))
        async def add_handler(event):
            if event.sender_id == OWNER_ID:
                args = event.message.text.split()
                if len(args) > 1:
                    user_input = ' '.join(args[1:])
                    await self.add_user_command(event, user_input)
                else:
                    await self.show_add_user_menu(event)
        
        @self.bot.on(events.NewMessage(pattern='/remove'))
        async def remove_handler(event):
            if event.sender_id == OWNER_ID:
                args = event.message.text.split()
                if len(args) > 1:
                    user_input = ' '.join(args[1:])
                    await self.remove_user_command(event, user_input)
                else:
                    await self.show_remove_user_menu(event)
        
        @self.bot.on(events.NewMessage(pattern='/list'))
        async def list_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_blacklist(event)
        
        @self.bot.on(events.NewMessage(pattern='/stats'))
        async def stats_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_stats(event)
        
        @self.bot.on(events.NewMessage(pattern='/chats'))
        async def chats_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_chat_management(event)
        
        @self.bot.on(events.NewMessage(pattern='/help'))
        async def help_handler(event):
            if event.sender_id == OWNER_ID:
                await self.show_help(event)
        
        @self.bot.on(events.NewMessage(pattern='/toggle'))
        async def toggle_handler(event):
            if event.sender_id == OWNER_ID:
                self.active_monitoring = not self.active_monitoring
                status = "✅ Включен" if self.active_monitoring else "⏸️ Приостановлен"
                await event.reply(f"**Мониторинг:** {status}")
        
        @self.bot.on(events.NewMessage(pattern='/broadcast'))
        async def broadcast_handler(event):
            if event.sender_id == OWNER_ID:
                args = event.message.text.split(maxsplit=1)
                if len(args) > 1:
                    message = args[1]
                    await self.broadcast_to_chats(event, message)
        
        @self.bot.on(events.NewMessage(pattern='/clean'))
        async def clean_handler(event):
            if event.sender_id == OWNER_ID:
                args = event.message.text.split()
                if len(args) > 1 and args[1].isdigit():
                    hours = int(args[1])
                    await self.clean_old_messages(event, hours)
        
        @self.bot.on(events.NewMessage)
        async def forwarded_message_handler(event):
            """Обработка пересланных сообщений"""
            if event.sender_id == OWNER_ID and event.message.is_reply:
                replied_msg = await event.get_reply_message()
                if replied_msg and replied_msg.sender_id == (await self.bot.get_me()).id:
                    # Проверяем, было ли это ответом на запрос добавления пользователя
                    if "отправьте мне сообщение от пользователя" in replied_msg.text.lower():
                        forwarded = event.message.forward
                        if forwarded:
                            sender_id = forwarded.sender_id
                            try:
                                user = await self.bot.get_entity(sender_id)
                                await self.add_user_from_forwarded(event, user)
                            except Exception as e:
                                await event.reply(f"❌ Ошибка: {str(e)}")
    
    def register_callback_handler(self):
        """Регистрация обработчика callback запросов"""
        
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            """Обработчик callback запросов"""
            try:
                data = event.data.decode('utf-8')
                
                if data == 'main_menu':
                    await self.show_main_menu(event)
                
                elif data == 'user_mgmt':
                    await self.show_add_user_menu(event)
                
                elif data == 'chat_mgmt':
                    await self.show_chat_management(event)
                
                elif data == 'stats':
                    await self.show_stats(event)
                
                elif data == 'settings':
                    await self.show_settings_menu(event)
                
                elif data == 'quick_add':
                    await event.edit(
                        "➕ **Быстрое добавление пользователя**\n\n"
                        "Отправьте мне:\n"
                        "• @username пользователя\n"
                        "• Или перешлите сообщение от него\n\n"
                        "Или используйте команду:\n"
                        "`/add @username`",
                        buttons=[[Button.inline("↩️ Назад", b"main_menu")]]
                    )
                
                elif data == 'mass_clean':
                    await event.edit(
                        "🗑️ **Массовая очистка**\n\n"
                        "Эта функция позволяет удалить все ваши сообщения в чате.\n\n"
                        "Для использования отправьте команду:\n"
                        "`/clean 24` - удалит сообщения старше 24 часов",
                        buttons=[[Button.inline("↩️ Назад", b"main_menu")]]
                    )
                
                elif data == 'refresh':
                    await self.show_main_menu(event)
                
                elif data == 'help':
                    await self.show_help(event)
                
                elif data == 'refresh_stats':
                    await self.show_stats(event)
                
                elif data == 'detailed_stats':
                    await self.show_detailed_stats(event)
                
                elif data == 'toggle_chat_mode':
                    self.config['enabled_for_all'] = not self.config['enabled_for_all']
                    self.save_config()
                    
                    mode = "🌐 Все чаты" if self.config['enabled_for_all'] else "💬 Только выбранные"
                    await event.answer(f"Режим изменен: {mode}", alert=False)
                    await self.show_chat_management(event)
                
                elif data == 'add_chat_menu':
                    await event.edit(
                        "➕ **Добавление чата**\n\n"
                        "Перешлите мне сообщение из чата или используйте команду:\n"
                        "`/add_chat ID_чата`\n\n"
                        "Чтобы получить ID чата, добавьте бота @getidsbot в нужный чат.",
                        buttons=[[Button.inline("↩️ Назад", b"chat_mgmt")]]
                    )
                
                elif data == 'remove_chat_menu':
                    await self.show_chats_for_removal(event)
                
                elif data == 'list_chats':
                    await self.show_chats_list(event)
                
                elif data == 'refresh_chats':
                    await self.refresh_chats_list(event)
                
                elif data == 'search_username':
                    await event.edit(
                        "🔍 **Поиск по username**\n\n"
                        "Введите username пользователя (например: @username):",
                        buttons=[[Button.inline("↩️ Назад", b"user_mgmt")]]
                    )
                
                elif data == 'list_chats_search':
                    await self.show_chats_for_member_search(event)
                
                elif data.startswith('blacklist_page_'):
                    page = int(data.split('_')[-1])
                    await self.show_blacklist_page(event, page)
                
                elif data == 'remove_user_menu':
                    await self.show_users_for_removal(event)
                
                elif data.startswith('remove_user_'):
                    user_id = int(data.split('_')[-1])
                    await self.remove_user_by_id(event, user_id)
                
                elif data.startswith('remove_chat_'):
                    chat_id = int(data.split('_')[-1])
                    await self.remove_chat_by_id(event, chat_id)
                
                elif data == 'command_examples':
                    await event.edit(
                        "📚 **Примеры команд:**\n\n"
                        "`/add @username` - добавить по username\n"
                        "`/add 123456789` - добавить по ID\n"
                        "`/add https://t.me/username` - добавить по ссылке\n"
                        "`/list` - показать черный список\n"
                        "`/stats` - статистика\n"
                        "`/chats` - управление чатами\n"
                        "`/toggle` - вкл/выкл мониторинг\n\n"
                        "📌 **Совет:** Просто перешлите сообщение от пользователя для быстрого добавления!",
                        buttons=[[Button.inline("↩️ Назад", b"help")]]
                    )
                
                elif data == 'troubleshooting':
                    await event.edit(
                        "⚠️ **Решение проблем:**\n\n"
                        "**1. Бот не удаляет сообщения:**\n"
                        "• Проверьте, что бот администратор в чате\n"
                        "• Убедитесь, что пользователь в черном списке\n"
                        "• Проверьте, включен ли мониторинг (`/toggle`)\n\n"
                        "**2. Не могу добавить пользователя:**\n"
                        "• Проверьте правильность username или ID\n"
                        "• Попробуйте переслать сообщение от пользователя\n\n"
                        "**3. Бот не отвечает:**\n"
                        "• Перезапустите бота\n"
                        "• Проверьте интернет-соединение\n\n"
                        "**4. Уведомления не приходят:**\n"
                        "• Проверьте настройки уведомлений в меню",
                        buttons=[[Button.inline("↩️ Назад", b"help")]]
                    )
                
                await event.answer()
                
            except Exception as e:
                logger.error(f"Ошибка в callback обработчике: {e}")
                await event.answer("❌ Произошла ошибка", alert=True)
    
    async def handle_owner_command(self, event):
        """Обработка команд от владельца"""
        text = event.message.text
        
        if text.startswith('/add_chat'):
            await self.add_chat_command(event)
        elif text.startswith('/remove_chat'):
            await self.remove_chat_command(event)
        elif text.startswith('/mode'):
            await self.toggle_mode_command(event)
    
    async def show_main_menu(self, event):
        """Показать главное меню"""
        menu_text = (
            f"🤖 **Главное меню - Автоудаление сообщений**\n\n"
            f"📊 **Статистика:**\n"
            f"• 👤 Пользователей в черном списке: **{len(self.config['blacklist'])}**\n"
            f"• 💬 Активных чатов: **{len(self.config['enabled_chats'])}**\n"
            f"• 🗑️ Всего удалено: **{self.deletion_stats['total_deleted']}**\n"
            f"• 🗑️ Удалено сегодня: **{self.deletion_stats['deleted_today']}**\n"
            f"• ⚡ Мониторинг: **{'✅ Активен' if self.active_monitoring else '⏸️ Приостановлен'}**\n\n"
            f"🌐 **Режим:** {'Все чаты' if self.config['enabled_for_all'] else 'Только выбранные'}\n\n"
            f"**Выберите действие:**"
        )
        
        buttons = [
            [Button.inline("👤 Управление пользователями", b"user_mgmt"),
             Button.inline("💬 Управление чатами", b"chat_mgmt")],
            [Button.inline("📊 Статистика", b"stats"),
             Button.inline("⚙️ Настройки", b"settings")],
            [Button.inline("➕ Быстрое добавление", b"quick_add"),
             Button.inline("🗑️ Массовая очистка", b"mass_clean")],
            [Button.inline("🔄 Обновить", b"refresh"),
             Button.inline("📋 Помощь", b"help")]
        ]
        
        await event.reply(menu_text, buttons=buttons, parse_mode='md')
    
    async def show_add_user_menu(self, event):
        """Показать меню добавления пользователя"""
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
            [Button.inline("📋 Список чатов для поиска", b"list_chats_search")],
            [Button.inline("🔍 Поиск по username", b"search_username")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(text, buttons=buttons, parse_mode='md')
    
    async def add_user_command(self, event, user_input):
        """Команда добавления пользователя"""
        if not user_input:
            await event.reply("❌ Укажите пользователя для добавления.\nПример: `/add @username`")
            return
        
        # Показываем статус обработки
        status_msg = await event.reply("🔄 Обработка запроса...")
        
        # Получаем информацию о пользователе
        user_info = await self.resolve_user_input(user_input)
        
        if not user_info:
            await status_msg.edit("❌ Не удалось найти пользователя. Проверьте правильность ввода.")
            return
        
        # Проверяем, есть ли уже пользователь в черном списке
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
            f"Теперь при любых реплаях от этого пользователя ваши сообщения будут автоматически удаляться."
        )
        
        logger.info(f"Добавлен пользователь: {user_display} (ID: {user_info['id']})")
    
    async def add_user_from_forwarded(self, event, user):
        """Добавление пользователя из пересланного сообщения"""
        user_info = self.format_user_info(user)
        
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
            f"🆔 ID: `{user_info['id']}`"
        )
        
        logger.info(f"Добавлен пользователь из пересланного: {user_display}")
    
    async def show_blacklist(self, event):
        """Показать черный список"""
        if not self.config['blacklist']:
            await event.reply("📋 **Черный список пуст.**\n\nИспользуйте `/add @username` для добавления пользователей.")
            return
        
        # Разбиваем на страницы по 10 пользователей
        users_per_page = 10
        total_pages = (len(self.config['blacklist']) + users_per_page - 1) // users_per_page
        
        text = f"📋 **Черный список пользователей**\n\n"
        text += f"Всего пользователей: {len(self.config['blacklist'])}\n"
        text += f"Страница 1/{total_pages}\n\n"
        
        for i, user in enumerate(self.config['blacklist'][:users_per_page], 1):
            user_display = self.format_user_display(user)
            text += f"{i}. {user_display}\n"
            text += f"   🆔 `{user['id']}`"
            if user.get('username'):
                text += f" | @{user['username']}"
            text += f"\n   📅 Добавлен: {user.get('added_date', 'Неизвестно')[:10]}\n\n"
        
        buttons = []
        if total_pages > 1:
            buttons.append([Button.inline("▶️ Следующая страница", b"blacklist_page_2")])
        
        buttons.append([
            Button.inline("➖ Удалить пользователя", b"remove_user_menu"),
            Button.inline("↩️ Назад", b"main_menu")
        ])
        
        await event.reply(text, buttons=buttons, parse_mode='md')
    
    async def show_stats(self, event):
        """Показать статистику"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Формируем топ пользователей
        top_users = sorted(
            self.deletion_stats['by_user'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Формируем топ чатов
        top_chats = sorted(
            self.deletion_stats['by_chat'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        stats_text = (
            f"📊 **Статистика бота**\n\n"
            f"📅 **Дата:** {today}\n"
            f"🕐 **Время работы:** {self.get_uptime()}\n\n"
            f"**Общая статистика:**\n"
            f"• 🗑️ Всего удалено сообщений: **{self.deletion_stats['total_deleted']}**\n"
            f"• 🗑️ Удалено сегодня: **{self.deletion_stats['deleted_today']}**\n"
            f"• 👤 Пользователей в черном списке: **{len(self.config['blacklist'])}**\n"
            f"• 💬 Мониторится чатов: **{'Все' if self.config['enabled_for_all'] else len(self.config['enabled_chats'])}**\n"
            f"• ⚡ Статус мониторинга: **{'✅ Активен' if self.active_monitoring else '⏸️ Приостановлен'}**\n\n"
        )
        
        if top_users:
            stats_text += f"**Топ пользователей по удалениям:**\n"
            for i, (user_id, count) in enumerate(top_users, 1):
                stats_text += f"{i}. Пользователь {user_id}: {count} удалений\n"
            stats_text += "\n"
        
        if top_chats:
            stats_text += f"**Топ чатов по удалениям:**\n"
            for i, (chat_id, count) in enumerate(top_chats, 1):
                stats_text += f"{i}. Чат {chat_id}: {count} удалений\n"
        
        buttons = [
            [Button.inline("🔄 Обновить статистику", b"refresh_stats")],
            [Button.inline("📈 Детальная статистика", b"detailed_stats")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(stats_text, buttons=buttons, parse_mode='md')
    
    def get_uptime(self):
        """Получение времени работы"""
        # В реальном боте здесь нужно хранить время запуска
        return "Неизвестно"
    
    async def show_chat_management(self, event):
        """Показать управление чатами"""
        mode = "🌐 Все чаты" if self.config['enabled_for_all'] else "💬 Только выбранные"
        
        text = (
            f"💬 **Управление чатами**\n\n"
            f"Текущий режим: **{mode}**\n"
            f"Активных чатов: **{len(self.config['enabled_chats'])}**\n\n"
            f"**Доступные действия:**"
        )
        
        buttons = [
            [Button.inline("🌐 Переключить режим", b"toggle_chat_mode")],
            [Button.inline("➕ Добавить чат", b"add_chat_menu")],
            [Button.inline("➖ Удалить чат", b"remove_chat_menu")],
            [Button.inline("📋 Список чатов", b"list_chats")],
            [Button.inline("🔄 Обновить список", b"refresh_chats")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(text, buttons=buttons, parse_mode='md')
    
    async def show_help(self, event):
        """Показать помощь"""
        help_text = """
        🤖 **Помощь по боту автоматического удаления сообщений**\n\n
        **📋 Основные команды:**
        `/menu` - Главное меню
        `/add @username` - Добавить пользователя
        `/remove @username` - Удалить пользователя
        `/list` - Показать черный список
        `/stats` - Статистика бота
        `/chats` - Управление чатами
        `/toggle` - Включить/выключить мониторинг
        `/help` - Эта справка\n\n
        **👤 Добавление пользователей:**
        1. **По команде:** `/add @username` или `/add 123456789`
        2. **Пересылкой:** Просто перешлите любое сообщение от пользователя боту
        3. **По ссылке:** `/add https://t.me/username`\n\n
        **💬 Управление чатами:**
        • **Режим "Все чаты":** Бот мониторит все чаты, где он есть
        • **Режим "Выбранные":** Только указанные вами чаты
        • Добавляйте чаты через меню управления\n\n
        **⚡ Как это работает:**
        1. Бот постоянно мониторит все сообщения во всех чатах
        2. Когда пользователь из черного списка отвечает (реплаит) на ВАШЕ сообщение
        3. Бот МОМЕНТАЛЬНО удаляет ваше сообщение, на которое был сделан реплай
        4. Вы получаете уведомление об удалении\n\n
        **🔧 Дополнительные функции:**
        • Массовое добавление пользователей
        • Статистика удалений
        • Настройка уведомлений
        • Работа в фоновом режиме
        """
        
        buttons = [
            [Button.inline("📚 Примеры команд", b"command_examples")],
            [Button.inline("⚠️ Решение проблем", b"troubleshooting")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.reply(help_text, buttons=buttons, parse_mode='md')
    
    async def add_chat_command(self, event):
        """Команда добавления чата"""
        args = event.message.text.split()
        if len(args) > 1:
            chat_input = ' '.join(args[1:])
            # Здесь будет логика добавления чата по введенным данным
            await event.reply(f"Добавление чата: {chat_input}\n\nЭта функция в разработке.")
        else:
            # Если аргументов нет, просим переслать сообщение из чата
            await event.reply(
                "💬 **Добавление чата**\n\n"
                "Перешлите мне любое сообщение из чата, который хотите добавить.",
                buttons=[[Button.inline("↩️ Назад", b"chat_mgmt")]]
            )
    
    async def remove_chat_command(self, event):
        """Команда удаления чата"""
        await event.reply(
            "Для удаления чата используйте меню управления чатами.",
            buttons=[[Button.inline("💬 Управление чатами", b"chat_mgmt")]]
        )
    
    async def toggle_mode_command(self, event):
        """Команда переключения режима"""
        self.config['enabled_for_all'] = not self.config['enabled_for_all']
        self.save_config()
        
        mode = "🌐 Все чаты" if self.config['enabled_for_all'] else "💬 Только выбранные"
        await event.reply(f"✅ Режим изменен: **{mode}**", parse_mode='md')
    
    async def broadcast_to_chats(self, event, message):
        """Рассылка сообщения по чатам"""
        if not message:
            await event.reply("❌ Укажите сообщение для рассылки.")
            return
        
        status_msg = await event.reply("🔄 Начинаю рассылку...")
        
        chats_to_broadcast = []
        if self.config['enabled_for_all']:
            # Получаем все чаты
            chats = await self.get_all_chats()
            chats_to_broadcast = chats
        else:
            # Только выбранные чаты
            for chat_id in self.config['enabled_chats']:
                try:
                    chat = await self.bot.get_entity(chat_id)
                    chats_to_broadcast.append({
                        'id': chat_id,
                        'title': getattr(chat, 'title', f'Чат {chat_id}')
                    })
                except:
                    continue
        
        success = 0
        failed = 0
        
        for chat in chats_to_broadcast:
            try:
                await self.bot.send_message(chat['id'], f"📢 {message}")
                success += 1
                await asyncio.sleep(0.5)  # Задержка между отправками
            except Exception as e:
                logger.error(f"Ошибка отправки в чат {chat['id']}: {e}")
                failed += 1
        
        await status_msg.edit(
            f"✅ **Рассылка завершена!**\n\n"
            f"📤 Отправлено успешно: {success}\n"
            f"❌ Не отправлено: {failed}\n"
            f"💬 Всего чатов: {len(chats_to_broadcast)}"
        )
    
    async def clean_old_messages(self, event, hours):
        """Очистка старых сообщений"""
        await event.reply(
            f"🔄 Очистка сообщений старше {hours} часов...\n\n"
            f"Эта функция в разработке."
        )
    
    async def show_settings_menu(self, event):
        """Показать меню настроек"""
        notifications = "✅ Включены" if self.config['delete_notifications'] else "❌ Выключены"
        auto_add = "✅ Включено" if self.config['auto_add_new_chats'] else "❌ Выключено"
        monitoring = "✅ Активен" if self.active_monitoring else "⏸️ Приостановлен"
        
        text = (
            f"⚙️ **Настройки бота**\n\n"
            f"**Текущие настройки:**\n"
            f"• 🔔 Уведомления: {notifications}\n"
            f"• ➕ Автодобавление чатов: {auto_add}\n"
            f"• ⚡ Мониторинг: {monitoring}\n"
            f"• ⏱️ Задержка удаления: {self.config['delete_delay']} сек.\n\n"
            f"**Выберите настройку для изменения:**"
        )
        
        buttons = [
            [Button.inline("🔔 Уведомления", b"toggle_notifications"),
             Button.inline("➕ Автодобавление", b"toggle_auto_add")],
            [Button.inline("⚡ Мониторинг", b"toggle_monitoring"),
             Button.inline("⏱️ Задержка", b"set_delay")],
            [Button.inline("🗑️ Сброс статистики", b"reset_stats"),
             Button.inline("🔄 Сброс настроек", b"reset_settings")],
            [Button.inline("💾 Экспорт данных", b"export_data"),
             Button.inline("📥 Импорт данных", b"import_data")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def show_detailed_stats(self, event):
        """Показать детальную статистику"""
        today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Получаем детальную статистику по пользователям
        users_stats = []
        for user_id, count in self.deletion_stats['by_user'].items():
            user_info = None
            for user in self.config['blacklist']:
                if str(user['id']) == user_id:
                    user_info = user
                    break
            
            if user_info:
                display = self.format_user_display(user_info)
                users_stats.append((display, count))
            else:
                users_stats.append((f"Пользователь {user_id}", count))
        
        # Сортируем по количеству удалений
        users_stats.sort(key=lambda x: x[1], reverse=True)
        
        text = f"📈 **Детальная статистика**\n\n"
        text += f"📅 **Обновлено:** {today}\n\n"
        
        if users_stats:
            text += "**Статистика по пользователям:**\n"
            for i, (user_display, count) in enumerate(users_stats[:10], 1):
                text += f"{i}. {user_display}: {count} удалений\n"
            text += "\n"
        
        # Статистика по чатам
        chats_stats = []
        for chat_id, count in self.deletion_stats['by_chat'].items():
            try:
                chat = await self.bot.get_entity(int(chat_id))
                chat_name = getattr(chat, 'title', f'Чат {chat_id}')
                chats_stats.append((chat_name, count))
            except:
                chats_stats.append((f'Чат {chat_id}', count))
        
        chats_stats.sort(key=lambda x: x[1], reverse=True)
        
        if chats_stats:
            text += "**Статистика по чатам:**\n"
            for i, (chat_name, count) in enumerate(chats_stats[:10], 1):
                text += f"{i}. {chat_name}: {count} удалений\n"
        
        buttons = [
            [Button.inline("📊 Общая статистика", b"stats")],
            [Button.inline("↩️ Назад", b"main_menu")]
        ]
        
        await event.edit(text, buttons=buttons)
    
    async def show_chats_for_removal(self, event):
        """Показать чаты для удаления"""
        if not self.config['enabled_chats']:
            await event.edit("📋 **Список чатов пуст.**", buttons=[[Button.inline("↩️ Назад", b"chat_mgmt")]])
            return
        
        text = "💬 **Выберите чат для удаления:**\n\n"
        buttons = []
        
        for chat_id in self.config['enabled_chats']:
            try:
                chat = await self.bot.get_entity(chat_id)
                chat_title = getattr(chat, 'title', f'Чат {chat_id}')[:30]
            except:
                chat_title = f'Чат {chat_id}'[:30]
            
            buttons.append([Button.inline(f"❌ {chat_title}", f"remove_chat_{chat_id}")])
        
        buttons.append([Button.inline("↩️ Назад", b"chat_mgmt")])
        
        await event.edit(text, buttons=buttons)
    
    async def show_users_for_removal(self, event):
        """Показать пользователей для удаления"""
        if not self.config['blacklist']:
            await event.edit("📋 **Черный список пуст.**", buttons=[[Button.inline("↩️ Назад", b"user_mgmt")]])
            return
        
        text = "👤 **Выберите пользователя для удаления:**\n\n"
        buttons = []
        
        for user in self.config['blacklist']:
            user_display = self.format_user_display(user)[:30]
            buttons.append([Button.inline(f"❌ {user_display}", f"remove_user_{user['id']}")])
        
        buttons.append([Button.inline("↩️ Назад", b"user_mgmt")])
        
        await event.edit(text, buttons=buttons)
    
    async def remove_user_by_id(self, event, user_id):
        """Удалить пользователя по ID"""
        for i, user in enumerate(self.config['blacklist']):
            if user['id'] == user_id:
                removed_user = self.config['blacklist'].pop(i)
                self.save_config()
                
                user_display = self.format_user_display(removed_user)
                await event.edit(f"✅ **Пользователь удален:**\n{user_display}")
                
                # Ждем 2 секунды и возвращаемся в меню
                await asyncio.sleep(2)
                await self.show_users_for_removal(event)
                return
        
        await event.answer("❌ Пользователь не найден", alert=True)
    
    async def remove_chat_by_id(self, event, chat_id):
        """Удалить чат по ID"""
        if chat_id in self.config['enabled_chats']:
            self.config['enabled_chats'].remove(chat_id)
            self.save_config()
            
            try:
                chat = await self.bot.get_entity(chat_id)
                chat_title = getattr(chat, 'title', f'Чат {chat_id}')
            except:
                chat_title = f'Чат {chat_id}'
            
            await event.edit(f"✅ **Чат удален:**\n{chat_title}")
            
            await asyncio.sleep(2)
            await self.show_chats_for_removal(event)
        else:
            await event.answer("❌ Чат не найден", alert=True)
    
    async def show_chats_list(self, event):
        """Показать список чатов"""
        chats = await self.get_all_chats()
        
        if not chats:
            await event.edit("📋 **Чаты не найдены.**", buttons=[[Button.inline("↩️ Назад", b"chat_mgmt")]])
            return
        
        text = "💬 **Доступные чаты:**\n\n"
        
        for i, chat in enumerate(chats[:20], 1):
            text += f"{i}. {chat['title']}\n"
            text += f"   🆔 `{chat['id']}` | 📁 {chat['type']}\n"
            
            # Показываем, включен ли мониторинг
            if chat['id'] in self.config['enabled_chats']:
                text += "   ✅ Мониторится\n"
            elif self.config['enabled_for_all']:
                text += "   🌐 Мониторится (все чаты)\n"
            else:
                text += "   ❌ Не мониторится\n"
            
            text += "\n"
        
        if len(chats) > 20:
            text += f"\n... и еще {len(chats) - 20} чатов"
        
        buttons = [
            [Button.inline("🔄 Обновить список", b"refresh_chats")],
            [Button.inline("↩️ Назад", b"chat_mgmt")]
        ]
        
        await event.edit(text, buttons=buttons, parse_mode='md')
    
    async def refresh_chats_list(self, event):
        """Обновить список чатов"""
        await event.answer("🔄 Обновление списка чатов...", alert=False)
        await self.show_chats_list(event)
    
    async def show_chats_for_member_search(self, event):
        """Показать чаты для поиска участников"""
        chats = await self.get_all_chats()
        
        if not chats:
            await event.edit("📋 **Чаты не найдены.**", buttons=[[Button.inline("↩️ Назад", b"user_mgmt")]])
            return
        
        text = "📋 **Выберите чат для просмотра участников:**\n\n"
        buttons = []
        
        for chat in chats[:10]:
            button_text = f"👥 {chat['title'][:25]}"
            buttons.append([Button.inline(button_text, f"view_members_{chat['id']}")])
        
        buttons.append([Button.inline("↩️ Назад", b"user_mgmt")])
        
        await event.edit(text, buttons=buttons)
    
    async def show_blacklist_page(self, event, page):
        """Показать определенную страницу черного списка"""
        users_per_page = 10
        start_idx = (page - 1) * users_per_page
        end_idx = start_idx + users_per_page
        
        total_pages = (len(self.config['blacklist']) + users_per_page - 1) // users_per_page
        
        text = f"📋 **Черный список пользователей**\n\n"
        text += f"Всего пользователей: {len(self.config['blacklist'])}\n"
        text += f"Страница {page}/{total_pages}\n\n"
        
        for i, user in enumerate(self.config['blacklist'][start_idx:end_idx], start_idx + 1):
            user_display = self.format_user_display(user)
            text += f"{i}. {user_display}\n"
            text += f"   🆔 `{user['id']}`"
            if user.get('username'):
                text += f" | @{user['username']}"
            text += f"\n   📅 Добавлен: {user.get('added_date', 'Неизвестно')[:10]}\n\n"
        
        buttons = []
        
        # Кнопки навигации
        nav_buttons = []
        if page > 1:
            nav_buttons.append(Button.inline("◀️ Назад", f"blacklist_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(Button.inline("▶️ Вперед", f"blacklist_page_{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([
            Button.inline("➖ Удалить пользователя", b"remove_user_menu"),
            Button.inline("↩️ Главное меню", b"main_menu")
        ])
        
        await event.edit(text, buttons=buttons, parse_mode='md')
    
    async def run(self):
        """Основной метод запуска"""
        try:
            await self.start()
        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем")
            print("\n👋 Бот остановлен")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            print(f"❌ Критическая ошибка: {e}")
            raise

# Запуск бота
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 ПРОДВИНУТЫЙ БОТ ДЛЯ АВТОМАТИЧЕСКОГО УДАЛЕНИЯ СООБЩЕНИЙ")
    print("=" * 60)
    print(f"👤 Владелец: {OWNER_ID}")
    print(f"🔑 Токен бота: {BOT_TOKEN[:15]}...")
    print(f"💾 Файл конфигурации: {CONFIG_FILE}")
    print(f"💾 Файл кэша чатов: {CHATS_CACHE_FILE}")
    print("=" * 60)
    print("⚡ ВОЗМОЖНОСТИ БОТА:")
    print("• 🌐 МОНИТОРИНГ ВСЕХ ЧАТОВ - работает везде, где есть бот")
    print("• ⚡ МГНОВЕННОЕ УДАЛЕНИЕ - как только пользователь отвечает")
    print("• 👤 ПОДДЕРЖКА МНОГИХ ПОЛЬЗОВАТЕЛЕЙ - неограниченное количество")
    print("• 🔍 РАБОТА ПО USERNAME - добавляйте по @username")
    print("• 📊 ПОДРОБНАЯ СТАТИСТИКА - сколько и кого удалил")
    print("• 📱 ИНТЕРАКТИВНОЕ МЕНЮ - удобные кнопки управления")
    print("• 💬 УПРАВЛЕНИЕ ЧАТАМИ - выбор, где мониторить")
    print("• 🔔 УВЕДОМЛЕНИЯ - моментальные оповещения об удалениях")
    print("=" * 60)
    print("🚀 Запуск бота...")
    
    bot = AdvancedAutoDeleteBot()
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    finally:
        loop.close()
