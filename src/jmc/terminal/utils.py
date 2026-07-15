from enum import Enum
from getpass import getpass
import shutil
import sys
import time
from threading import Event, Lock, Thread
from traceback import format_exc
from ..compile import Logger

logger = Logger(__name__)


class Colors(Enum):
    HEADER = "\033[1;33m"
    YELLOW = "\033[33m"
    INFO = "\033[94m"
    INPUT = "\033[96m"
    PURPLE = "\033[35m"
    CONTEXT = "\033[90m"
    FAIL = "\033[91m"
    FAIL_BOLD = "\033[1;91m"
    ENDC = "\033[0m"
    EXIT = "\033[0m"
    NONE = "\033[0m"


SPINNER_FRAMES = ["|","/","-","\\"]
SPINNER_DELAY = 0.0667  # In seconds

_tty_mode: bool = sys.stdout.isatty()
_phase_start: float = 0.0
_tty_lock: Lock = Lock()
_spinner_stop: Event = Event()
_spinner_frame: int = 0
_spinner_thread: Thread | None = None
_action: str | None = None
_context: str | None = None


def _spinner_worker() -> None:
    global _spinner_frame
    while not _spinner_stop.wait(SPINNER_DELAY):
        _spinner_frame = (_spinner_frame + 1) % len(SPINNER_FRAMES)
        print_status()


def start_spinner() -> None:
    global _spinner_thread, _spinner_frame
    if not _tty_mode:
        return
    _spinner_stop.clear()
    _spinner_frame = 0
    _spinner_thread = Thread(target=_spinner_worker, daemon=True)
    _spinner_thread.start()


def stop_spinner() -> None:
    global _spinner_thread
    print_status()
    if _spinner_thread is not None and _spinner_thread.is_alive():
        _spinner_stop.set()
        _spinner_thread.join()
        _spinner_thread = None


def pprint(values, color: Colors = Colors.NONE, file=sys.stdout):
    formatted = f"{color.value}{values}{Colors.ENDC.value}" if file.isatty() else str(values)
    if _tty_mode:
        with _tty_lock:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
            print(formatted, file=file)
    else:
        print(formatted, file=file)
    print_status()


def eprint(values, color: Colors = Colors.FAIL):
    pprint(values, color, file=sys.stderr)


def print_status() -> None:
    if not _tty_mode:
        return
    with _tty_lock:
        if not _action:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
            return

        console_width = shutil.get_terminal_size().columns

        output_text = f"\r\033[2K{Colors.NONE.value}{SPINNER_FRAMES[_spinner_frame]} "
        output_length = 3 + len(_action) # spinner will always be one char
        output_text += f"{Colors.YELLOW.value}{_action}…"

        if _context and (output_length + 1 + len(_context)) <= console_width:
            padding = console_width - output_length - len(_context) - 1
            output_text += (' ' * padding) + f"{Colors.CONTEXT.value}{_context}"

        sys.stdout.write(output_text)
        sys.stdout.flush()


def handle_message_hook(message: str) -> None:
    pprint(message, Colors.YELLOW)


def handle_status_hook(action: str) -> None:
    global _action, _context, _phase_start
    _action = action
    _context = None
    _phase_start = time.monotonic()


def handle_done_hook() -> None:
    global _action, _context
    elapsed = time.monotonic() - _phase_start
    pprint(f"{_action} complete ({elapsed:.3f}s)", Colors.INFO)
    _action = None
    _context = None


def handle_context_hook(context: str) -> None:
    global _context
    _context = context


def abort_progress() -> None:
    global _action, _context
    if _tty_mode:
        stop_spinner()
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()
    _action = None
    _context = None


def get_input(prompt: str = "> ", color: Colors = Colors.INPUT) -> str:
    """
    Get an input from user

    :param prompt: Display string infront
    :param color: Color of the input and promt
    :return: input from user
    """
    if sys.stdout.isatty():
        input_value = input(f"{color.value}{prompt}")
        print(Colors.ENDC.value, end="", flush=True)
    else:
        input_value = input(prompt)
    logger.info(f"Input from user: {input_value}")
    return input_value


def press_enter(prompt: str, color: Colors = Colors.INPUT) -> None:
    """
    Wait for Enter key from user

    :param prompt: Display string
    :param color: Color of prompt
    """
    getpass(f"{color.value}{prompt}{Colors.ENDC.value}")


def error_report(error: Exception) -> None:
    eprint(type(error).__name__, Colors.FAIL_BOLD)
    eprint(error)


def handle_exception(error: Exception, event: Event, is_ok: bool):
    event.set()
    eprint("An unexpected error caused the program to crash")
    eprint(type(error).__name__, Colors.FAIL_BOLD)
    eprint(error)
    if not is_ok:
        eprint(format_exc(), Colors.YELLOW)
        eprint(
            "Please report this error at https://github.com/WingedSeal/jmc/issues/new/choose or https://discord.gg/PNWKpwdzD3.")
    logger.critical("Program crashed")
    logger.exception("")
    press_enter("Press Enter to continue...")


class RestartException(BaseException):
    """Raise to restart the program without telling error to user"""
