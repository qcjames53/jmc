from typing import Callable

_message_handler: Callable[[str], None] = print
_status_handler: Callable[..., None] = lambda pn, c="", pr="": print(f"{pn}…")
_context_handler: Callable[[str], None] = lambda _: None


def register_message(fn: Callable[[str], None]) -> None:
    """Register a handler for user-facing compile-time messages.

    This hook avoids a circular import and prevents the compile module from knowing specifics of how output is rendered.
    Note: Must be called before compilation begins. Not thread-safe to call concurrently with emit_message.

    :param fn: lambda which receives the message string and renders it.
    """
    global _message_handler
    _message_handler = fn


def emit_message(message: str) -> None:
    """Emit a user-facing message through the registered handler.

    :param message: The message string to emit.
    """
    _message_handler(message)


def register_status(fn: Callable[..., None]) -> None:
    global _status_handler
    _status_handler = fn


def emit_status(process_name: str, progress: str = "", context: str = "") -> None:
    _status_handler(process_name, progress, context)


def register_context(fn: Callable[[str], None]) -> None:
    global _context_handler
    _context_handler = fn


def emit_context(context: str) -> None:
    _context_handler(context)


_info_handler: Callable[[str], None] = print


def register_info(fn: Callable[[str], None]) -> None:
    global _info_handler
    _info_handler = fn


def emit_info(message: str) -> None:
    _info_handler(message)