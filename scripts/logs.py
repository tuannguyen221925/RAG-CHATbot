"""Follow local logs, reopening on rotation so Windows does not lock the file."""
import argparse
import sys
from collections import deque
from threading import Event

from api.db import ROOT  # Loads the project's .env.
from api.observability import configure_console, log_directory


def follow_log(path, stop, last=0):
    position, identity = None, None
    while not stop.is_set():
        try:
            stat = path.stat()
            current = (stat.st_dev, stat.st_ino)
            if identity is not None and identity != current or position is not None and stat.st_size < position:
                position = 0
            with path.open(encoding='utf-8', errors='replace') as stream:
                if position is None:
                    text = ''.join(deque(stream, maxlen=last)) if last else ''
                    stream.seek(0, 2)
                else:
                    stream.seek(position)
                    text = stream.read()
                position = stream.tell()
            identity = current
            if text:
                print(text, end='', flush=True)
        except FileNotFoundError:
            # If created after following starts, show its first entries too.
            position, identity = 0, None
        stop.wait(0.2)


def main():
    configure_console()
    parser = argparse.ArgumentParser(description='Theo dõi log BIG_RAG; Ctrl+C để dừng.')
    parser.add_argument('--name', choices=['api', 'api-error', 'dev'], default='api')
    args = parser.parse_args()
    path = log_directory() / (args.name + '.log')
    print(f'Log: {path}', flush=True)
    try:
        follow_log(path, Event(), last=50)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
