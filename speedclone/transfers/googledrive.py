import json
import os
import random
import time
from threading import Lock, Thread

import jwt
import requests

from ..error import TaskExistError, TaskFailError
from ..utils import DataIter, iter_path, norm_path, with_lock

_google_token_write_lock = Lock()


class FileSystemTokenBackend:
    token_url = "https://oauth2.googleapis.com/token"

    def __init__(self, token_path, cred, proxies=None):
        self.token_path = token_path
        self.client = cred
        self.proxies = proxies

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

    @with_lock(_google_token_write_lock)
    def _refresh_accesstoken(self):
        now_time = int(time.time())
        refresh_token = self.token.get("refresh_token")

        data = {"refresh_token": refresh_token, "grant_type": "refresh_token"}
        data.update(self.client)

        r = requests.post(self.token_url, data=data, proxies=self.proxies)
        r.raise_for_status()

        self.token = r.json()
        self.token["get_time"] = now_time
        self._update_tokenfile()

    def get_token(self):
        if self._token_expired():
            self._refresh_accesstoken()
        return self.token.get("access_token")


class FileSystemServiceAccountTokenBackend(FileSystemTokenBackend):
    scope = "https://www.googleapis.com/auth/drive"
    expires_in = 3600

    def __init__(self, cred_path, proxies=None):
        self.cred_path = cred_path
        self.proxies = proxies

        self.token = {}
        if os.path.exists(self.cred_path):
            with open(self.cred_path, "r") as f:
                self.config = json.load(f)
        else:
            raise Exception("No cred file found.")

    @with_lock(_google_token_write_lock)
    def _refresh_accesstoken(self):
        now_time = int(time.time())
        token_data = {
            "iss": self.config["client_email"],
            "scope": self.scope,
            "aud": self.token_url,
            "exp": now_time + self.expires_in,
            "iat": now_time,
        }

        auth_jwt = jwt.encode(
            token_data, self.config["private_key"].encode("utf-8"), algorithm="RS256"
        )
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": auth_jwt,
        }
        r = requests.post(self.token_url, data=data, proxies=self.proxies)
        r.raise_for_status()
        self.token = r.json()
        self.token["get_time"] = now_time


class GoogleDrive:

    drive_url = "https://www.googleapis.com/drive/v3/files"
    drive_upload_url = "https://www.googleapis.com/upload/drive/v3/files"

    def __init__(self, token_backend, drive=None, proxies=None):
        self.token_backend = token_backend
        self.proxies = proxies
        self.drive = drive
        self.sleeping = False

    def get_headers(self, content_type="application/json"):
        headers = {
            "Authorization": "Bearer {}".format(self.token_backend.get_token()),
            "Content-Type": content_type,
        }
        return headers

    def create_file_by_name(
        self, parent_id, name, mime="application/vnd.google-apps.folder"
    ):
        params = {"supportsAllDrives": "true"}
        data = {"name": name, "parents": [parent_id], "mimeType": mime}
        headers = self.get_headers()
        r = requests.post(
            self.drive_url,
            headers=headers,
            params=params,
            json=data,
            proxies=self.proxies,
        )
        return r

    def get_files_by_name(self, parent_id, name, mime="folder"):
        params = {
            "q": "'{parent_id}' in parents and "
            "name = '{name}' and "
            "mimeType {mime} 'application/vnd.google-apps.folder' and "
            "trashed = false".format(
                parent_id=parent_id,
                mime=("=" if mime == "folder" else "!="),
                name=name.replace("'", r"\'"),
            ),
            "supportsAllDrives": "true",
        }
        if self.drive:
            params.update(
                {
                    "corpora": "drive",
                    "includeItemsFromAllDrives": "true",
                    "driveId": self.drive,
                }
            )
        headers = self.get_headers()
        r = requests.get(
            self.drive_url, headers=headers, params=params, proxies=self.proxies
        )
        return r

    def get_upload_url(self, parent_id, name):
        exist_file = (
            self.get_files_by_name(parent_id, name, mime="file").json().get("files", [])
        )
        if exist_file:
            return False

        params = {"uploadType": "resumable", "supportsAllDrives": "true"}
        headers = self.get_headers()
        data = {"name": name, "parents": [parent_id]}
        r = requests.post(
            self.drive_upload_url,
            headers=headers,
            json=data,
            params=params,
            proxies=self.proxies,
        )
        return r

    def sleep(self, seconds):
        if not self.sleeping:

            def sleep():
                self.sleeping = True
                time.sleep(seconds)
                self.sleeping = False

            t = Thread(target=sleep)
            t.start()


class GoogleDriveTransferDownloadTask:
    # TODO
    pass


class GoogleDriveTransferUploadTask:
    chunk_size = 10 * 1024 ** 2
    step_size = 1024 ** 2
    sleep_time = 10

    def __init__(self, task, bar, client):
        self.task = task
        self.bar = bar
        self.client = client

    def _handle_request_error(self, request):
        if request.status_code == 429:
            sleep_time = request.headers.get("Retry-After", self.sleep_time)
            self.client.sleep(sleep_time)
            raise Exception(
                "Client Limit Exceeded. Sleep for {}s".format(self.sleep_time)
            )

        if request.status_code == 400 and "LimitExceeded" in request.text:
            self.client.sleep(self.sleep_time)
            raise Exception(
                "Client Limit Exceeded. Sleep for {}s".format(self.sleep_time)
            )

        request.raise_for_status()

    def run(self, forlder_id, name):
        if self.client.sleeping:
            raise TaskFailError(
                task=self.task, msg="Client is sleeping, will retry later."
            )

        try:
            upload_url_request = self.client.get_upload_url(forlder_id, name)
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

            upload_url = upload_url_request.headers.get("Location")
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

                r = requests.put(
                    upload_url, data=data, headers=headers, proxies=self.client.proxies,
                )

                if r.status_code not in (200, 201, 308):
                    self._handle_request_error(r)
                    raise Exception("Unknown Error: " + str(r))

                self.bar.close()

        except Exception as e:
            self.bar.close()
            raise TaskFailError(exce=e, task=self.task, msg=str(e))


class GoogleDriveTransferManager:
    def __init__(self, path, clients, root):
        self.path_dict = {"/": root}
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

    def _reduce_path(self, path):
        now = ""
        for p in path.split("/"):
            now += "/" + p
            yield now

    def _get_dir_id(self, client, path):
        for p in self._reduce_path(path):
            if self.path_dict.get(p) is None:
                dir_path, dir_name = os.path.split(p)
                base_folder_id = self.path_dict[dir_path]
                has_folder = (
                    client.get_files_by_name(base_folder_id, dir_name)
                    .json()
                    .get("files")
                )
                if not has_folder:
                    folder = client.create_file_by_name(base_folder_id, dir_name).json()
                    folder_id = folder.get("id")
                else:
                    folder_id = has_folder[0].get("id")
                self.path_dict[p] = folder_id
        return self.path_dict[p]

    @classmethod
    def get_transfer(cls, conf, path):
        token_path = conf.get("token_path")
        if os.path.exists(token_path):
            use_service_account = conf.get("service_account", False)
            proxies = conf.get("proxies")

            root = conf.get("root")
            drive = conf.get("drive_id")
            cred = conf.get("client")

            clients = []

            for p in iter_path(token_path):
                if use_service_account:
                    token_backend = FileSystemServiceAccountTokenBackend(
                        cred_path=p, proxies=proxies
                    )
                else:
                    token_backend = FileSystemTokenBackend(
                        cred=cred, token_path=p, proxies=proxies
                    )
                client = GoogleDrive(
                    token_backend=token_backend, drive=drive, proxies=proxies
                )
                clients.append(client)
            random.shuffle(clients)
            return cls(path=path, clients=clients, root=root)
        else:
            raise Exception("Token path not exists")

    def iter_tasks(self):
        pass

    def get_worker(self, task):

        total_path = norm_path(self.path, task.get_relative_path())
        dir_path, name = os.path.split(total_path)
        try:
            client = self._get_client()
            dir_id = self._get_dir_id(client, dir_path)

            def worker(bar):
                w = GoogleDriveTransferUploadTask(task, bar, client)
                w.run(dir_id, name)

            return worker
        except Exception as e:
            _error = e

            def worker(bar):
                raise TaskFailError(exce=_error, task=task, msg=str(_error))

            return worker
