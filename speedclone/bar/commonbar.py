from tqdm.autonotebook import tqdm
from .basebar import BaseBarManager


class CommonBar:
    max_width = 20
    slow = 20

    def __init__(self):
        self.step = 1
        self.bar = None

    def init_bar(self, total, desc):
        self.content = desc.ljust(self.max_width, " ")
        self.bar = self._create_bar(total)

    def update(self, n):
        self.scroll_text()
        self.bar.set_description_str(self.content[: self.max_width])
        self.bar.update(n)

    def close(self):
        if self.bar:
            self.bar.close()

    def scroll_text(self):
        if self.step % self.slow == 0:
            self.content = self.content[1:] + self.content[0]
        self.step += 1

    def _create_bar(self, total):
        bar_format = "| {desc} | {percentage: >6.2f}% |{bar:20}| {n_fmt:>6} / {total_fmt:<6} [{rate_fmt:<8} {elapsed}>{remaining}]"
        bar = tqdm(
            total=total,
            bar_format=bar_format,
            unit="B",
            unit_scale=True,
            unit_divisor=1024
        )
        bar.set_description_str(self.content[: self.max_width])
        return bar


class CommonBarManager(BaseBarManager):
    def __init__(self, max_workers=5):
        self.n = 0
        self.max_workers = max_workers

    def get_bar(self, task):
        bar = CommonBar()
        return bar
