import asyncio
from pathlib import Path
import sys
import subprocess
import click
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

from agent.agent import Agent
from agent.events import AgentEventType
from agent.persistence import PersistenceManager, SessionSnapshot
from agent.session import Session
from config.config import ApprovalPolicy, Config
from config.loader import load_config
from ui.tui import TUI, get_console

console = get_console()


class CLI:
    def __init__(self, config: Config):
        self.agent: Agent | None = None
        self.config = config
        self.tui = TUI(config, console)

    async def run_single(self, message: str, shared_session: Session) -> str | None:
        async def cli_ask_user(question: str) -> str:
            from prompt_toolkit import PromptSession
            sess = PromptSession()
            return await sess.prompt_async(f"\n[ansiblue bold]Agent asks:[/ansiblue bold] {question}\n[user]> ")
            
        shared_session.ask_user_callback = cli_ask_user
        
        async with Agent(self.config, session=shared_session) as agent:
            self.agent = agent
            return await self._process_message(message)

    async def run_interactive(self, shared_session: Session) -> str | None:
        self.tui.print_welcome(
            "AI Agent",
            lines=[
                f"model: {self.config.model_name}",
                f"cwd: {self.config.cwd}",
                "commands: /help /config /approval /model /exit",
            ],
        )

        class CommandCompleter(Completer):
            def __init__(self):
                self.commands = {
                    "/help": "Show this help",
                    "/exit": "Exit the agent",
                    "/quit": "Exit the agent",
                    "/clear": "Clear conversation history",
                    "/config": "Show current configuration",
                    "/model": "Change the model",
                    "/approval": "Change approval mode",
                    "/stats": "Show session statistics",
                    "/tools": "List available tools",
                    "/mcp": "Show MCP server status",
                    "/save": "Save current session",
                    "/checkpoint": "Create a checkpoint",
                    "/checkpoints": "List available checkpoints",
                    "/restore": "Restore a checkpoint",
                    "/sessions": "List saved sessions",
                    "/resume": "Resume a saved session"
                }

            def get_completions(self, document, complete_event):
                text = document.text_before_cursor.lstrip()
                if text.startswith('/'):
                    for cmd, desc in self.commands.items():
                        if cmd.startswith(text.lower()):
                            yield Completion(cmd, start_position=-len(text), display_meta=desc)

        completer = CommandCompleter()
        style = Style.from_dict({
            "prompt": "ansiblue bold",
            "completion-menu.completion": "bg:#333333 #ffffff",
            "completion-menu.completion.current": "bg:#00aa00 #ffffff",
            "completion-menu.meta.completion": "bg:#333333 #aaaaaa",
            "completion-menu.meta.completion.current": "bg:#00aa00 #ffffff",
        })
        prompt_session = PromptSession(completer=completer, style=style, complete_while_typing=True)

        async def cli_ask_user(question: str) -> str:
            return await prompt_session.prompt_async(f"\n[ansiblue bold]Agent asks:[/ansiblue bold] {question}\n[user]> ")

        shared_session.ask_user_callback = cli_ask_user

        async with Agent(
            self.config,
            confirmation_callback=self.tui.handle_confirmation,
            session=shared_session,
        ) as agent:
            self.agent = agent

            while True:
                try:
                    user_input = await prompt_session.prompt_async("\n[user]> ")
                    user_input = user_input.strip()
                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        should_continue = await self._handle_command(user_input)
                        if not should_continue:
                            break
                        continue

                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                except EOFError:
                    break

        console.print("\n[dim]Goodbye![/dim]")

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool_kind = None
        tool = self.agent.session.tool_registry.get(tool_name)
        if not tool:
            tool_kind = None

        tool_kind = tool.kind.value

        return tool_kind

    async def _process_message(self, message: str) -> str | None:
        if not self.agent:
            return None

        assistant_streaming = False
        final_response: str | None = None

        async for event in self.agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get("content", "")
                if not assistant_streaming:
                    self.tui.begin_assistant()
                    assistant_streaming = True
                self.tui.stream_assistant_delta(content)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                if assistant_streaming:
                    self.tui.end_assistant()
                    assistant_streaming = False
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data.get("error", "Unknown error")
                console.print(f"\n[error]Error: {error}[/error]")
            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_start(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("arguments", {}),
                )
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_complete(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("success", False),
                    event.data.get("output", ""),
                    event.data.get("error"),
                    event.data.get("metadata"),
                    event.data.get("diff"),
                    event.data.get("truncated", False),
                    event.data.get("exit_code"),
                )

        return final_response

    async def _handle_command(self, command: str) -> bool:
        cmd = command.lower().strip()
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else ""
        if cmd_name == "/exit" or cmd_name == "/quit":
            return False
        elif command == "/help":
            self.tui.show_help()
        elif command == "/clear":
            self.agent.session.context_manager.clear()
            self.agent.session.loop_detector.clear()
            console.print("[success]Conversation cleared [/success]")
        elif command == "/config":
            console.print("\n[bold]Current Configuration[/bold]")
            console.print(f"  Model: {self.config.model_name}")
            console.print(f"  Temperature: {self.config.temperature}")
            console.print(f"  Approval: {self.config.approval.value}")
            console.print(f"  Working Dir: {self.config.cwd}")
            console.print(f"  Max Turns: {self.config.max_turns}")
            console.print(f"  Hooks Enabled: {self.config.hooks_enabled}")
        elif cmd_name == "/model":
            if cmd_args:
                self.config.model_name = cmd_args
                console.print(f"[success]Model changed to: {cmd_args} [/success]")
            else:
                try:
                    output = subprocess.check_output(["ollama", "list"], text=True)
                    models = [line.split()[0] for line in output.splitlines()[1:] if line.strip()]
                    if models:
                        from rich.prompt import Prompt
                        default_model = self.config.model_name if self.config.model_name in models else None
                        console.print()
                        for i, m in enumerate(models):
                            console.print(f"  {i+1}. {m}")
                        
                        selected = Prompt.ask("\nSelect a model", choices=[str(i+1) for i in range(len(models))] + models, default=default_model)
                        
                        if selected in models:
                            self.config.model_name = selected
                        else:
                            self.config.model_name = models[int(selected)-1]
                            
                        console.print(f"[success]Model changed to: {self.config.model_name} [/success]")
                    else:
                        console.print(f"Current model: {self.config.model_name} (No ollama models found)")
                except Exception as e:
                    console.print(f"Current model: {self.config.model_name} (Error listing ollama: {e})")
        elif cmd_name == "/approval":
            if cmd_args:
                try:
                    approval = ApprovalPolicy(cmd_args)
                    self.config.approval = approval
                    console.print(
                        f"[success]Approval policy changed to: {cmd_args} [/success]"
                    )
                except:
                    console.print(
                        f"[error]Incorrect approval policy: {cmd_args} [/error]"
                    )
                    console.print(
                        f"Valid options: {', '.join(p for p in ApprovalPolicy)}"
                    )
            else:
                console.print(f"Current approval policy: {self.config.approval.value}")
        elif cmd_name == "/stats":
            stats = self.agent.session.get_stats()
            console.print("\n[bold]Session Statistics [/bold]")
            for key, value in stats.items():
                console.print(f"   {key}: {value}")
        elif cmd_name == "/tools":
            tools = self.agent.session.tool_registry.get_tools()
            console.print(f"\n[bold]Available tools ({len(tools)}) [/bold]")
            for tool in tools:
                console.print(f"  • {tool.name}")
        elif cmd_name == "/mcp":
            mcp_servers = self.agent.session.mcp_manager.get_all_servers()
            console.print(f"\n[bold]MCP Servers ({len(mcp_servers)}) [/bold]")
            for server in mcp_servers:
                status = server["status"]
                status_color = "green" if status == "connected" else "red"
                console.print(
                    f"  • {server['name']}: [{status_color}]{status}[/{status_color}] ({server['tools']} tools)"
                )
        elif cmd_name == "/save":
            persistence_manager = PersistenceManager()
            session_snapshot = SessionSnapshot(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            persistence_manager.save_session(session_snapshot)
            console.print(
                f"[success]Session saved: {self.agent.session.session_id}[/success]"
            )
        elif cmd_name == "/sessions":
            persistence_manager = PersistenceManager()
            sessions = persistence_manager.list_sessions()
            console.print("\n[bold]Saved Sessions[/bold]")
            for s in sessions:
                console.print(
                    f"  • {s['session_id']} (turns: {s['turn_count']}, updated: {s['updated_at']})"
                )
        elif cmd_name == "/resume":
            if not cmd_args:
                console.print(f"[error]Usage: /resume <session_id> [/error]")
            else:
                persistence_manager = PersistenceManager()
                snapshot = persistence_manager.load_session(cmd_args)
                if not snapshot:
                    console.print(f"[error]Session does not exist [/error]")
                else:
                    session = Session(
                        config=self.config,
                    )
                    await session.initialize()
                    session.session_id = snapshot.session_id
                    session.created_at = snapshot.created_at
                    session.updated_at = snapshot.updated_at
                    session.turn_count = snapshot.turn_count
                    session.context_manager.total_usage = snapshot.total_usage

                    for msg in snapshot.messages:
                        if msg.get("role") == "system":
                            continue
                        elif msg["role"] == "user":
                            session.context_manager.add_user_message(
                                msg.get("content", "")
                            )
                        elif msg["role"] == "assistant":
                            session.context_manager.add_assistant_message(
                                msg.get("content", ""), msg.get("tool_calls")
                            )
                        elif msg["role"] == "tool":
                            session.context_manager.add_tool_result(
                                msg.get("tool_call_id", ""), msg.get("content", "")
                            )

                    await self.agent.session.client.close()
                    await self.agent.session.mcp_manager.shutdown()

                    self.agent.session = session
                    console.print(
                        f"[success]Resumed session: {session.session_id}[/success]"
                    )
        elif cmd_name == "/checkpoint":
            persistence_manager = PersistenceManager()
            session_snapshot = SessionSnapshot(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            checkpoint_id = persistence_manager.save_checkpoint(session_snapshot)
            console.print(f"[success]Checkpoint created: {checkpoint_id}[/success]")
        elif cmd_name == "/restore":
            if not cmd_args:
                console.print(f"[error]Usage: /restire <checkpoint_id> [/error]")
            else:
                persistence_manager = PersistenceManager()
                snapshot = persistence_manager.load_checkpoint(cmd_args)
                if not snapshot:
                    console.print(f"[error]Checkpoint does not exist [/error]")
                else:
                    session = Session(
                        config=self.config,
                    )
                    await session.initialize()
                    session.session_id = snapshot.session_id
                    session.created_at = snapshot.created_at
                    session.updated_at = snapshot.updated_at
                    session.turn_count = snapshot.turn_count
                    session.context_manager.total_usage = snapshot.total_usage

                    for msg in snapshot.messages:
                        if msg.get("role") == "system":
                            continue
                        elif msg["role"] == "user":
                            session.context_manager.add_user_message(
                                msg.get("content", "")
                            )
                        elif msg["role"] == "assistant":
                            session.context_manager.add_assistant_message(
                                msg.get("content", ""), msg.get("tool_calls")
                            )
                        elif msg["role"] == "tool":
                            session.context_manager.add_tool_result(
                                msg.get("tool_call_id", ""), msg.get("content", "")
                            )

                    await self.agent.session.client.close()
                    await self.agent.session.mcp_manager.shutdown()

                    self.agent.session = session
                    console.print(
                        f"[success]Resumed session: {session.session_id}, checkpoint: {checkpoint_id}[/success]"
                    )
        else:
            console.print(f"[error]Unknown command: {cmd_name}[/error]")

        return True


@click.command()
@click.argument("prompt", required=False)
@click.option(
    "--cwd",
    "-c",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Current working directory",
)
@click.option(
    "--cli",
    "cli_flag",
    is_flag=True,
    help="Start interactive CLI in foreground alongside background channels",
)
def main(
    prompt: str | None,
    cwd: Path | None,
    cli_flag: bool,
):
    load_dotenv()
    
    try:
        config = load_config(cwd=cwd)
    except Exception as e:
        console.print(f"[error]Configuration Error: {e}[/error]")

    errors = config.validate()

    if errors:
        for error in errors:
            console.print(f"[error]{error}[/error]")

        sys.exit(1)

    cli_instance = CLI(config)

    async def run_app():
        shared_session = Session(config)
        await shared_session.initialize()

        telegram_channel = None
        if config.telegram_bot_token and config.telegram_authorized_chat_id:
            try:
                from channels.telegram_channel import TelegramChannel
                telegram_channel = TelegramChannel(config, shared_session)
                await telegram_channel.start()
            except Exception as e:
                console.print(f"[error]Failed to start Telegram channel: {e}[/error]")

        try:
            if prompt:
                await cli_instance.run_single(prompt, shared_session)
            elif cli_flag or (not telegram_channel):
                await cli_instance.run_interactive(shared_session)
            else:
                console.print("[info]Telegram bot is running in the background. Use --cli to open the interactive terminal.[/info]")
                await asyncio.Event().wait()
                
        finally:
            if telegram_channel:
                await telegram_channel.stop()
            if shared_session.client:
                await shared_session.client.close()
            if shared_session.mcp_manager:
                await shared_session.mcp_manager.shutdown()

    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        pass


main()
