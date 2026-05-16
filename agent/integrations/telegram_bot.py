"""Telegram Bot integration for Agent framework.

Implements a polling-based Telegram Bot that bridges Telegram messages
to the Agent framework. Uses httpx directly (no python-telegram-bot dependency).

Features:
- TelegramBot: Low-level Bot API wrapper (send_message, get_updates, long polling)
- TelegramAgentBridge: Connects Telegram Bot to Agent with session isolation
- User whitelist for access control
- Rate limiting per user
- Auto-splitting long messages (Telegram 4096 char limit)
- Commands: /start, /help, /clear, /cost

Usage:
    export TELEGRAM_BOT_TOKEN=xxx
    export OPENAI_API_KEY=xxx
    agent-telegram
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

# Telegram message length limit
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Default rate limit: max messages per minute per user
DEFAULT_RATE_LIMIT = 20
DEFAULT_RATE_WINDOW = 60  # seconds


@dataclass
class RateLimiter:
    """Simple sliding-window rate limiter per user."""

    max_requests: int = DEFAULT_RATE_LIMIT
    window_seconds: float = DEFAULT_RATE_WINDOW
    _requests: dict[int, list[float]] = field(default_factory=lambda: defaultdict(list))

    def is_allowed(self, user_id: int) -> bool:
        """Check if a user is allowed to make a request."""
        now = time.time()
        # Clean old entries
        self._requests[user_id] = [
            t for t in self._requests[user_id] if now - t < self.window_seconds
        ]
        if len(self._requests[user_id]) >= self.max_requests:
            return False
        self._requests[user_id].append(now)
        return True

    def remaining(self, user_id: int) -> int:
        """Get remaining requests for a user in the current window."""
        now = time.time()
        self._requests[user_id] = [
            t for t in self._requests[user_id] if now - t < self.window_seconds
        ]
        return max(0, self.max_requests - len(self._requests[user_id]))


def split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit.

    Tries to split at newlines first, then at spaces, then hard-cuts.
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to find a good split point
        split_at = max_length

        # Try splitting at last newline within limit
        newline_pos = remaining.rfind("\n", 0, max_length)
        if newline_pos > max_length // 2:
            split_at = newline_pos + 1
        else:
            # Try splitting at last space within limit
            space_pos = remaining.rfind(" ", 0, max_length)
            if space_pos > max_length // 2:
                split_at = space_pos + 1

        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    return chunks


class TelegramBot:
    """Low-level Telegram Bot API client using httpx.

    Handles sending messages and receiving updates via long polling.
    """

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(
        self,
        token: str,
        allowed_users: Optional[list[int]] = None,
        timeout: float = 30.0,
    ):
        """Initialize Telegram Bot.

        Args:
            token: Telegram Bot API token from @BotFather.
            allowed_users: Optional list of allowed Telegram user IDs.
                          If None, all users are allowed.
            timeout: HTTP request timeout in seconds.
        """
        self.token = token
        self.allowed_users = set(allowed_users) if allowed_users else None
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout + 10)
        return self._client

    def _url(self, method: str) -> str:
        """Build API URL for a given method."""
        return self.BASE_URL.format(token=self.token, method=method)

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if a user is in the whitelist."""
        if self.allowed_users is None:
            return True
        return user_id in self.allowed_users

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> list[dict]:
        """Send a message to a chat. Auto-splits long messages.

        Args:
            chat_id: Target chat ID.
            text: Message text.
            parse_mode: Optional parse mode (Markdown, HTML).

        Returns:
            List of sent message responses.
        """
        chunks = split_message(text)
        results = []

        for chunk in chunks:
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            payload.update(kwargs)

            try:
                response = await self.client.post(self._url("sendMessage"), json=payload)
                response.raise_for_status()
                result = response.json()
                if not result.get("ok"):
                    logger.error("Telegram API error: %s", result.get("description"))
                results.append(result)
            except httpx.HTTPError as e:
                logger.error("Failed to send message to chat %d: %s", chat_id, e)
                results.append({"ok": False, "error": str(e)})

            # Small delay between chunks to avoid rate limiting
            if len(chunks) > 1:
                await asyncio.sleep(0.3)

        return results

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 30,
    ) -> list[dict]:
        """Get new updates via long polling.

        Args:
            offset: Identifier of the first update to be returned.
            limit: Maximum number of updates to retrieve.
            timeout: Long polling timeout in seconds.

        Returns:
            List of update objects.
        """
        payload: dict[str, Any] = {
            "limit": limit,
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset

        try:
            response = await self.client.post(
                self._url("getUpdates"),
                json=payload,
                timeout=self.timeout + timeout,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                return result.get("result", [])
            else:
                logger.error("getUpdates error: %s", result.get("description"))
                return []
        except httpx.HTTPError as e:
            logger.error("Failed to get updates: %s", e)
            return []

    async def start_polling(
        self,
        callback: Callable[[dict], Any],
    ) -> None:
        """Start the polling loop.

        Args:
            callback: Async function to call for each new message update.
        """
        self._running = True
        offset: Optional[int] = None
        logger.info("Telegram Bot polling started")

        while self._running:
            try:
                updates = await self.get_updates(offset=offset)
                for update in updates:
                    offset = update["update_id"] + 1
                    # Process in background to not block polling
                    asyncio.create_task(self._safe_callback(callback, update))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Polling error: %s", e)
                await asyncio.sleep(5)

        logger.info("Telegram Bot polling stopped")

    async def _safe_callback(self, callback: Callable, update: dict) -> None:
        """Safely execute callback, catching exceptions."""
        try:
            await callback(update)
        except Exception as e:
            logger.error("Error processing update %s: %s", update.get("update_id"), e)

    async def stop(self) -> None:
        """Stop the polling loop and close the HTTP client."""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("Telegram Bot stopped")

    async def get_me(self) -> Optional[dict]:
        """Get bot info to verify token."""
        try:
            response = await self.client.post(self._url("getMe"))
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                return result.get("result")
        except httpx.HTTPError as e:
            logger.error("Failed to get bot info: %s", e)
        return None


@dataclass
class UserSession:
    """Represents a user's conversation session."""

    chat_id: int
    user_id: int
    username: Optional[str] = None
    messages: list[dict] = field(default_factory=list)
    total_cost: float = 0.0
    message_count: int = 0
    created_at: float = field(default_factory=time.time)

    def clear(self) -> None:
        """Clear conversation history."""
        self.messages.clear()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.messages.append({"role": role, "content": content})
        self.message_count += 1


class TelegramAgentBridge:
    """Bridge between Telegram Bot and Agent framework.

    Handles:
    - Multi-user session isolation (by chat_id)
    - Command processing (/start, /help, /clear, /cost)
    - Rate limiting
    - Message routing to Agent
    """

    HELP_TEXT = """🤖 *Agent Bot*

Available commands:
/start - Start a new conversation
/help - Show this help message
/clear - Clear conversation history
/cost - Show usage cost for this session

Just send any message to chat with the AI agent!
"""

    def __init__(
        self,
        bot: TelegramBot,
        agent_factory: Callable[[], Any],
        rate_limit: int = DEFAULT_RATE_LIMIT,
        rate_window: float = DEFAULT_RATE_WINDOW,
    ):
        """Initialize the bridge.

        Args:
            bot: TelegramBot instance.
            agent_factory: Callable that creates an Agent instance.
                          Called once per user session.
            rate_limit: Max messages per user per window.
            rate_window: Rate limit window in seconds.
        """
        self.bot = bot
        self.agent_factory = agent_factory
        self.rate_limiter = RateLimiter(
            max_requests=rate_limit, window_seconds=rate_window
        )
        self._sessions: dict[int, UserSession] = {}
        self._agents: dict[int, Any] = {}
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _get_or_create_session(self, chat_id: int, user_id: int, username: Optional[str] = None) -> UserSession:
        """Get existing session or create a new one."""
        if chat_id not in self._sessions:
            self._sessions[chat_id] = UserSession(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
            )
        return self._sessions[chat_id]

    def _get_or_create_agent(self, chat_id: int) -> Any:
        """Get existing agent or create a new one for the session."""
        if chat_id not in self._agents:
            self._agents[chat_id] = self.agent_factory()
        return self._agents[chat_id]

    async def handle_update(self, update: dict) -> None:
        """Handle an incoming Telegram update.

        Routes to command handlers or agent processing.
        """
        message = update.get("message")
        if not message:
            return

        chat_id = message["chat"]["id"]
        user = message.get("from", {})
        user_id = user.get("id", 0)
        username = user.get("username")
        text = message.get("text", "").strip()

        if not text:
            return

        # Access control
        if not self.bot.is_user_allowed(user_id):
            await self.bot.send_message(
                chat_id, "⛔ Access denied. You are not authorized to use this bot."
            )
            logger.warning("Unauthorized access attempt from user %d (@%s)", user_id, username)
            return

        # Rate limiting
        if not self.rate_limiter.is_allowed(user_id):
            remaining_time = int(self.rate_limiter.window_seconds)
            await self.bot.send_message(
                chat_id,
                f"⚠️ Rate limit exceeded. Please wait up to {remaining_time}s before sending more messages.\n"
                f"Limit: {self.rate_limiter.max_requests} messages per {remaining_time}s.",
            )
            return

        # Command routing
        if text.startswith("/"):
            await self._handle_command(chat_id, user_id, username, text)
        else:
            await self._handle_message(chat_id, user_id, username, text)

    async def _handle_command(
        self, chat_id: int, user_id: int, username: Optional[str], text: str
    ) -> None:
        """Handle bot commands."""
        command = text.split()[0].lower().split("@")[0]  # Handle /command@botname

        if command == "/start":
            session = self._get_or_create_session(chat_id, user_id, username)
            session.clear()
            # Reset agent for this session
            if chat_id in self._agents:
                del self._agents[chat_id]
            await self.bot.send_message(
                chat_id,
                "👋 Hello! I'm an AI agent. Send me any message and I'll help you.\n\n"
                "Type /help to see available commands.",
            )

        elif command == "/help":
            await self.bot.send_message(chat_id, self.HELP_TEXT, parse_mode="Markdown")

        elif command == "/clear":
            session = self._get_or_create_session(chat_id, user_id, username)
            session.clear()
            if chat_id in self._agents:
                del self._agents[chat_id]
            await self.bot.send_message(chat_id, "🗑️ Conversation history cleared.")

        elif command == "/cost":
            session = self._get_or_create_session(chat_id, user_id, username)
            await self.bot.send_message(
                chat_id,
                f"📊 *Session Stats*\n\n"
                f"Messages: {session.message_count}\n"
                f"Estimated cost: ${session.total_cost:.4f}\n"
                f"Rate limit remaining: {self.rate_limiter.remaining(user_id)}/{self.rate_limiter.max_requests}",
                parse_mode="Markdown",
            )

        else:
            await self.bot.send_message(
                chat_id, "❓ Unknown command. Type /help to see available commands."
            )

    async def _handle_message(
        self, chat_id: int, user_id: int, username: Optional[str], text: str
    ) -> None:
        """Handle a regular text message by forwarding to the Agent."""
        session = self._get_or_create_session(chat_id, user_id, username)

        # Use per-chat lock to serialize messages within same conversation
        async with self._locks[chat_id]:
            session.add_message("user", text)

            try:
                agent = self._get_or_create_agent(chat_id)

                # Try to invoke the agent
                # The agent_factory should return an object with an invoke/ainvoke method
                response_text = await self._invoke_agent(agent, text, session)

                session.add_message("assistant", response_text)
                await self.bot.send_message(chat_id, response_text)

            except Exception as e:
                logger.error(
                    "Error processing message from user %d in chat %d: %s",
                    user_id, chat_id, e,
                )
                await self.bot.send_message(
                    chat_id,
                    "❌ An error occurred while processing your message. Please try again.",
                )

    async def _invoke_agent(self, agent: Any, text: str, session: UserSession) -> str:
        """Invoke the agent and return the response text.

        Supports multiple agent interfaces:
        - ainvoke(input) -> dict with 'output' key
        - arun(input) -> str
        - invoke(input) -> dict with 'output' key
        - run(input) -> str
        - __call__(input) -> str or dict
        """
        # Build input with conversation context
        input_data = {
            "input": text,
            "chat_history": session.messages[:-1],  # Exclude current message
        }

        try:
            if hasattr(agent, "ainvoke"):
                result = await agent.ainvoke(input_data)
            elif hasattr(agent, "arun"):
                result = await agent.arun(text)
            elif hasattr(agent, "invoke"):
                result = await asyncio.to_thread(agent.invoke, input_data)
            elif hasattr(agent, "run"):
                result = await asyncio.to_thread(agent.run, text)
            elif callable(agent):
                result = await asyncio.to_thread(agent, text)
            else:
                return "❌ Agent does not support any known invocation method."

            # Extract text from result
            if isinstance(result, dict):
                return result.get("output", result.get("response", str(result)))
            return str(result)

        except Exception as e:
            logger.error("Agent invocation error: %s", e)
            raise


async def run_telegram_bot(
    token: str,
    agent_factory: Callable[[], Any],
    allowed_users: Optional[list[int]] = None,
    rate_limit: int = DEFAULT_RATE_LIMIT,
) -> None:
    """Convenience function to start the Telegram bot.

    Args:
        token: Telegram Bot API token.
        agent_factory: Callable that creates an Agent instance per session.
        allowed_users: Optional list of allowed user IDs.
        rate_limit: Max messages per user per minute.
    """
    bot = TelegramBot(token=token, allowed_users=allowed_users)

    # Verify bot token
    bot_info = await bot.get_me()
    if bot_info:
        logger.info(
            "Bot started: @%s (%s)",
            bot_info.get("username"),
            bot_info.get("first_name"),
        )
    else:
        logger.error("Failed to verify bot token. Please check TELEGRAM_BOT_TOKEN.")
        return

    bridge = TelegramAgentBridge(
        bot=bot,
        agent_factory=agent_factory,
        rate_limit=rate_limit,
    )

    try:
        await bot.start_polling(callback=bridge.handle_update)
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    finally:
        await bot.stop()


def _create_default_agent() -> Any:
    """Create a default agent using the framework's built-in configuration.

    Attempts to use the agent framework's standard setup.
    Falls back to a simple echo agent if dependencies are not available.
    """
    try:
        from agent.coordinator import create_agent

        return create_agent()
    except (ImportError, Exception) as e:
        logger.warning("Could not create default agent: %s. Using echo agent.", e)

        class EchoAgent:
            """Fallback echo agent when framework is not fully configured."""

            async def ainvoke(self, input_data: dict) -> dict:
                text = input_data.get("input", "")
                return {"output": f"Echo: {text}\n\n(Default agent not configured. Set up LLM provider.)"}

        return EchoAgent()


def main() -> None:
    """Entry point for the agent-telegram script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error(
            "TELEGRAM_BOT_TOKEN environment variable is not set.\n"
            "Get a token from @BotFather on Telegram."
        )
        raise SystemExit(1)

    # Parse allowed users from environment
    allowed_users_str = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    allowed_users: Optional[list[int]] = None
    if allowed_users_str.strip():
        try:
            allowed_users = [int(uid.strip()) for uid in allowed_users_str.split(",") if uid.strip()]
            logger.info("User whitelist enabled: %s", allowed_users)
        except ValueError:
            logger.error("Invalid TELEGRAM_ALLOWED_USERS format. Use comma-separated user IDs.")
            raise SystemExit(1)

    rate_limit = int(os.environ.get("TELEGRAM_RATE_LIMIT", str(DEFAULT_RATE_LIMIT)))

    logger.info("Starting Telegram Bot...")
    asyncio.run(
        run_telegram_bot(
            token=token,
            agent_factory=_create_default_agent,
            allowed_users=allowed_users,
            rate_limit=rate_limit,
        )
    )


if __name__ == "__main__":
    main()
