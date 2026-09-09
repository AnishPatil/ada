#!/usr/bin/env python
"""
Very simple HTTP server in python (Updated for Python 3.7)
Usage:
    ./startServer.py -h
    ./startServer.py -l localhost -p 8000
Send a POST request:
    curl -d "foo=bar&bin=baz" http://localhost:8000
"""

# show active ports and pids
# netstat -anvp tcp | awk 'NR<3 || /LISTEN/'

import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from multiprocessing import Process
import subprocess
import json
import platform
import shutil
import time
import webbrowser
import ada
from ada.ui.uiManager import UIHandler
from ada.ui.llm_runtime import is_wsl, resolve_runtime_info
from ada.ui.runtime_preferences import load_llm_config, save_llm_config

home_dir = Path.home()
ui_source_dir = Path(ada.ada_path) / "ui" / "UI_Files"

DIRECTORY=home_dir

handler = UIHandler(print_calls=True)


def sync_ui_assets():
    target_dir = home_dir / ".ada"
    target_dir.mkdir(parents=True, exist_ok=True)

    for source_path in ui_source_dir.iterdir():
        destination_path = target_dir / source_path.name
        if source_path.is_dir():
            if destination_path.exists():
                shutil.rmtree(destination_path)
            shutil.copytree(source_path, destination_path)
        else:
            shutil.copy2(source_path, destination_path)

class S(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/llm-config":
            self._set_headers()
            content_length = int(self.headers.get('Content-Length', 0))
            content = self.rfile.read(content_length)
            contentDict = json.loads(content.decode('utf8')) if content else {}
            saved = save_llm_config(contentDict)
            info = resolve_runtime_info()
            message = {
                "config": saved,
                "runtime": info,
            }
            self.wfile.write(json.dumps(message).encode('utf-8'))
            return

        self._set_headers()
        content_length = int(self.headers['Content-Length'])
        content = self.rfile.read(content_length)
        contentDict = json.loads(content.decode('utf8'))

        portNumber = int(self.connection.getsockname()[1])

        queryText = contentDict['queryText']
        callMode = contentDict['callMode']
        handler.makeCall(queryText, callMode, portNumber)
        outputText = handler.generateBodyHTML()
        filetreeText = handler.generateFiletreeHTML()
        geometryText = handler.generateGeometryHTML()
        analysisText = handler.generateAnalysisHTML()
        dataText     = handler.generateDataHTML()
        graphicWindow = handler.generateGraphicWindow()

        message = {}
        message['mainBodyText'] = outputText
        message['filetreeText'] = filetreeText
        message['geometryText'] = geometryText
        message['analysisText'] = analysisText
        message['dataText']     = dataText
        message['graphicWindow'] = graphicWindow

        jsn = json.dumps(message)
        self.wfile.write(jsn.encode('utf-8'))

    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/llm-config":
            self._set_headers()
            message = {
                "config": load_llm_config(),
                "runtime": resolve_runtime_info(),
            }
            self.wfile.write(json.dumps(message).encode('utf-8'))
            return

        super().do_GET()


def run(server_class=HTTPServer, handler_class=S, addr="localhost", port=8000):
    server_address = (addr, port)
    httpd = server_class(server_address, handler_class)

    print(f"Starting httpd server on {addr}:{port}")
    httpd.serve_forever()

def openBrowser(port=8000):
    time.sleep(0.25)
    url = f"http://localhost:{port}/.ada/index.html"

    if platform.system() == "Darwin":
        subprocess.run(["open", url], check=False)
        return

    if is_wsl():
        if shutil.which("wslview"):
            subprocess.run(["wslview", url], check=False)
        else:
            subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Start-Process '{url}'"], check=False)
        return

    webbrowser.open(url, new=2)

if __name__ == "__main__":
    # try:
    sync_ui_assets()
    parser = argparse.ArgumentParser(description="Run a simple HTTP server")
    parser.add_argument(
        "-l",
        "--listen",
        default="localhost",
        help="Specify the IP address on which the server listens",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8000,
        help="Specify the port on which the server listens",
    )
    args = parser.parse_args()
    llm_info = resolve_runtime_info()
    print(f"Runtime platform: {llm_info['platform']}")
    print(f"LLM provider: {llm_info['provider']}")
    if llm_info.get("base_url"):
        print(f"LLM base URL: {llm_info['base_url']}")
    if llm_info.get("model"):
        print(f"LLM model override: {llm_info['model']}")

    # run(addr=args.listen, port=args.port)
    t1 = Process(target=run, kwargs={"addr":args.listen, "port":args.port})
    t1.start()
    t2 = Process(target=openBrowser,  kwargs={"port":args.port})
    t2.start()

    # except KeyboardInterrupt:
    #     print ('^C received, shutting down the web server')
    # #     server.socket.close()
