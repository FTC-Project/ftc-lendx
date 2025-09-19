from typing import TYPE_CHECKING

from ..messages import TelegramMessage

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..bot import TelegramBot


def handle(bot: "TelegramBot", msg: TelegramMessage) -> None:
    """Queue price lookup so it runs in the Celery worker."""
    from ..tasks import prices_command_task

    prices_command_task.delay(msg.__dict__)
