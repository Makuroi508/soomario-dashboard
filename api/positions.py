from http.server import BaseHTTPRequestHandler
import json
import os
import time
import hmac
import hashlib
import urllib.request
import urllib.error

PIONEX_API_URL = "https://api.pionex.com"
PIONEX_API_KEY = os.environ.get("PIONEX_API_KEY", "")
PIONEX_API_SECRET = os.environ.get("PIONEX_API_SECRET", "")


def generate_signature(method, path, query_string):
    timestamp = int(time.time() * 1000)
    
    if query_string:
        path_url = f"{path}?{query_string}&timestamp={timestamp}"
    else:
        path_url = f"{path}?timestamp={timestamp}"
    
    sign_str = f"{method}{path_url}"
    
    signature = hmac.new(
        PIONEX_API_SECRET.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature, timestamp


def pionex_request(endpoint, params=None):
    if not PIONEX_API_KEY or not PIONEX_API_SECRET:
        return {"error": "API credentials not configured", "result": False}
    
    query_parts = []
    if params:
        for key, value in sorted(params.items()):
            if value is not None:
                query_parts.append(f"{key}={value}")
    query_string = "&".join(query_parts)
    
    signature, timestamp = generate_signature("GET", endpoint, query_string)
    
    if query_string:
        url = f"{PIONEX_API_URL}{endpoint}?{query_string}&timestamp={timestamp}"
    else:
        url = f"{PIONEX_API_URL}{endpoint}?timestamp={timestamp}"
    
    headers = {
        "PIONEX-KEY": PIONEX_API_KEY,
        "PIONEX-SIGNATURE": signature,
        "Content-Type": "application/json"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return {"error": f"HTTP {e.code}: {error_body}", "result": False}
    except Exception as e:
        return {"error": str(e), "result": False}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Get futures positions
        result = pionex_request("/api/v1/futures/positions")
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
