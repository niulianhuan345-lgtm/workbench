#!/usr/bin/env python3
"""总控台服务器 — 静态文件 + 任务 CRUD API。零依赖。"""
import http.server, json, os, shutil, sys, urllib.parse
from pathlib import Path

PORT = 8898
BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE.parent), **kwargs)

    def do_POST(self):
        if self.path == '/api/tasks/save':
            self._save_tasks()
        elif self.path == '/api/scanner/run':
            self._run_scanner()
        else:
            self.send_error(404)

    def _save_tasks(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            tasks = json.loads(body)
            if not isinstance(tasks, list):
                raise ValueError('tasks must be array')
            with open(DATA / 'tasks.json', 'w', encoding='utf-8') as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
            self._json({'ok': True, 'count': len(tasks)})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)}, 400)

    def _run_scanner(self):
        try:
            script = BASE / 'scanner.py'
            if not script.exists():
                self._json({'ok': False, 'error': 'scanner.py not found'}, 404)
                return
            import subprocess
            result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=30)
            self._json({'ok': True, 'output': result.stdout.strip().split('\n')[-3:]})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)}, 500)

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, fmt, *args):
        if '/data/' not in args[0]:
            super().log_message(fmt, *args)

if __name__ == '__main__':
    print(f'🖥️  总控台服务 http://localhost:{PORT}')
    http.server.HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
