import atexit
from enum import Enum
from getpass import getpass
import shutil
import sys
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


_last_process_name: str = ""
_last_progress: str = ""
_footer_process_name: str = ""
_footer_left: str = ""
_footer_right: str = ""
_spinner_frame: int = 0
_SPINNER_CHARS = ('|', '/', '-', '\\')
_tty_mode: bool = sys.stdout.isatty()
_tty_lock: Lock = Lock()
_tty_stop: Event = Event()


def _draw_footer_locked() -> None:
    cols = shutil.get_terminal_size().columns
    char = _SPINNER_CHARS[_spinner_frame]
    prefix = f"{char} "
    available = cols - len(prefix)
    pn = _footer_process_name
    rest = _footer_left[len(pn):]
    right_width = available - len(_footer_left)
    if _footer_right and right_width > 0:
        right = _footer_right[-right_width:].rjust(right_width)
    else:
        visible = _footer_left[:available]
        pn = visible[:len(pn)]
        rest = visible[len(pn):]
        right = ""
    sys.stdout.write(
        f"\r\033[2K{Colors.INFO.value}{prefix}"
        f"{Colors.HEADER.value}{pn}{Colors.INFO.value}{rest}{right}"
        f"{Colors.ENDC.value}"
    )
    sys.stdout.flush()


def _spinner_worker() -> None:
    global _spinner_frame
    while not _tty_stop.wait(1 / 15):
        with _tty_lock:
            _spinner_frame = (_spinner_frame + 1) % 4
            _draw_footer_locked()


def _atexit_cleanup() -> None:
    _tty_stop.set()
    with _tty_lock:
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()


if _tty_mode:
    atexit.register(_atexit_cleanup)
    Thread(target=_spinner_worker, daemon=True).start()


def pprint(values, color: Colors = Colors.NONE, file=sys.stdout):
    if _tty_mode:
        with _tty_lock:
            if file.isatty():
                sys.stdout.write("\r\033[2K")
                sys.stdout.flush()
                file.write(f"{color.value}{values}{Colors.ENDC.value}\n")
                file.flush()
                _draw_footer_locked()
            else:
                file.write(f"{values}\n")
                file.flush()
    elif file.isatty():
        print(f"{color.value}{values}{Colors.ENDC.value}", file=file)
    else:
        print(values, file=file)


def eprint(values, color: Colors = Colors.FAIL):
    pprint(values, color, file=sys.stderr)


def statprint(process_name: str, progress: str = "", context: str = "") -> None:
    global _last_process_name, _last_progress, _footer_process_name, _footer_left, _footer_right
    _last_process_name = process_name
    _last_progress = progress
    left = f"{process_name} [{progress}]…" if progress else f"{process_name}…"

    if _tty_mode:
        with _tty_lock:
            _footer_process_name = process_name
            _footer_left = left
            _footer_right = context + " "
            _draw_footer_locked()
    else:
        if context:
            cols = shutil.get_terminal_size().columns
            line = f"{left}{context.rjust(cols - len(left))} "
        else:
            line = left
        pprint(line, Colors.INFO)


def statprint_context(context: str) -> None:
    statprint(_last_process_name, _last_progress, context)


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
