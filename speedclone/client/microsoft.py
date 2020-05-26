import json
import os
import time
from threading import Lock, Thread
from urllib.parse import quote

import requests


class FileSystemTokenBackend:
    token_url = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    lock = Lock()

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

    def _refresh_accesstoken(self):
        with self.lock:
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
