from colorama import Fore, init
from tqdm.autonotebook import tqdm

init()


class BaseBarManager:
    @classmethod
    def get_bar_manager(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    def done(self, result):
        # tqdm.write(
        #     "{color}[{message}]{reset}".format(
        #         color=Fore.GREEN, message=result, reset=Fore.RESET
        #     )
        # )
        pass

    def sleep(self, e):
        tqdm.write(
            "{color}[{message} {sleep_time}]{reset}".format(
                color=Fore.BLUE,
                sleep_time=e.sleep_time,
                message=e.msg,
                reset=Fore.RESET,
            )
        )

    def error(self, e):
        tqdm.write(
            "{color}[{message}]{reset}".format(
                color=Fore.RED, message=e.msg, reset=Fore.RESET
            )
        )

    def exists(self, e):
        tqdm.write(
            "{color}[{message}]{reset}".format(
                color=Fore.YELLOW, message=e.msg, reset=Fore.RESET
            )
        )

    def fail(self, e):
        tqdm.write(
            "{color}[{message}]{reset}".format(
                color=Fore.RED, message=e.msg, reset=Fore.RESET
            )
        )
