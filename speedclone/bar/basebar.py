from ..utils import console_write


class BaseBarManager:
    @classmethod
    def get_bar_manager(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    def sleep(self, e):
        message = "{message} {sleep_time}".format(
            sleep_time=e.sleep_time, message=e.msg
        )
        console_write(mode="sleep", message=message)

    def error(self, e):
        console_write(mode="error", message=e.msg)

    def exists(self, e):
        console_write(mode="exists", message=e.msg)

    def fail(self, e):
        console_write(mode="fail", message=e.msg)
