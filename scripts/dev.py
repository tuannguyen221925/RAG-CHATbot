"""One development command for Python API and the Vite frontend."""
import json
import logging
import logging.config
import os
import re
import subprocess
import sys
import time
from threading import Event, Thread
from urllib.error import URLError
from urllib.request import urlopen

from api.db import ROOT
from api.observability import configure_console, log_directory, logging_config
from scripts.logs import follow_log

logger = logging.getLogger(__name__)


def frontend_output(process):
    for line in process.stdout:
        print(line, end='', flush=True)
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line).rstrip()
        if text:
            logging.getLogger('dev.frontend').info('Vite | %s', text)


def healthy(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=2) as response:
            return json.load(response).get('backend') == 'python'
    except (URLError, OSError, ValueError):
        return False


def main():
    configure_console()
    os.chdir(ROOT)
    logging.config.dictConfig(logging_config('dev'))
    port = int(os.getenv('WEB_PORT', '8501'))
    backend = frontend = None
    stop, threads = Event(), []
    logger.info('Logs: %s (api.log, api-error.log, dev.log)', log_directory())
    try:
        if healthy(port):
            logger.info('Using Python API already running on http://127.0.0.1:%s; following api.log in this terminal', port)
            follower = Thread(target=follow_log, args=(log_directory() / 'api.log', stop), daemon=True)
            follower.start()
            threads.append(follower)
        else:
            logger.info('Starting Python API on http://127.0.0.1:%s ...', port)
            backend = subprocess.Popen([sys.executable, '-u', '-m', 'scripts.serve'], cwd=ROOT,
                                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            deadline = time.monotonic() + 90
            while not healthy(port):
                if backend.poll() is not None:
                    raise RuntimeError(f'Python API failed to start. See {log_directory() / "api-error.log"}')
                if time.monotonic() >= deadline:
                    raise RuntimeError('Python API did not become ready within 90 seconds. Check MySQL and .env.')
                time.sleep(0.5)
        frontend = subprocess.Popen(['node', str(ROOT / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', *sys.argv[1:]], cwd=ROOT,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        output = Thread(target=frontend_output, args=(frontend,), daemon=True)
        output.start()
        threads.append(output)
        while frontend.poll() is None:
            if backend is not None and backend.poll() is not None:
                raise RuntimeError('Python API stopped. Restart npm run dev after fixing the backend error.')
            time.sleep(0.5)
        return frontend.returncode
    except KeyboardInterrupt:
        return 0
    finally:
        for process in (frontend, backend):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        stop.set()
        for thread in threads:
            thread.join(timeout=2)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as exc:
        logger.exception('Development server failed: %s', exc)
        sys.exit(1)
