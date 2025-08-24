from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return jsonify({"message": "Flask app is running on Fly.io!"})

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        data = request.get_json()
        url = data.get("url")

        if not url:
            return jsonify({"error": "URL is required"}), 400

        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string if soup.title else "No title found"
        description = soup.find("meta", attrs={"name": "description"})
        description = description["content"] if description else "No description found"

        return jsonify({
            "url": url,
            "title": title,
            "description": description
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
