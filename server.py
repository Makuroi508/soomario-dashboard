"""
Pionex Dashboard Backend Server
Handles Pionex API authentication and data fetching for futures signal bots
"""

import os
import time
import hmac
import hashlib
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Pionex API Configuration
PIONEX_API_URL = "https://api.pionex.com"
PIONEX_API_KEY = os.getenv("PIONEX_API_KEY", "")
PIONEX_API_SECRET = os.getenv("PIONEX_API_SECRET", "")


def generate_signature(method: str, path: str, query_string: str, body: str = "") -> tuple[str, int]:
    """Generate HMAC SHA256 signature for Pionex API authentication"""
    timestamp = int(time.time() * 1000)
    
    # Build the string to sign
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


def pionex_request(method: str, endpoint: str, params: dict = None, body: dict = None):
    """Make authenticated request to Pionex API"""
    if not PIONEX_API_KEY or not PIONEX_API_SECRET:
        return {"error": "API credentials not configured"}
    
    # Build query string from params
    query_parts = []
    if params:
        for key, value in sorted(params.items()):
            if value is not None:
                query_parts.append(f"{key}={value}")
    query_string = "&".join(query_parts)
    
    # Generate signature
    body_str = ""
    if body:
        import json
        body_str = json.dumps(body, separators=(',', ':'))
    
    signature, timestamp = generate_signature(method, endpoint, query_string, body_str)
    
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
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=body, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, json=body, timeout=10)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "configured": bool(PIONEX_API_KEY and PIONEX_API_SECRET)
    })


@app.route("/api/futures/balance", methods=["GET"])
def get_futures_balance():
    """Get futures account balance"""
    result = pionex_request("GET", "/api/v1/account/balances", {"type": "PERP"})
    return jsonify(result)


@app.route("/api/futures/positions", methods=["GET"])
def get_futures_positions():
    """Get active futures positions"""
    result = pionex_request("GET", "/api/v1/futures/positions")
    return jsonify(result)


@app.route("/api/futures/positions/history", methods=["GET"])
def get_position_history():
    """Get historical positions"""
    params = {
        "limit": request.args.get("limit", 100)
    }
    symbol = request.args.get("symbol")
    if symbol:
        params["symbol"] = symbol
    
    result = pionex_request("GET", "/api/v1/futures/positions/history", params)
    return jsonify(result)


@app.route("/api/futures/orders", methods=["GET"])
def get_futures_orders():
    """Get open futures orders"""
    params = {}
    symbol = request.args.get("symbol")
    if symbol:
        params["symbol"] = symbol
    
    result = pionex_request("GET", "/api/v1/futures/orders", params)
    return jsonify(result)


@app.route("/api/futures/orders/history", methods=["GET"])
def get_order_history():
    """Get historical orders"""
    params = {
        "limit": request.args.get("limit", 100)
    }
    symbol = request.args.get("symbol")
    if symbol:
        params["symbol"] = symbol
    
    result = pionex_request("GET", "/api/v1/futures/orders/history", params)
    return jsonify(result)


@app.route("/api/futures/funding", methods=["GET"])
def get_funding_fees():
    """Get funding fee history"""
    params = {
        "limit": request.args.get("limit", 100)
    }
    symbol = request.args.get("symbol")
    if symbol:
        params["symbol"] = symbol
    
    result = pionex_request("GET", "/api/v1/futures/funding", params)
    return jsonify(result)


@app.route("/api/market/tickers", methods=["GET"])
def get_tickers():
    """Get 24hr tickers for symbols"""
    params = {"type": "PERP"}
    symbol = request.args.get("symbol")
    if symbol:
        params["symbol"] = symbol
    
    result = pionex_request("GET", "/api/v1/common/symbols", params)
    return jsonify(result)


@app.route("/api/market/price/<symbol>", methods=["GET"])
def get_price(symbol):
    """Get current price for a symbol"""
    result = pionex_request("GET", "/api/v1/market/ticker", {"symbol": symbol})
    return jsonify(result)


# Manual data entry endpoints for bot data not available via API
# This serves as a fallback when bot-specific data isn't accessible

MANUAL_BOT_DATA = {}

@app.route("/api/bots", methods=["GET"])
def get_bots():
    """Get manually configured bot data"""
    return jsonify({
        "result": True,
        "data": {"bots": list(MANUAL_BOT_DATA.values())}
    })


@app.route("/api/bots", methods=["POST"])
def update_bot():
    """Update/add bot data manually"""
    data = request.json
    bot_name = data.get("name")
    if not bot_name:
        return jsonify({"error": "Bot name required"}), 400
    
    MANUAL_BOT_DATA[bot_name] = {
        "name": bot_name,
        "pair": data.get("pair", ""),
        "leverage": data.get("leverage", 1),
        "investment": data.get("investment", 0),
        "profit": data.get("profit", 0),
        "profitPercent": data.get("profitPercent", 0),
        "lastPrice": data.get("lastPrice", 0),
        "markPrice": data.get("markPrice", 0),
        "liqPrice": data.get("liqPrice", None),
        "updatedAt": int(time.time() * 1000)
    }
    
    return jsonify({"result": True, "data": MANUAL_BOT_DATA[bot_name]})


@app.route("/api/bots/<bot_name>", methods=["DELETE"])
def delete_bot(bot_name):
    """Delete a bot from manual data"""
    if bot_name in MANUAL_BOT_DATA:
        del MANUAL_BOT_DATA[bot_name]
        return jsonify({"result": True})
    return jsonify({"error": "Bot not found"}), 404


if __name__ == "__main__":
    print("Starting Pionex Dashboard Server...")
    print(f"API Key configured: {bool(PIONEX_API_KEY)}")
    app.run(host="0.0.0.0", port=5000, debug=True)
