import json
import os
import random
import time
from threading import Lock, Thread
from urllib.parse import quote

import requests

from ..error import TaskExistError, TaskFailError
from ..utils import DataIter, iter_path, norm_path, with_lock

_onedrive_token_write_lock = Lock()


class FileSystemTokenBackend:
    token_url = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    def __init__(self, token_path, cred, tenant=None):
        self.token_path = token_path
        self.client = cred
        self.token_url = self.token_url.format(tenant=tenant if tenant else "common")

        if os.path.exists(self.token_path):
            with open(self.token_path, "r") as f:
                self.token = json.load(f)
        else:
            raise Exception("No token file found.")

    def _update_tokenfile(self):
        with open(self.token_path, "w") as f:
            json.dump(self.token, f)

    def _token_expired(self):
        if self.token:
            expired_time = self.token.get("expires_in") + self.token.get("get_time", 0)
            return expired_time <= int(time.time())
        else:
            return True

    @with_lock(_onedrive_token_write_lock)
    def _refresh_accesstoken(self):
        now_time = int(time.time())

        refresh_token = self.token.get("refresh_token")
        scope = self.token.get("scope")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": scope,
        }
        data.update(self.client)

        r = requests.post(self.token_url, data=data)
        r.raise_for_status()

        self.token = r.json()
        self.token["get_time"] = now_time
        self._update_tokenfile()

    def get_token(self):
        if self._token_expired():
            self._refresh_accesstoken()
        return self.token.get("access_token")


class OneDrive:

    api_url = "https://graph.microsoft.com/v1.0"
    sleep_time = 10

    def __init__(self, token_backend, proxies=None, drive=None):
        self.token_backend = token_backend
        self.proxies = proxies
        self.drive = "/drives/" + drive if drive else "/me/drive"
        self.sleeping = False

    def get_headers(self, content_type="application/json"):
        headers = {
            "Authorization": "Bearer {}".format(self.token_backend.get_token()),
            "Content-Type": content_type,
        }
        return headers

    def get_upload_url(self, remote_path):

        url = (
            self.api_url
            + self.drive
            + quote("/root:/{}:/createUploadSession".format(remote_path))
        )
        headers = self.get_headers()
        data = {"item": {"@microsoft.graph.conflictBehavior": "fail"}}

        r = requests.post(url, headers=headers, json=data)

        if r.status_code == 409:
            return False
        return r

    def sleep(self, seconds=None):
        if not seconds:
            seconds = self.sleep_time
        if not self.sleeping:

            def sleep():
                self.sleeping = True
                time.sleep(seconds)
                self.sleeping = False

            t = Thread(target=sleep)
            t.start()
        return seconds


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

        request.raise_for_status()

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
                raise TaskExistError(
                    task=self.task,
                    msg="{}: File already exists".format(self.task.get_relative_path()),
                )

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

                self.bar.close()
        except Exception as e:
            self.bar.close()
            raise TaskFailError(exce=e, task=self.task, msg=str(e))


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
        OneDrive.sleep_time = args.client_sleep

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
