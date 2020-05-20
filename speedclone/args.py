import argparse
import json
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument("-S", "--sleep-time", default=0.1, type=int)
    parser.add_argument("-W", "--workers", default=5, type=int)
    parser.add_argument("--chunk-size", default=30 * (1024 ** 2), type=int)
    parser.add_argument("--step-size", default=1024 ** 2, type=int)
    parser.add_argument("--bar", default="common", type=str)
    parser.add_argument("--conf", default="./speedclone.json", type=str)

    args, rest = parser.parse_known_args()

    args.conf = os.path.join(BASE_DIR, "..", args.conf)
    if os.path.exists(args.conf):
        conf_json = json.load(open(args.conf, "r"))
        config = conf_json.get("configs")
        transfers = conf_json.get("transfers")
        bars = conf_json.get("bar")

        if not config:
            print("Missing configs")
            return

        if not transfers:
            print("Missing transfers")
            return

        args_dict = vars(args)

        for k in config.keys():
            config[k].update(args_dict)

        return args, rest[:2], config, transfers, bars
    else:
        print("Config file does not exist.")
