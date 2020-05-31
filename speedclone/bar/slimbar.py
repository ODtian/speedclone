from tqdm.autonotebook import tqdm
from .basebar import BaseBarManager


class SlimBar:
    def __init__(self):
        self.byte_bar = tqdm(
            total=0, position=1, unit="B", unit_scale=True, unit_divisor=1024
        )
        self.count_bar = tqdm(total=0, position=2, unit="tasks")

    def init_bar(self, total, desc):
        pass

    def update_total(self, bar, n):
        bar.total += n
        bar.refresh()

    def update(self, n):
        self.byte_bar.update(n)

    def close(self):
        pass

    def close_bar(self):
        self.count_bar.close()
        self.byte_bar.close()


class SlimBarManager(BaseBarManager):
    def __init__(self):
        self.bar = SlimBar()

    def update_total(self, task):
        self.bar.update_total(self.bar.byte_bar, task.get_total())
        self.bar.update_total(self.bar.count_bar, 1)

    def update(self, task):
        self.bar.update(task.get_total())
        self.bar.count_bar.update(1)

    def get_bar(self, task):
        self.update_total(task)
        return self.bar

    def done(self):
        self.bar.count_bar.update(1)

    def sleep(self, e):
        super().sleep(e)
        self.update(e.task)

    def error(self, e):
        super().error(e)
        self.update(e.task)

    def fail(self, e):
        super().fail(e)
        self.update(e.task)

    def exists(self, e):
        super().exists(e)
        self.update(e.task)

    def exit(self):
        self.bar.close_bar()
