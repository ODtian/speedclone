class TaskException(Exception):
    def __init__(self, task, msg, code=1):
        self.task = task
        self.msg = msg
        self.code = code


class TaskSleepError(TaskException):
    def __init__(
        self, sleep_time, **kwargs,
    ):
        super().__init__(**kwargs)
        self.sleep_time = sleep_time


class TaskFailError(TaskException):
    def __init__(
        self, exce=None, **kwargs,
    ):
        super().__init__(**kwargs)
        self.exce = exce
        self.msg += "" if self.msg else str(type(self.exce))


class TaskExistError(TaskException):
    def __init__(
        self, **kwargs,
    ):
        if "msg" not in kwargs.keys():
            t = kwargs.get("task")
            msg = "{}: File already exists".format(t.get_relative_path())
            kwargs["msg"] = msg
        super().__init__(**kwargs)
