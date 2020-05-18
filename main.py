import importlib

from speedclone.args import parse_args
from speedclone.bar import BarManager
from speedclone.manager import TransferManager

BASE_IMPORT_PATH = "speedclone.transfers."


def handle_rest(s):
    a = s.split(":/")
    return a.pop(0), ":/".join(a)


def main():
    args, rest, config, transfers = parse_args()

    f, t = rest
    f_name, f_path = handle_rest(f)
    t_name, t_path = handle_rest(t)

    f_conf = config.get(f_name)
    t_conf = config.get(t_name)

    f_trans = transfers.get(f_conf.get("transfer"))
    t_trans = transfers.get(t_conf.get("transfer"))

    from_transfer = getattr(
        importlib.import_module(BASE_IMPORT_PATH + f_trans.get("mod")),
        f_trans.get("cls"),
    ).get_transfer(f_conf, f_path)

    to_transfer = getattr(
        importlib.import_module(BASE_IMPORT_PATH + t_trans.get("mod")),
        t_trans.get("cls"),
    ).get_transfer(t_conf, t_path)

    bar_manager = BarManager()
    transfer_manager = TransferManager(
        download_manager=from_transfer,
        upload_manager=to_transfer,
        bar_manager=bar_manager,
        sleep_time=args.sleep_time,
    )
    transfer_manager.run(max_workers=args.workers)


if __name__ == "__main__":
    main()
