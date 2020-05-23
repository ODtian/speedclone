from tqdm.autonotebook import tqdm
from .basebar import BaseBarManager


class ByteBar:
    def __init__(self):
        self.bar = self._create_bar(0)

    def init_bar(self, total, desc):
        pass

    def update_total(self, n):
        self.bar.total += n
        self.bar.refresh()

    def update(self, n):
        self.bar.update(n)

    def close(self):
        pass

    def close_bar(self):
        self.bar.close()

    def _create_bar(self, total):
        bar = tqdm(
            total=total, position=1, unit="B", unit_scale=True, unit_divisor=1024
        )
        return bar


class CountBar:
    def __init__(self):
        self.bar = self._create_bar(0)

    def init_bar(self, total, desc):
        pass

    def update_total(self, n):
        self.bar.total += n
        self.bar.refresh()

    def update(self, n):
        self.bar.update(n)

    def close(self):
        pass

    def close_bar(self):
        self.bar.close()

    def _create_bar(self, total):
        bar = tqdm(total=total, position=2, unit="tasks")
        return bar


class SlimBarManager(BaseBarManager):
    def __init__(self, max_workers=5):
        self.byte_bar = ByteBar()
        self.count_bar = CountBar()

    def get_bar(self, task):
        self.byte_bar.update_total(task.get_total())
        self.count_bar.update_total(1)
        return self.byte_bar

    def sleep(self, e):
        super().sleep(e)
        self.byte_bar.update(e.task.get_total())
        self.count_bar.update(1)

    def error(self, e):
        super().error(e)
        self.byte_bar.update(e.task.get_total())
        self.count_bar.update(1)

    def exists(self, e):
        super().exists(e)
        self.byte_bar.update(e.task.get_total())
        self.count_bar.update(1)

    def fail(self, e):
        super().fail(e)
        self.byte_bar.update(e.task.get_total())
        self.count_bar.update(1)

    def done(self, result):
        self.count_bar.update(1)

    def exit(self):
        self.byte_bar.close_bar()
        self.count_bar.close_bar()
