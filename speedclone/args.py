import argparse
import json
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-I",
        "--interval",
        default=0,
        type=int,
        help="Interval time when putting workers into thread pool.",
    )

    parser.add_argument(
        "--client-sleep",
        default=0,
        type=int,
        help="Time to sleep when client has been throttled.",
    )

    parser.add_argument(
        "-W", "--workers", default=5, type=int, help="The number of workers."
    )

    parser.add_argument(
        "-C",
        "--chunk-size",
        default=30 * (1024 ** 2),
        type=int,
        help="Size of single request in multiple chunk uploading.",
    )

    parser.add_argument(
        "-S",
        "--step-size",
        default=1024 ** 2,
        type=int,
        help="Size of chunk when updating the progress bar.",
    )

    parser.add_argument(
        "-B", "--bar", default="common", type=str, help="Name of the progress bar."
    )

    parser.add_argument(
        "--conf",
        default=os.path.join(BASE_DIR, "..", "speedclone.json"),
        type=str,
        help="Path to the config file.",
    )

    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy file through drive, can only use with Google Drive.",
    )

    parser.add_argument(
        "--max-page-size",
        default=100,
        type=int,
        help="Max size of single page when listing files.",
    )

    args, rest = parser.parse_known_args()

    if os.path.exists(args.conf):
        conf_json = json.load(open(args.conf, "r"))
        config = conf_json.get("configs")
        transfers = conf_json.get("transfers")
        bars = conf_json.get("bar")

        if not config:
            raise Exception("Missing configs")

        if not transfers:
            raise Exception("Missing transfers")

        args_dict = vars(args)

        for k in config.keys():
            config[k].update(args_dict)

        return args, rest, config, transfers, bars
    else:
        raise Exception("Config file does not exist.")
