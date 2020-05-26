import json
import os
import time
from threading import Lock, Thread

import jwt
import requests


class FileSystemTokenBackend:
    token_url = "https://oauth2.googleapis.com/token"
    http = {}
    lock = Lock()

    def __init__(self, token_path, cred):
        self.token_path = token_path
        self.client = cred

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

    def _refresh_accesstoken(self):
        with self.lock:
            now_time = int(time.time())
            refresh_token = self.token.get("refresh_token")

            data = {"refresh_token": refresh_token, "grant_type": "refresh_token"}
            data.update(self.client)

            r = requests.post(self.token_url, data=data, **self.http)
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

    def __init__(self, cred_path):
        self.cred_path = cred_path
        self.token = {}
        self.lock = Lock()

        if os.path.exists(self.cred_path):
            with open(self.cred_path, "r") as f:
                self.config = json.load(f)
        else:
            raise Exception("No cred file found.")

    def _refresh_accesstoken(self):
        with self.lock:
            now_time = int(time.time())
            token_data = {
                "iss": self.config["client_email"],
                "scope": self.scope,
                "aud": self.token_url,
                "exp": now_time + self.expires_in,
                "iat": now_time,
            }

            auth_jwt = jwt.encode(
                token_data,
                self.config["private_key"].encode("utf-8"),
                algorithm="RS256",
            )
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": auth_jwt,
            }
            r = requests.post(self.token_url, data=data, **self.http)
            r.raise_for_status()
            self.token = r.json()
            self.token["get_time"] = now_time


class GoogleDrive:

    drive_url = "https://www.googleapis.com/drive/v3/files"
    drive_upload_url = "https://www.googleapis.com/upload/drive/v3/files"
    sleep_time = 10
    http = {}

    def __init__(self, token_backend, drive=None):
        self.token_backend = token_backend
        self.drive = drive
        self.sleeping = False

    def get_headers(self, content_type="application/json"):
        headers = {
            "Authorization": "Bearer {}".format(self.token_backend.get_token()),
            "Content-Type": content_type,
        }
        headers.update(self.http.get("headers", {}))
        return headers

    def get_params(self, params={}):
        params.update({"supportsAllDrives": "true"})
        if self.drive:
            params.update(
                {
                    "corpora": "drive",
                    "includeItemsFromAllDrives": "true",
                    "driveId": self.drive,
                }
            )
        return params

    def create_file_by_name(
        self, parent_id, name, mime="application/vnd.google-apps.folder"
    ):
        params = {"supportsAllDrives": "true"}
        data = {"name": name, "parents": [parent_id], "mimeType": mime}
        headers = self.get_headers()
        r = requests.post(
            self.drive_url, headers=headers, params=params, json=data, **self.http
        )
        return r

    def get_files_by_p(self, params):
        headers = self.get_headers()
        r = requests.get(
            self.drive_url, headers=headers, params=self.get_params(params), **self.http
        )
        return r

    def get_files_by_name(
        self,
        parent_id,
        name=None,
        mime="folder",
        fields=("files/id", "files/name", "files/mimeType"),
    ):
        p = {
            "q": " and ".join(
                [
                    "'{parent_id}' in parents",
                    "name = '{name}'",
                    "mimeType {mime} 'application/vnd.google-apps.folder'",
                    "trashed = false",
                ]
            ).format(
                parent_id=parent_id,
                name=name.replace("'", r"\'"),
                mime=("=" if mime == "folder" else "!="),
            ),
            "fields": ", ".join(fields),
        }
        r = self.get_files_by_p(p)
        return r

    def get_upload_url(self, parent_id, name):
        exist_file = (
            self.get_files_by_name(parent_id, name, mime="file", fields=("files/kind",))
            .json()
            .get("files", [])
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
            **self.http
        )
        return r

    def get_file(self, file_id, fields):
        params = {"fields": fields, "supportsAllDrives": "true"}
        headers = self.get_headers()
        r = requests.get(
            self.drive_url + "/" + file_id, headers=headers, params=params, **self.http
        )
        return r

    def get_download_request(self, file_id):
        params = {"alt": "media", "supportsAllDrives": "true"}
        headers = self.get_headers()
        r = requests.get(
            self.drive_url + "/" + file_id,
            headers=headers,
            params=params,
            stream=True,
            **self.http
        )
        return r

    def copy_to(self, source_id, dest_id, name):
        exist_file = (
            self.get_files_by_name(dest_id, name, mime="file", fields=("files/kind",))
            .json()
            .get("files", [])
        )
        if exist_file:
            return False

        params = {"supportsAllDrives": "true"}
        data = {"name": name, "parents": [dest_id]}
        headers = self.get_headers()
        r = requests.post(
            self.drive_url + "/" + source_id + "/copy",
            headers=headers,
            json=data,
            params=params,
            **self.http
        )
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
