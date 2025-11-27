"""
Pionex Dashboard API - Vercel Serverless Function
"""

import os
import time
import hmac
import hashlib
import json
from urllib.parse import parse_qs, urlparse
import urllib.request
import urllib.error

# Pionex API Configuration
PIONEX_API_URL = "https://api.pionex.com"
PIONEX_API_KEY = os.environ.get("PIONEX_API_KEY", "")
PIONEX_API_SECRET = os.environ.get("PIONEX_API_SECRET", "")


def generate_signature(method: str, path: str, query_string: str, body: str = ""):
    """Generate HMAC SHA256 signature for Pionex API authentication"""
    timestamp = int(time.time() * 1000)
    
    if query_string:
        path_url = f"{path}?{query_string}&timestamp={timestamp}"
    else:
        path_url = f"{path}?timestamp={timestamp}"
    
    sign_str = f"{method}{path_url}"
    if body:
        sign_str += body
    
    signature = hmac.new(
        PIONEX_API_SECRET.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature, timestamp


def pionex_request(method: str, endpoint: str, params: dict = None):
    """Make authenticated request to Pionex API"""
    if not PIONEX_API_KEY or not PIONEX_API_SECRET:
        return {"error": "API credentials not configured", "result": False}
    
    # Build query string from params
    query_parts = []
    if params:
        for key, value in sorted(params.items()):
            if value is not None:
                query_parts.append(f"{key}={value}")
    query_string = "&".join(query_parts)
    
    # Generate signature
    signature, timestamp = generate_signature(method, endpoint, query_string)
    
    # Build full URL
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
        req = urllib.request.Request(url, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return {"error": f"HTTP {e.code}: {error_body}", "result": False}
    except Exception as e:
        return {"error": str(e), "result": False}


def handler(request):
    """Main Vercel serverless handler"""
    
    # Parse the path
    path = request.get("path", "/")
    method = request.get("method", "GET")
    
    # CORS headers
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json"
    }
    
    # Handle OPTIONS preflight
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": ""
        }
    
    # Route handling
    response_body = {"error": "Not found", "result": False}
    status_code = 404
    
    # Health check
    if path == "/api" or path == "/api/" or path == "/api/health":
        response_body = {
            "status": "ok",
            "configured": bool(PIONEX_API_KEY and PIONEX_API_SECRET),
            "result": True
        }
        status_code = 200
    
    # Futures balance
    elif path == "/api/futures/balance":
        response_body = pionex_request("GET", "/api/v1/account/balances", {"type": "PERP"})
        status_code = 200 if response_body.get("result") else 400
    
    # Futures positions
    elif path == "/api/futures/positions":
        response_body = pionex_request("GET", "/api/v1/futures/positions")
        status_code = 200 if response_body.get("result") else 400
    
    # Account balances (spot)
    elif path == "/api/balance":
        response_body = pionex_request("GET", "/api/v1/account/balances")
        status_code = 200 if response_body.get("result") else 400
    
    # All balances
    elif path == "/api/balances":
        spot = pionex_request("GET", "/api/v1/account/balances", {"type": "SPOT"})
        perp = pionex_request("GET", "/api/v1/account/balances", {"type": "PERP"})
        response_body = {
            "result": True,
            "spot": spot,
            "futures": perp
        }
        status_code = 200
    
    # Open orders
    elif path == "/api/futures/orders":
        response_body = pionex_request("GET", "/api/v1/futures/openOrders")
        status_code = 200 if response_body.get("result") else 400
    
    # Test endpoint - shows what Pionex returns
    elif path == "/api/test":
        response_body = {
            "result": True,
            "message": "API is working",
            "has_key": bool(PIONEX_API_KEY),
            "has_secret": bool(PIONEX_API_SECRET),
            "key_preview": PIONEX_API_KEY[:8] + "..." if PIONEX_API_KEY else "not set"
        }
        status_code = 200
    
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(response_body)
    }


# Vercel expects this format
def main(request):
    return handler({
        "path": request.path,
        "method": request.method,
        "body": request.body
    })


# For Vercel Python runtime - this is the entry point
from http.server import BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = handler({"path": self.path, "method": "GET"})
        self.send_response(result["statusCode"])
        for key, value in result["headers"].items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(result["body"].encode())
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length else ""
        result = handler({"path": self.path, "method": "POST", "body": body})
        self.send_response(result["statusCode"])
        for key, value in result["headers"].items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(result["body"].encode())
    
    def do_OPTIONS(self):
        result = handler({"path": self.path, "method": "OPTIONS"})
        self.send_response(result["statusCode"])
        for key, value in result["headers"].items():
            self.send_header(key, value)
        self.end_headers()
