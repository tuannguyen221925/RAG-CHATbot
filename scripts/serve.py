"""Start the single Python backend using WEB_PORT from .env."""
import argparse
import os

import uvicorn
from api.db import ROOT
from api.observability import configure_console, logging_config


def main():
    configure_console()
    parser = argparse.ArgumentParser()
    parser.add_argument('--reload', action='store_true')
    parser.add_argument('--port', type=int, default=int(os.getenv('WEB_PORT', '8501')))
    args = parser.parse_args()
    os.chdir(ROOT)
    uvicorn.run('api.web:app', host='127.0.0.1', port=args.port, reload=args.reload,
                log_config=logging_config(), access_log=False)


if __name__ == '__main__':
    main()
