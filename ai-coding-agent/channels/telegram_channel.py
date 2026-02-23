import asyncio
import logging
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from agent.agent import Agent
from agent.events import AgentEventType
from config.config import Config
from agent.session import Session

logger = logging.getLogger(__name__)

class TelegramChannel:
    def __init__(self, config: Config, session: Session):
        self.config = config
        self.session = session
        self.bot_token = config.telegram_bot_token
        self.authorized_chat_id = config.telegram_authorized_chat_id
        self._pending_input_future: asyncio.Future | None = None
        self._pending_input_future: asyncio.Future | None = None
        
        if not self.bot_token or not self.authorized_chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_AUTHORIZED_CHAT_ID is missing in environment variables.")

        # We will still instantiate a TUI to handle tool confirmations 
        # but output will be piped to Telegram instead
        self.app = (
            Application.builder()
            .token(self.bot_token)
            .connect_timeout(30.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .pool_timeout(30.0)
            .build()
        )
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def _is_authorized(self, update: Update) -> bool:
        if str(update.effective_chat.id) != str(self.authorized_chat_id):
            logger.warning(f"Unauthorized access attempt from Chat ID: {update.effective_chat.id}")
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._is_authorized(update):
            return
            
        await update.message.reply_text(
            f"🤖 *AI Coding Agent Connected*\n"
            f"Model: `{self.config.model_name}`\n"
            f"Working directory: `{self.config.cwd}`\n\n"
            f"Send me an instruction to begin.",
            parse_mode="Markdown"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._is_authorized(update):
            return
            
        user_message = update.message.text
        
        if self._pending_input_future and not self._pending_input_future.done():
            self._pending_input_future.set_result(user_message)
            return
            
        async def telegram_ask_user(question: str) -> str:
            await update.message.reply_text(f"🤖 *Agent asks:* {question}", parse_mode="Markdown")
            self._pending_input_future = asyncio.Future()
            answer = await self._pending_input_future
            self._pending_input_future = None
            return answer

        self.session.ask_user_callback = telegram_ask_user
        
        status_msg = await update.message.reply_text("🤔 *Thinking...*", parse_mode="Markdown")

        async with Agent(self.config, session=self.session) as agent:
            assistant_response = ""
            current_tool = None
            
            # Agent async generator loop
            async for event in agent.run(user_message):
                if event.type == AgentEventType.TEXT_DELTA:
                    assistant_response += event.data.get("content", "")
                
                elif event.type == AgentEventType.TEXT_COMPLETE:
                    assistant_response = event.data.get("content", "")
                    
                elif event.type == AgentEventType.TOOL_CALL_START:
                    tool_name = event.data.get("name", "unknown")
                    await status_msg.edit_text(f"🔧 *Running tool:* `{tool_name}`", parse_mode="Markdown")
                    
                elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                    tool_name = event.data.get("name", "unknown")
                    success = event.data.get("success", False)
                    icon = "✅" if success else "❌"
                    await update.message.reply_text(f"{icon} *Tool finished:* `{tool_name}`", parse_mode="Markdown")
                    await status_msg.edit_text("🤔 *Thinking...*", parse_mode="Markdown")
                    
                elif event.type == AgentEventType.AGENT_ERROR:
                    error = event.data.get("error", "Unknown error")
                    await status_msg.edit_text(f"❌ *Agent Error:*\n`{error}`", parse_mode="Markdown")
                    return

            # Final response
            if assistant_response:
                # Telegram has a 4096 character limit per message
                if len(assistant_response) > 4000:
                    for i in range(0, len(assistant_response), 4000):
                        await update.message.reply_text(assistant_response[i:i+4000])
                else:
                    await status_msg.edit_text(assistant_response, parse_mode="Markdown")

    async def start(self):
        logger.info("Initializing Telegram Bot...")
        await self.app.initialize()
        await self.app.start()
        logger.info("Starting Telegram Polling in background...")
        await self.app.updater.start_polling()

    async def stop(self):
        logger.info("Stopping Telegram Bot...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
