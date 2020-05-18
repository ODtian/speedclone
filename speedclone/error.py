class TaskException(Exception):
    def __init__(self, task, msg, code=1):
        self.task = task
        self.msg = msg
        self.code = code


class TaskSleepError(TaskException):
    def __init__(
        self, sleep_time, *args, **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.sleep_time = sleep_time


class TaskFailError(TaskException):
    def __init__(
        self, exce=None, *args, **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.exce = exce


class TaskExistError(TaskException):
    def __init__(
        self, *args, **kwargs,
    ):
        super().__init__(*args, **kwargs)
