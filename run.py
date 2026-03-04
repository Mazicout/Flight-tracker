#!/usr/bin/env python3
"""
Flight Tracker Server v5 — Plug & Play
Serves HTML, proxies flights, fetches news, collects feedback.
"""

import http.server
import urllib.request
import urllib.error
import json
import os
import sys
import subprocess
import threading
import time
import webbrowser
import re
import html as htmlmod

PORT = 4000
DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_FILE = os.path.join(DIR, 'feedback.json')

def ensure_pywebview():
    try:
        import webview
        return True
    except ImportError:
        print("  [SETUP] Installing pywebview (one-time)...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pywebview', '--break-system-packages', '--quiet'])
            return True
        except Exception:
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pywebview', '--quiet'])
                return True
            except Exception:
                return False

def fetch_news_items():
    items = []
    try:
        url = 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en'
        req = urllib.request.Request(url, headers={'User-Agent': 'FlightTracker/1.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            in_item = False
            for line in raw.split('\n'):
                line = line.strip()
                if '<item>' in line:
                    in_item = True
                elif '</item>' in line:
                    in_item = False
                elif in_item and '<title>' in line:
                    m = re.search(r'<title>(.*?)</title>', line)
                    if not m:
                        m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', line)
                    if m:
                        title = htmlmod.unescape(m.group(1)).strip()
                        if title and title != 'Google News':
                            items.append({'title': title})
                if len(items) >= 15:
                    break
    except Exception as e:
        print(f"  [NEWS] Error: {e}")
    if not items:
        items = [
            {'title': 'Live global flight tracking active'},
            {'title': 'Monitoring conflict zones worldwide'},
            {'title': 'ADS-B data refreshing every 12 seconds'},
        ]
    return items

def save_feedback(data):
    feedbacks = []
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r') as f:
                feedbacks = json.load(f)
        except Exception:
            feedbacks = []
    feedbacks.append(data)
    with open(FEEDBACK_FILE, 'w') as f:
        json.dump(feedbacks, f, indent=2)
    print(f"  [FEEDBACK] From {data.get('name', 'Anon')} - {data.get('rating', '?')}/5")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith('/api/flights'):
            self.proxy_flights()
        elif self.path.startswith('/api/news'):
            self.serve_news()
        elif self.path in ('/', ''):
            self.path = '/index.html'
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/feedback'):
            self.handle_feedback()
        else:
            self.send_error(404)

    def proxy_flights(self):
        from urllib.parse import urlparse, parse_qs
        params = parse_qs(urlparse(self.path).query)
        lat = params.get('lat', ['23.81'])[0]
        lon = params.get('lon', ['90.41'])[0]
        dist = params.get('dist', ['250'])[0]
        urls = [
            f"https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{dist}",
            f"https://opensky-network.org/api/states/all?lamin={float(lat)-3}&lomin={float(lon)-4}&lamax={float(lat)+3}&lomax={float(lon)+4}",
        ]
        data = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'FlightTracker/1.0', 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    break
            except Exception:
                continue
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data or {"ac": []}).encode())

    def serve_news(self):
        items = fetch_news_items()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"items": items}).encode())

    def handle_feedback(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode()
            data = json.loads(body)
            data['ip'] = self.client_address[0]
            save_feedback(data)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, fmt, *args):
        path = str(args[0]) if args else ''
        if '/api/' in path:
            print(f"  [API] {path.split(' ')[1] if ' ' in path else path}")

def start_server():
    server = http.server.HTTPServer(('127.0.0.1', PORT), Handler)
    server.serve_forever()

def try_desktop_level():
    if sys.platform == 'darwin':
        time.sleep(1.5)
        try:
            import AppKit
            for w in AppKit.NSApplication.sharedApplication().windows():
                w.setLevel_(AppKit.kCGDesktopWindowLevel)
                w.setCollectionBehavior_(
                    AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                    AppKit.NSWindowCollectionBehaviorStationary |
                    AppKit.NSWindowCollectionBehaviorIgnoresCycle)
            print("  [OK] Desktop level set")
        except Exception:
            pass

def main():
    print(f"""
+===============================================+
|        FLIGHT TRACKER WALLPAPER v5.0          |
+===============================================+
|  Live flights, trails, war zones, news,       |
|  plane details, feedback collection           |
+-----------------------------------------------+
|  Close this window to stop.                   |
+===============================================+
""")
    print(f"  [1/3] Starting server on port {PORT}")
    threading.Thread(target=start_server, daemon=True).start()
    time.sleep(0.5)
    print(f"  [OK]  http://localhost:{PORT}")

    print("  [2/3] Checking pywebview...")
    has_wv = ensure_pywebview()

    if has_wv:
        try:
            import webview
            print("  [3/3] Opening wallpaper window...")
            print()
            print("  > Flight Tracker is LIVE!")
            print("  > ESC or Cmd+Q to close")
            print(f"  > Feedback saved to: {FEEDBACK_FILE}")
            print()
            threading.Thread(target=try_desktop_level, daemon=True).start()
            webview.create_window('Flight Tracker', url=f'http://localhost:{PORT}',
                                  fullscreen=True, frameless=True, easy_drag=False)
            webview.start(debug=False)
            return
        except Exception as e:
            print(f"  [WARN] pywebview: {e}")

    print("  [3/3] Opening browser...")
    url = f'http://localhost:{PORT}'
    opened = False
    if sys.platform == 'win32':
        for b in [
            os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
            os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
        ]:
            if os.path.exists(b):
                subprocess.Popen([b, f'--app={url}', '--start-fullscreen'])
                opened = True; break
    elif sys.platform == 'darwin':
        for b in ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                   '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']:
            if os.path.exists(b):
                subprocess.Popen([b, f'--app={url}', '--start-fullscreen'])
                opened = True; break
    if not opened:
        webbrowser.open(url)

    print()
    print("  > Flight Tracker LIVE!")
    print("  > Keep this window open. Ctrl+C to stop.")
    print(f"  > Feedback: {FEEDBACK_FILE}")
    print()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down.")

if __name__ == '__main__':
    main()
