"""API gateway: the single entry point that clients talk to."""
import os

import requests
from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__)

# Configuration comes from environment variables, with local defaults.
PORT = int(os.environ.get("PORT", 5000))
CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://localhost:5001")
ORDERS_URL = os.environ.get("ORDERS_URL", "http://localhost:5002")
TIMEOUT = 3  # seconds

# Which internal service owns which public resource
ROUTES = {
    "books": CATALOGUE_URL,
    "orders": ORDERS_URL,
}


@app.get("/")
def shop_page():
    """Serve the shop's web page to the browser."""
    return send_from_directory("static", "index.html")


@app.get("/health")
def health():
    """Report the gateway's own health plus that of each downstream service."""
    services = {}
    for name, base_url in {"catalogue": CATALOGUE_URL, "orders": ORDERS_URL}.items():
        try:
            r = requests.get(f"{base_url}/health", timeout=1)
            services[name] = "ok" if r.ok else f"error ({r.status_code})"
        except requests.exceptions.RequestException:
            services[name] = "unreachable"
    overall = "ok" if all(s == "ok" for s in services.values()) else "degraded"
    return jsonify(status=overall, services=services), (200 if overall == "ok" else 503)

def forward(base_url, path):
    """Pass the incoming request on to an internal service and relay its reply."""
    url = f"{base_url}/{path}"
    try:
        r = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            json=request.get_json(silent=True),
            timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return jsonify(error=f"Upstream service for '{path}' is unavailable"), 502
    return Response(r.content, status=r.status_code,
                    content_type=r.headers.get("Content-Type", "application/json"))


@app.route("/api/<resource>", methods=["GET", "POST"])
@app.route("/api/<resource>/<path:rest>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(resource, rest=""):
    base_url = ROUTES.get(resource)
    if base_url is None:
        return jsonify(error=f"Unknown resource '{resource}'"), 404
    path = f"{resource}/{rest}" if rest else resource
    print(f"[gateway] {request.method} /api/{path} -> {base_url}/{path}", flush=True)
    return forward(base_url, path)

if __name__ == "__main__":
    # 0.0.0.0 so the service is reachable from outside a container next week.
    app.run(host="0.0.0.0", port=PORT, debug=True)
