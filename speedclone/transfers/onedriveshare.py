from urllib.parse import parse_qs, unquote

import requests

from ..utils import console_write
from threading import Thread
from queue import Queue


class OneDriveShareTransferDownloadTask:
    http = {}

    def __init__(self, url, relative_path, size, session):
        self.url = url
        self.relative_path = relative_path
        self.size = size
        self.s = session

    def iter_data(self, chunk_size=(10 * 1024 ** 2)):
        with self.s.get(self.url, stream=True, **self.http) as r:
            r.raise_for_status()
            yield from r.iter_content(chunk_size=chunk_size)

    def get_relative_path(self):
        return self.relative_path

    def get_total(self):
        return self.size


class OneDriveShareTransferManager:
    headers = {"Content-Type": "application/json;odata=verbose"}
    base_list_url = "/_api/web/{list_func}/RenderListDataAsStream"
    list_data = {
        "parameters": {
            "__metadata": {"type": "SP.RenderListDataParameters"},
            "AddRequiredFields": True,
        }
    }
    file_xml = (
        '<View Scope="RecursiveAll">'
        "<Query><Where><Eq>"
        '<FieldRef Name="FileRef" /><Value Type="Text">'
        "<![CDATA[{file_path}]]>"
        "</Value></Eq></Where></Query>"
        '<RowLimit Paged="True">1</RowLimit>'
        "</View>"
    )

    def __init__(self, path, is_folder):
        self.path = path
        self.is_folder = is_folder
        self.s = requests.Session()
        self.task_q = None

        split_url = self.path.lstrip("http://").lstrip("https://").split("/")
        tenant_name, account_name = split_url[0], split_url[4]

        base_url = "https://{tenant_name}/personal/{account_name}".format(
            tenant_name=tenant_name, account_name=account_name
        )
        base_list_url = self.base_list_url.format(
            list_func=(
                "GetListUsingPath(DecodedUrl=@a1)" if self.is_folder else "GetList(@a1)"
            )
        )

        self.url = base_url + base_list_url
        self.download_url = base_url + "/_layouts/15/download.aspx?UniqueId={unique_id}"

        self.base_document_path = "/personal/{account_name}/Documents".format(
            account_name=account_name
        )
        self.base_list_params = {
            "@a1": "'{folder}'".format(folder=self.base_document_path)
        }

        self.ref_path = (
            self.s.get(self.path)
            .history[0]
            .headers["Location"]
            .split("/")[7]
            .split("&")[0]
            .lstrip("onedrive.aspx?id=")
        )

        if self.is_folder:
            self.ref_path = "/" + "/".join(self.ref_path.split("%2F")[4:])

            self.list_data["parameters"].update(
                {
                    "AllowMultipleValueFilterForTaxonomyFields": True,
                    "RenderOptions": 464647,
                }
            )
        else:
            file_xml = self.file_xml.format(file_path=unquote(self.ref_path, "utf-8"))
            self.list_data["parameters"].update(
                {"ViewXml": file_xml, "RenderOptions": 12295}
            )

    def _iter_items(self, ref_path, add_params=None):
        try:
            params = {
                **self.base_list_params,
                **(
                    add_params
                    or (
                        {"RootFolder": self.base_document_path + ref_path}
                        if self.is_folder
                        else {"View=": ""}
                    )
                ),
            }

            result = self.s.post(
                self.url, headers=self.headers, json=self.list_data, params=params,
            )
            list_data = result.json()["ListData"]

            folders = []

            for row in list_data["Row"]:
                is_folder = row[".fileType"] == "" and row[".hasPdf"] == ""
                path = "/".join(row["FileRef"].split("/")[4:])

                if is_folder:
                    folder_path = "/" + path
                    folders.append(folder_path)
                else:
                    unique_id = row["UniqueId"].lstrip("{").rstrip("}")
                    download_url = self.download_url.format(unique_id=unique_id)
                    size = int(row["FileSizeDisplay"])
                    yield download_url, path, size

            self.list_data["parameters"]["RenderOptions"] = 167943

            next_href = list_data.get("NextHref")

            if next_href:
                params = parse_qs(next_href)
                yield from self._iter_items(ref_path, add_params=params)

            for folder_path in folders:
                yield from self._iter_items(folder_path)

        except Exception as e:
            console_write(mode="error", message="{}: {}".format(ref_path, str(e)))
            yield from self._iter_items(ref_path)

    @classmethod
    def get_transfer(cls, conf, path, args):
        OneDriveShareTransferDownloadTask.chunk_size = args.chunk_size
        OneDriveShareTransferDownloadTask.http = conf.get("http", {})
        is_folder = conf.get("is_folder", False)
        return cls(path=path, is_folder=is_folder)

    def iter_tasks(self):
        self.task_q = Queue()

        def pusher():
            for url, name, size in self._iter_items(self.ref_path):
                t = OneDriveShareTransferDownloadTask(url, name, size, self.s)
                self.task_q.put(t)
                self.task_q.put(None)

        thread = Thread(target=pusher)
        thread.setDaemon(True)
        thread.start()

        while True:
            t = self.task_q.get()
            if t is None:
                break
            else:
                yield t

    def get_worker(self, task):
        pass
