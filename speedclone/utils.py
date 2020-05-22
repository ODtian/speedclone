import functools
import os
import time

from colorama import Fore, init
from tqdm.autonotebook import tqdm

init()


class DataIter:
    def __init__(self, file_piece, step_size, bar):
        self.bar = bar
        self.step_size = step_size
        self.file_piece = file_piece

    def __iter__(self):
        while self.file_piece:
            step = self.file_piece[: self.step_size]
            yield step
            self.bar.update(len(step))
            self.file_piece = self.file_piece[self.step_size :]

    def __len__(self):
        return len(self.file_piece)


def norm_path(*path):
    norm = [os.path.normpath(p).replace("\\", "/").strip("/") for p in path if p]
    return "/".join(norm)


def get_now_time():
    return "[" + time.strftime("%H:%M:%S", time.localtime()) + "]"


def iter_path(path):
    if os.path.isfile(path):
        yield path
    else:
        for root, _, files in os.walk(path):
            for filename in files:
                yield os.path.join(root, filename)


def with_lock(lock):
    def _with_lock(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            with lock:
                return func(self, *args, **kwargs)

        return wrapper

    return _with_lock


def console_write(mode, message):
    if mode == "sleep":
        tqdm.write(
            "{color}[{message}]{reset}".format(
                color=Fore.BLUE, message=message, reset=Fore.RESET,
            )
        )

    elif mode == "error":
        tqdm.write(
            "{color}[{message}]{reset}".format(
                color=Fore.RED, message=message, reset=Fore.RESET
            )
        )

    elif mode == "exists":
        tqdm.write(
            "{color}[{message}]{reset}".format(
                color=Fore.YELLOW, message=message, reset=Fore.RESET
            )
        )

    elif mode == "fail":
        tqdm.write(
            "{color}[{message}]{reset}".format(
                color=Fore.RED, message=message, reset=Fore.RESET
            )
        )
