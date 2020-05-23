import os
import requests
from urllib.parse import unquote


class HttpTransferDownloadTask:
    http = {}

    def __init__(self, url, relative_path):
        self.url = url
        self.relative_path = relative_path
        self.r = None

    def iter_data(self, chunk_size=(10 * 1024 ** 2)):
        if not self.r:
            self.r = requests.get(self.url, stream=True, **self.http)
        try:
            self.r.raise_for_status()
            yield from self.r.iter_content(chunk_size=chunk_size)
        finally:
            self.r.close()

    def get_relative_path(self):
        return self.relative_path

    def get_total(self):
        self.r = requests.get(self.url, stream=True, **self.http)
        try:
            self.r.raise_for_status()
            size = int(self.r.headers.get("Content-Length", 0))
        except Exception as e:
            self.r.close()
            raise e
        else:
            return size


class HttpTransferManager:
    def __init__(self, path):
        self.path = path

    def _iter_urls(self):
        if self.path.startswith("http://") or self.path.startswith("https://"):
            yield self.path, unquote(os.path.basename(self.path))
        elif os.path.exists(self.path) and os.path.isfile(self.path):
            with open(self.path, "r") as f:
                while True:
                    url = f.readline().rstrip("\n")
                    if url:
                        resource_name = unquote(os.path.basename(url))
                        yield url, resource_name
                    else:
                        return
        else:
            raise Exception("Source not illegal")

    @classmethod
    def get_transfer(cls, conf, path, args):
        HttpTransferDownloadTask.chunk_size = args.chunk_size
        HttpTransferDownloadTask.http = conf.get("http", {})
        return cls(path=path)

    def iter_tasks(self):
        for url, name in self._iter_urls():
            yield HttpTransferDownloadTask(url, name)

    def get_worker(self, task):
        pass
