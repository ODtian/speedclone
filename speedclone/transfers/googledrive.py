import os
import random
from json.decoder import JSONDecodeError

import requests
from requests.exceptions import HTTPError

from ..client.google import (
    FileSystemServiceAccountTokenBackend,
    FileSystemTokenBackend,
    GoogleDrive,
)
from ..error import TaskExistError, TaskFailError
from ..utils import DataIter, console_write, iter_path, norm_path


class GoogleDriveTransferDownloadTask:
    http = {}

    def __init__(self, file_id, relative_path, size, client):
        self.file_id = file_id
        self.relative_path = relative_path
        self.size = size
        self.client = client

    def iter_data(self, chunk_size=(10 * 1024 ** 2), copy=False):
        if copy:
            yield self.file_id
        else:
            with self.client.get_download_request(self.file_id) as r:
                r.raise_for_status()
                yield from r.iter_content(chunk_size=chunk_size)

    def get_relative_path(self):
        return self.relative_path

    def get_total(self):
        return self.size


class GoogleDriveTransferUploadTask:
    chunk_size = 10 * 1024 ** 2
    step_size = 1024 ** 2
    http = {}

    def __init__(self, task, bar, client):
        self.task = task
        self.bar = bar
        self.client = client

    def _handle_request_error(self, request):
        if request.status_code == 429:
            sleep_time = request.headers.get("Retry-After")
            seconds = self.client.sleep(sleep_time)
            raise Exception("Client Limit Exceeded. Sleep for {}s".format(seconds))

        if request.status_code == 400 and "LimitExceeded" in request.text:
            seconds = self.client.sleep()
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

    def _do_copy(self, folder_id, name):
        if self.client.sleeping:
            raise TaskFailError(
                task=self.task, msg="Client is sleeping, will retry later."
            )

        try:
            file_size = self.task.get_total()
            self.bar.init_bar(file_size, self.task.get_relative_path())
            for file_id in self.task.iter_data(copy=True):
                result = self.client.copy_to(file_id, folder_id, name)
                if result is not False:
                    self._handle_request_error(result)
        except Exception as e:
            raise TaskFailError(exce=e, task=self.task, msg=str(e))
        else:
            if result is False:
                raise TaskExistError(task=self.task)
        finally:
            self.bar.update(file_size)
            self.bar.close()

    def run(self, folder_id, name):
        if self.client.sleeping:
            raise TaskFailError(
                task=self.task, msg="Client is sleeping, will retry later."
            )

        try:
            upload_url_request = self.client.get_upload_url(folder_id, name)
        except Exception as e:
            raise TaskFailError(exce=e, task=self.task, msg=str(e))
        else:
            if upload_url_request is False:
                raise TaskExistError(task=self.task)

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
                end = start + chunk_length - 1
                headers = {
                    "Content-Range": "bytes {}-{}/{}".format(start, end, file_size),
                    "Content-Length": str(chunk_length),
                }

                data = DataIter(file_piece, self.step_size, self.bar)

                r = requests.put(
                    upload_url, data=data, headers=headers, **self.client.http
                )

                self._handle_request_error(r)

                if r.status_code == 308:
                    header_range = r.headers.get("Range")
                    if not header_range or header_range.lstrip("bytes=0-") != str(end):
                        raise Exception("Upload Error: Range missing")

                elif "id" not in r.json().keys():
                    raise Exception("Upload Error: Upload not successful")

        except Exception as e:
            raise TaskFailError(exce=e, task=self.task, msg=str(e))
        finally:
            self.bar.close()


class GoogleDriveTransferManager:
    max_page_size = 100

    def __init__(self, path, clients, root):
        self.path = path
        self.clients = clients
        self.path_dict = {"/": root}
        self.root_path, self.base_name = os.path.split(self.path)

    def _get_client(self):
        while True:
            client = self.clients.pop(0)
            self.clients.append(client)
            if client.sleeping:
                continue
            else:
                return client

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
                    client.get_files_by_name(
                        base_folder_id, dir_name, fields=("files/id",)
                    )
                    .json()
                    .get("files")
                )
                if has_folder:
                    folder_id = has_folder[0].get("id")
                else:
                    folder = client.create_file_by_name(base_folder_id, dir_name).json()
                    folder_id = folder.get("id")
                self.path_dict[p] = folder_id
        return self.path_dict[p]

    def _get_root_name(self):
        client = self._get_client()
        root_id = self.path_dict["/"]
        r = client.get_file(root_id, "name")
        return r.json()["name"]

    def _list_files(self, path):
        client = self._get_client()
        dir_path, name = os.path.split(path)
        parent_dir_id = self._get_dir_id(client, dir_path)
        is_file = (
            client.get_files_by_name(
                parent_dir_id,
                name,
                mime="file",
                fields=("files/id", "files/name", "files/mimeType", "files/size"),
            )
            .json()
            .get("files", [])
        )
        for i in is_file:
            yield i.get("id", ""), i.get("name", ""), int(i.get("size", 0))

    def _list_dirs(self, path, page_token=None, client=None):
        try:
            client = client or self._get_client()

            abs_path = norm_path(self.root_path, path)
            dir_id = self._get_dir_id(client, abs_path)

            p = {
                "q": " and ".join(
                    ["'{parent_id}' in parents", "trashed = false"]
                ).format(parent_id=dir_id),
                "pageSize": self.max_page_size,
                "fields": ", ".join(
                    (
                        "nextPageToken",
                        "files/id",
                        "files/name",
                        "files/size",
                        "files/mimeType",
                    )
                ),
            }

            if page_token:
                p.update({"pageToken": page_token})

            r = client.get_files_by_p(p)
            result = r.json()

            folders = []

            for file in result.get("files", []):
                relative_path = norm_path(path, file.get("name", ""))
                if file["mimeType"] == "application/vnd.google-apps.folder":
                    folders.append(relative_path)
                else:
                    file_id = file.get("id", "")
                    file_path = norm_path(self.root_name, relative_path)
                    file_size = int(file.get("size", 0))
                    yield file_id, file_path, file_size

            next_token = result.get("nextPageToken")

            if next_token:
                yield from self._list_dirs(path, next_token, client)

            for folder_path in folders:
                yield from self._list_dirs(folder_path)

        except Exception as e:
            console_write(mode="error", message="{}: {}".format(path, str(e)))
            yield from self._list_dirs(path)

    @classmethod
    def get_transfer(cls, conf, path, args):

        GoogleDriveTransferUploadTask.chunk_size = args.chunk_size
        GoogleDriveTransferUploadTask.step_size = args.step_size
        GoogleDrive.sleep_time = args.client_sleep
        cls.max_page_size = args.max_page_size

        if args.copy:
            GoogleDriveTransferUploadTask.run = GoogleDriveTransferUploadTask._do_copy

        GoogleDrive.http = conf.get("http", {})
        FileSystemTokenBackend.http = conf.get("http", {})

        token_path = conf.get("token_path")

        if os.path.exists(token_path):
            use_service_account = conf.get("service_account", False)

            root = conf.get("root")

            if conf.get("use_root_in_path"):
                _path = path.split("/")
                root = _path.pop(0)
                path = "/".join(_path)

            drive = conf.get("drive_id")
            cred = conf.get("client")

            clients = []

            for p in iter_path(token_path):
                if use_service_account:
                    token_backend = FileSystemServiceAccountTokenBackend(cred_path=p)
                else:
                    token_backend = FileSystemTokenBackend(cred=cred, token_path=p)
                client = GoogleDrive(token_backend=token_backend, drive=drive)
                clients.append(client)

            random.shuffle(clients)
            return cls(path=path, clients=clients, root=root)
        else:
            raise Exception("Token path not exists")

    def iter_tasks(self):
        for file_id, relative_path, size in self._list_files(self.path):
            yield GoogleDriveTransferDownloadTask(
                file_id, relative_path, size, self._get_client()
            )
            return

        self.root_name = "" if self.path else self._get_root_name()

        for file_id, relative_path, size in self._list_dirs(self.base_name):
            yield GoogleDriveTransferDownloadTask(
                file_id, relative_path, size, self._get_client()
            )

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
