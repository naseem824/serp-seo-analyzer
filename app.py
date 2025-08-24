from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

# ✅ Load ScraperAPI key from environment variables
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")


@app.route("/")
def home():
    return jsonify({
        "message": "✅ Scraper API is running on Fly.io!",
        "usage": "/scrape?url=https://example.com"
    })


@app.route("/scrape", methods=["GET"])
def scrape():
    url = request.args.get("url")

    if not url:
        return jsonify({"error": "❌ Missing 'url' parameter"}), 400

    if not SCRAPERAPI_KEY:
        return jsonify({"error": "❌ SCRAPERAPI_KEY is not set in environment"}), 500

    try:
        # ✅ Build ScraperAPI request
        scraper_url = "http://api.scraperapi.com"
        params = {
            "api_key": SCRAPERAPI_KEY,
            "url": url
        }

        response = requests.get(scraper_url, params=params, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title & description
        title = soup.title.string.strip() if soup.title else "No title found"
        meta = soup.find("meta", attrs={"name": "description"})
        description = meta["content"].strip() if meta and "content" in meta.attrs else "No description found"

        return jsonify({
            "success": True,
            "url": url,
            "title": title,
            "description": description
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    # ✅ Fly.io runs on port 8080
    app.run(host="0.0.0.0", port=8080)
