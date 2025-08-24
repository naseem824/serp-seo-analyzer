from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

# Get API key from environment variables
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")

@app.route("/scrape", methods=["GET"])
def scrape():
    url = request.args.get("url")

    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    if not SCRAPERAPI_KEY:
        return jsonify({"error": "SCRAPERAPI_KEY is not set in environment"}), 500

    try:
        # Use ScraperAPI endpoint
        scraper_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={url}"

        response = requests.get(scraper_url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title and meta description
        title = soup.title.string if soup.title else None
        description = None
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and "content" in meta.attrs:
            description = meta["content"]

        return jsonify({
            "url": url,
            "title": title,
            "description": description
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "✅ Scraper API is running! Use /scrape?url=https://example.com"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
