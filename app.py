from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return jsonify({"message": "Welcome to Flask API – running successfully on Fly.io/Railway"})

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json()
        url = data.get("url")
        if not url:
            return jsonify({"error": "URL is required"}), 400

        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Example: extract page <title> and meta description
        title = soup.title.string if soup.title else "No title"
        description = soup.find("meta", attrs={"name": "description"})
        description = description["content"] if description else "No description"

        return jsonify({
            "url": url,
            "title": title,
            "description": description
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    # Fly.io / Railway will use Gunicorn in production, but for local test:
    app.run(host="0.0.0.0", port=8080, debug=True)
