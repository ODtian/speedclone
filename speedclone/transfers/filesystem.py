from ..error import TaskExistError, TaskFailError
from ..utils import norm_path, iter_path
import os


class FileSystemTransferDownloadTask:
    def __init__(self, file_path, relative_path):
        self.file_path = file_path
        self.relative_path = relative_path

    def iter_data(self, chunk_size=(10 * 1024 ** 2)):
        with open(self.file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if chunk:
                    yield chunk
                else:
                    return

    def get_relative_path(self):
        return self.relative_path

    def get_total(self):
        return os.path.getsize(self.file_path)


class FileSystemTransferUploadTask:
    chunk_size = 10 * 1024 ** 2
    step_size = 1024 ** 2

    def __init__(self, task, bar):
        self.task = task
        self.bar = bar

    def run(self, total_path):
        if os.path.exists(total_path):
            raise TaskExistError(task=self.task)
        try:
            base_dir = os.path.dirname(total_path)
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)

            self.bar.init_bar(self.task.get_total(), self.task.get_relative_path())

            with open(total_path, "wb") as f:
                for data in self.task.iter_data(chunk_size=self.chunk_size):
                    while data:
                        step = data[: self.step_size]
                        f.write(step)
                        data = data[self.step_size :]
                        self.bar.update(len(step))
        except Exception as e:
            raise TaskFailError(task=self.task, msg=str(e), code=type(e))
        finally:
            self.bar.close()


class FileSystemTransferManager:
    def __init__(self, path):
        self.path = path

    def _iter_localpaths(self):
        base_path, _ = os.path.split(self.path)
        for p in iter_path(self.path):
            relative_path = p[len(base_path) :]
            yield p, relative_path

    @classmethod
    def get_transfer(cls, conf, path, args):
        FileSystemTransferUploadTask.chunk_size = args.chunk_size
        FileSystemTransferUploadTask.step_size = args.step_size
        return cls(path=path)

    def iter_tasks(self):
        for l, r in self._iter_localpaths():
            yield FileSystemTransferDownloadTask(l, r)

    def get_worker(self, task):
        total_path = norm_path(self.path, task.get_relative_path())

        def worker(bar):
            w = FileSystemTransferUploadTask(task, bar)
            w.run(total_path=total_path)

        return worker
