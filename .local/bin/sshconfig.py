#!/usr/bin/python3

import os
import argparse

# read the content of ~/.ssh/config
# if file not found, make text an empty string
try:
    with open(os.path.expanduser("~/.ssh/config")) as f:
        text = f.read()
except FileNotFoundError:
    text = ""

sshconfig = {}
for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    if line.startswith("Host "):
        curr_host = line.split(" ")[1]
        sshconfig[curr_host] = {}
    else:
        if "=" in line:
            key, value = line.split("=", 1)
        else:
            key, value = line.split(" ", 1)
        sshconfig[curr_host][key] = value

if __name__ == '__main__':

    if not sshconfig:
        print("No hosts found in ~/.ssh/config")
        exit()

    parser = argparse.ArgumentParser()
    parser.add_argument('host', help='The host to display the configuration for', type=str, nargs='?',
                        # available hosts: sshconfig.keys()
                        choices=sshconfig.keys())
    parser.add_argument('--all', help='Display all hosts', action='store_true')

    args = parser.parse_args()

    if args.all:
        for host in sshconfig.keys():
            print(f"Host {host}")
            for key, value in sshconfig[host].items():
                print(f"    {key} {value}")
    elif args.host:
        print(f"Host {args.host}")
        for key, value in sshconfig[args.host].items():
            print(f"    {key} {value}")
    else:
        parser.print_help()
        parser.exit()
