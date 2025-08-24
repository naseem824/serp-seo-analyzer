from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")

@app.route("/")
def home():
    return jsonify({"message": "Flask app is running on Fly.io!"})

# Updated scrape endpoint
@app.route("/scrape", methods=["GET", "POST"])
def scrape():
    url = request.args.get("url") if request.method == "GET" else request.json.get("url")

    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    if not SCRAPERAPI_KEY:
        return jsonify({"error": "Missing SCRAPERAPI_KEY configuration"}), 500

    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={url}"

    try:
        response = requests.get(proxy_url, timeout=30)
        return jsonify({"status_code": response.status_code, "content": response.text[:500]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
