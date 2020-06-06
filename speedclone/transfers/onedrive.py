import os
import random
from json import JSONDecodeError

import requests
from requests.exceptions import HTTPError

from ..client.microsoft import FileSystemTokenBackend, OneDrive
from ..error import TaskExistError, TaskFailError
from ..utils import DataIter, iter_path, norm_path


class OneDriveTransferDownloadTask:
    # TODO
    pass


class OneDriveTransferUploadTask:
    chunk_size = 10 * 1024 ** 2
    step_size = 1024 ** 2

    def __init__(self, task, bar, client):
        self.task = task
        self.bar = bar
        self.client = client

    def _handle_request_error(self, request):
        if request.status_code == 429:
            sleep_time = request.headers.get("Retry-After")
            seconds = self.client.sleep(sleep_time)
            raise Exception("Client Limit Exceeded. Sleep for {}s".format(seconds))

        try:
            request.raise_for_status()
        except HTTPError as e:
            status_code = e.response.status_code
            try:
                message = (
                    e.response.json().get("error", {}).get("message", "Empty message")
                )
            except JSONDecodeError:
                message = ""
            raise Exception("HttpError {}: {}".format(status_code, message))

    def run(self, remote_path):
        if self.client.sleeping:
            raise TaskFailError(
                task=self.task, msg="Client is sleeping, will retry later."
            )

        try:
            upload_url_request = self.client.get_upload_url(remote_path)
        except Exception as e:
            raise TaskFailError(exce=e, task=self.task, msg=str(e))
        else:
            if upload_url_request is False:
                raise TaskExistError(task=self.task)

        try:
            self._handle_request_error(upload_url_request)

            upload_url = upload_url_request.json()["uploadUrl"]
            file_size = self.task.get_total()

            self.bar.init_bar(file_size, self.task.get_relative_path())

            for i, file_piece in enumerate(
                self.task.iter_data(chunk_size=self.chunk_size)
            ):
                chunk_length = len(file_piece)
                start = i * self.chunk_size

                data = DataIter(file_piece, self.step_size, self.bar)
                headers = {
                    "Content-Range": "bytes {}-{}/{}".format(
                        start, start + chunk_length - 1, file_size,
                    ),
                    "Content-Length": str(chunk_length),
                }

                r = requests.put(upload_url, data=data, headers=headers,)

                if r.status_code not in (201, 202):
                    self._handle_request_error(r)
                    raise Exception("Unknown Error: " + str(r))

        except Exception as e:
            raise TaskFailError(exce=e, task=self.task, msg=str(e))
        finally:
            self.bar.close()


class OneDriveTransferManager:
    def __init__(self, path, clients):
        self.path = path
        self.clients = clients

    def _get_client(self):
        while True:
            _client = self.clients[0]
            self.clients = self.clients[1:] + self.clients[:1]
            if _client.sleeping:
                continue
            else:
                return _client

    @classmethod
    def get_transfer(cls, conf, path, args):
        OneDriveTransferUploadTask.chunk_size = args.chunk_size
        OneDriveTransferUploadTask.step_size = args.step_size
        OneDrive.sleep_time = args.sleep

        token_path = conf.get("token_path")
        if os.path.exists(token_path):
            drive = conf.get("drive_id")
            cred = conf.get("client")

            clients = []

            for p in iter_path(token_path):
                token_backend = FileSystemTokenBackend(cred=cred, token_path=p)
                client = OneDrive(token_backend=token_backend, drive=drive)
                clients.append(client)

            random.shuffle(clients)
            return cls(path=path, clients=clients)
        else:
            raise Exception("Token path not exists")

    def iter_tasks(self):
        pass

    def get_worker(self, task):

        total_path = norm_path(self.path, task.get_relative_path())
        try:
            client = self._get_client()

            def worker(bar):
                w = OneDriveTransferUploadTask(task, bar, client)
                w.run(total_path)

            return worker
        except Exception as e:
            _error = e

            def worker(bar):
                raise TaskFailError(exce=_error, task=task, msg=str(_error))

            return worker
