"""Pixora Main ASGI Entrypoint & Local Development Launcher."""
import os
import uvicorn

from gateway import app

application = app  # ASGI compatibility alias

if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '8000'))
    reload = os.environ.get('RELOAD', '1') == '1'
    print(f"🚀 Booting Pixora Localhost Platform on http://{host}:{port}")
    uvicorn.run("gateway:app", host=host, port=port, reload=reload)
