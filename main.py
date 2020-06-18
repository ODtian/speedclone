import importlib

from speedclone.args import parse_args
from speedclone.manager import TransferManager

TRANSFERS_BASE_IMPORT_PATH = "speedclone.transfers."
BARS_BASE_IMPORT_PATH = "speedclone.bar."


def handle_rest(s):
    a = s.split(":/")
    return a.pop(0), ":/".join(a)


def main():
    args, rest, config, transfers, bars = parse_args()

    f, t = rest[0], rest[1]
    f_name, f_path = handle_rest(f)
    t_name, t_path = handle_rest(t)

    f_conf = config.get(f_name)
    t_conf = config.get(t_name)

    if not f_conf or not t_conf:
        raise Exception(
            "Could not find config named '{}'".format(
                "' and '".join(
                    filter(
                        None, [("" if f_conf else f_name), ("" if t_conf else t_name)]
                    )
                )
            )
        )

    f_trans_name = f_conf.get("transfer")
    t_trans_name = t_conf.get("transfer")

    if args.copy and (f_trans_name != "gd" or t_trans_name != "gd"):
        raise Exception(
            "Copy mode only support Google Drive, please check your config."
        )

    f_trans = transfers.get(f_trans_name)
    t_trans = transfers.get(t_trans_name)
    from_transfer = getattr(
        importlib.import_module(TRANSFERS_BASE_IMPORT_PATH + f_trans.get("mod")),
        f_trans.get("cls"),
    ).get_transfer(f_conf, f_path, args)

    to_transfer = getattr(
        importlib.import_module(TRANSFERS_BASE_IMPORT_PATH + t_trans.get("mod")),
        t_trans.get("cls"),
    ).get_transfer(t_conf, t_path, args)

    bar = bars.get(args.bar)
    bar_manager = getattr(
        importlib.import_module(BARS_BASE_IMPORT_PATH + bar.get("mod")), bar.get("cls"),
    ).get_bar_manager()

    transfer_manager = TransferManager(
        download_manager=from_transfer,
        upload_manager=to_transfer,
        bar_manager=bar_manager,
        sleep_time=args.interval,
        max_workers=args.workers,
    )
    transfer_manager.run()


if __name__ == "__main__":
    main()
