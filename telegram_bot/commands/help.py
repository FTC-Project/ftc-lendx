from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Send help text asynchronously."""
    from ..tasks import help_command_task

    help_command_task.delay(msg.__dict__)
