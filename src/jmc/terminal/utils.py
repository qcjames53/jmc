from enum import Enum
from getpass import getpass
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
    FAIL = "\033[91m"
    FAIL_BOLD = "\033[1;91m"
    ENDC = "\033[0m"
    EXIT = "\033[0m"
    NONE = "\033[0m"


TICK_SYMBOL = "."
TICK_SPINNER = ["|","/","-","\\"]

# TICK_SYMBOL = "▪"
# TICK_SPINNER = ["⬝","▪","■","▪"]

# TICK_SYMBOL = "."
# TICK_SPINNER = [".","o","O","0","@","0","O","o"]

TICK_SPINNER_DELAY = 1 / 15  # In seconds

_tty_mode: bool = sys.stdout.isatty()
_tick_header: str = ""
_tick_count: int = 0
_tick_line_open: bool = False
_phase_start: float = 0.0
_tty_lock: Lock = Lock()
_spinner_stop: Event = Event()
_spinner_frame: int = 0
_spinner_thread: Thread | None = None


def _spinner_worker() -> None:
    global _spinner_frame
    while not _spinner_stop.wait(TICK_SPINNER_DELAY):
        _spinner_frame = (_spinner_frame + 1) % len(TICK_SPINNER)
        with _tty_lock:
            sys.stdout.write(f"\b{TICK_SPINNER[_spinner_frame]}")
            sys.stdout.flush()


def _start_spinner() -> None:
    global _spinner_thread, _spinner_frame
    _spinner_stop.clear()
    _spinner_frame = 0
    _spinner_thread = Thread(target=_spinner_worker, daemon=True)
    _spinner_thread.start()


def _stop_spinner() -> None:
    global _spinner_thread
    if _spinner_thread is not None and _spinner_thread.is_alive():
        _spinner_stop.set()
        _spinner_thread.join()
        _spinner_thread = None


def pprint(values, color: Colors = Colors.NONE, file=sys.stdout):
    line_was_open = _tick_line_open and (_tty_mode or file is sys.stdout)
    if line_was_open and _tty_mode:
        with _tty_lock:
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
            if file.isatty():
                print(f"{color.value}{values}{Colors.ENDC.value}", file=file)
            else:
                print(values, file=file)
            sys.stdout.write(f"{Colors.INFO.value}{_tick_header}{TICK_SYMBOL * _tick_count}{TICK_SPINNER[_spinner_frame]}")
            sys.stdout.flush()
        return
    if line_was_open:
        sys.stdout.write("↵\n")
        sys.stdout.flush()
    if file.isatty():
        print(f"{color.value}{values}{Colors.ENDC.value}", file=file)
    else:
        print(values, file=file)
    if line_was_open:
        sys.stdout.write(_tick_header + TICK_SYMBOL * _tick_count)
        sys.stdout.flush()


def eprint(values, color: Colors = Colors.FAIL):
    pprint(values, color, file=sys.stderr)


def handle_message_hook(message: str) -> None:
    pprint(message, Colors.YELLOW)


def handle_status_hook(action: str, file_count: int | None = None) -> None:
    global _tick_header, _tick_count, _tick_line_open, _phase_start
    if _tty_mode:
        _stop_spinner()
    _phase_start = time.monotonic()
    _tick_header = f"{action} {file_count} files " if file_count is not None else f"{action} "
    _tick_count = 0

    if _tick_line_open:
        sys.stdout.write("\r\033[2K" if _tty_mode else "\n")
        sys.stdout.flush()

    _tick_line_open = True
    if _tty_mode:
        sys.stdout.write(f"{Colors.INFO.value}{_tick_header}{TICK_SPINNER[0]}")
        sys.stdout.flush()
        _start_spinner()
    else:
        sys.stdout.write(_tick_header)
        sys.stdout.flush()


def handle_tick_hook() -> None:
    global _tick_count
    _tick_count += 1
    if _tty_mode:
        with _tty_lock:
            sys.stdout.write(f"\b{TICK_SYMBOL}{TICK_SPINNER[_spinner_frame]}")
            sys.stdout.flush()
    else:
        sys.stdout.write(TICK_SYMBOL)
        sys.stdout.flush()


def abort_progress() -> None:
    global _tick_line_open
    if not _tick_line_open:
        return
    _tick_line_open = False
    if _tty_mode:
        _stop_spinner()
    sys.stdout.write("\n")
    sys.stdout.flush()


def handle_done_hook() -> None:
    global _tick_line_open
    elapsed = time.monotonic() - _phase_start
    _tick_line_open = False
    if _tty_mode:
        _stop_spinner()
        sys.stdout.write(f"\r{Colors.INFO.value}{_tick_header}{TICK_SYMBOL * _tick_count} done ({elapsed:.3f}s){Colors.ENDC.value}\n")
    else:
        sys.stdout.write(f" done ({elapsed:.3f}s)\n")
    sys.stdout.flush()


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
