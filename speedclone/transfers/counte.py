class CountTransferManager:
    def __init__(self):
        pass

    @classmethod
    def get_transfer(cls, conf, path, args):
        return cls()

    def iter_tasks(self):
        pass

    def get_worker(self, task):
        def worker():
            pass

        return worker
