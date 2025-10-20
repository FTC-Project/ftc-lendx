from typing import Dict, Type, Optional, Iterable
from dataclasses import dataclass

from backend.apps.telegram_bot.commands.base import BaseCommand


@dataclass
class CommandMeta:
    cls: Type[BaseCommand]
    name: str
    aliases: Iterable[str]
    description: str
    permission: str  # e.g. "public", "user", "admin"


_command_classes: Dict[str, CommandMeta] = {}


def register(
    name: str,
    *,
    aliases: Optional[Iterable[str]] = None,
    description: str = "",
    permission: str = "public"
):
    """Decorator: @register('name', aliases=['/name'], permission='user')"""
    aliases = aliases or []

    def _decorator(cls: Type[BaseCommand]) -> Type[BaseCommand]:
        meta = CommandMeta(
            cls=cls,
            name=name,
            aliases=aliases,
            description=description,
            permission=permission,
        )
        _command_classes[name] = meta
        for a in aliases:
            _command_classes[a] = meta
        return cls

    return _decorator


def get_command_meta(name: str) -> Optional[CommandMeta]:
    return _command_classes.get(name)


def all_command_metas() -> Dict[str, CommandMeta]:
    return dict(_command_classes)
