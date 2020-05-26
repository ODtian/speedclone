class CountTransferManager:
    def __init__(self):
        pass

    @classmethod
    def get_transfer(cls, conf, path, args):
        return cls()

    def iter_tasks(self):
        pass

    def get_worker(self, task):
        def worker(bar):
            file_size = task.get_total()
            relative_path = task.get_relative_path()
            bar.init_bar(file_size, relative_path)
            bar.update(file_size)
            bar.close()

        return worker
