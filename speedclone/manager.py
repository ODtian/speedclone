import time
from concurrent.futures import ThreadPoolExecutor, CancelledError

# from multiprocessing import JoinableQueue
from queue import Queue
from queue import Empty
from threading import Thread

from .error import TaskExistError, TaskFailError, TaskSleepError
from .utils import console_write


class TransferManager:
    def __init__(self, download_manager, upload_manager, bar_manager, sleep_time):
        self.download_manager = download_manager
        self.upload_manager = upload_manager
        self.bar_manager = bar_manager

        self.sleep_time = sleep_time

        self.pusher_thread = None
        self.pusher_finished = False

        self.task_queue = Queue()
        self.taskdone_queue = Queue()
        self.sleep_queue = Queue()

        self.futures = []

    def handle_sleep(self, e):
        self.task_queue.put(e.task)
        if not self.sleep_queue.empty():
            self.sleep_queue.put(e.sleep_time)
        self.bar_manager.sleep(e)

    def handle_error(self, e):
        self.task_queue.put(e.task)
        self.bar_manager.error(e)

    def handle_exists(self, e):
        self.bar_manager.exists(e)

    def handle_fail(self, e):
        self.task_queue.put(e.task)
        self.bar_manager.fail(e)

    def handle_done(self, result):
        self.bar_manager.done(result)

    def run_task_pusher(self):
        def pusher():
            for task in self.download_manager.iter_tasks():
                if self.pusher_finished:
                    return
                else:
                    self.task_queue.put(task)
                    self.taskdone_queue.put(0)
            self.pusher_finished = True

        self.pusher_thread = Thread(target=pusher)
        self.pusher_thread.start()

    def finished(self):
        return self.taskdone_queue.empty()

    def if_sleep(self):
        return not self.sleep_queue.empty()

    def sleep(self):
        sleep_time = self.sleep_queue.get()
        time.sleep(sleep_time)
        self.sleep_queue.task_done()

    def done_callback(self, task):
        result = None
        try:
            result = task.result()
        except CancelledError:
            pass
        except TaskExistError as e:
            self.handle_exists(e)
        except TaskSleepError as e:
            self.handle_sleep(e)
        except TaskFailError as e:
            self.handle_fail(e)
        except Exception as e:
            self.handle_error(e)
        else:
            self.handle_done(result)
        finally:
            if not self.taskdone_queue.empty():
                self.taskdone_queue.get()

    def clear_all_futueres(self):
        [f.cancel() for f in self.futures]

    def get_task(self):
        try:
            task = self.task_queue.get(timeout=self.sleep_time)
        except Empty:
            return
        else:
            return task

    def get_worker(self, task):
        _worker = self.upload_manager.get_worker(task)
        bar = self.bar_manager.get_bar(task)

        def worker():
            self.sleep_queue.join()
            return _worker(bar)

        return worker

    def add_to_excutor(self, executor):
        while True:
            if self.finished() and self.pusher_finished:
                break
            elif self.if_sleep():
                self.sleep()
            else:
                task = self.get_task()
                if not task:
                    continue
                worker = self.get_worker(task)
                future = executor.submit(worker)
                future.add_done_callback(self.done_callback)
                self.futures.append(future)
            time.sleep(self.sleep_time)

    def run(self, max_workers=None):
        self.run_task_pusher()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            try:
                self.add_to_excutor(executor)
            except KeyboardInterrupt:
                if not self.pusher_finished:
                    console_write("error", "Stopping pusher thread.")
                    self.pusher_finished = True
                    console_write("error", "Waitting pusher thread.")
                    self.pusher_thread.join()

                console_write("error", "Waitting worker threads.")
                self.clear_all_futueres()

        console_write("error", "Clearing queues.")
        self.sleep_queue.queue.clear()
        self.task_queue.queue.clear()
        self.taskdone_queue.queue.clear()
        self.bar_manager.exit()
