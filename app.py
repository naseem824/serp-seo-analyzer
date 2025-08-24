import os
import re
import requests
import traceback
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import OrderedDict, Counter

# --- Basic Setup ---
app = Flask(__name__)
CORS(app)

# --- Constants ---
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/91.0.4472.124 Safari/537.36"
}
REQUEST_TIMEOUT = 60
MAX_CONTENT_SIZE = 500000


# --- Utility Functions ---
def clean_text(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text or "")
    return text.lower()


def extract_keywords(text: str, top_n: int = 20) -> dict:
    stopwords = {
        "the", "and", "to", "of", "a", "in", "for", "is",
        "on", "with", "that", "as", "by", "it", "are"
    }
    words = clean_text(text).split()
    words = [w for w in words if w not in stopwords and len(w) > 2]
    freq = Counter(words)
    return dict(freq.most_common(top_n))


def build_single_page_report(url: str, soup: BeautifulSoup, response_status: int) -> OrderedDict:
    report = OrderedDict()
    report["URL"] = url
    report["Status"] = response_status

    title = (soup.title.string or "").strip() if soup.title else "Not Found"
    report["Title"] = title

    desc = soup.find("meta", attrs={"name": "description"})
    meta_desc = desc.get("content", "").strip() if desc else "Not Found"
    report["Meta Description"] = meta_desc

    full_text = soup.get_text(" ", strip=True)
    total_words = len(full_text.split())
    report["Word Count"] = total_words
    report["Top Keywords"] = extract_keywords(full_text)
    return report


# --- Core SERP Analysis Function ---
def analyze_serp_competitors(keyword: str, user_url: str, scraperapi_key: str) -> dict:
    print(f"Fetching SERP for keyword: {keyword} using ScraperAPI")

    google_search_url = "https://www.google.com/search?" + urlencode({'q': keyword})
    scraperapi_payload = {'api_key': scraperapi_key, 'url': google_search_url}

    response = requests.get(
        "https://api.scraperapi.com",
        params=scraperapi_payload,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    organic_results = []
    for result_div in soup.select("div.g, div.tF2Cxc"):
        link_tag = result_div.find("a")
        if link_tag and link_tag.get('href') and link_tag.get('href').startswith('http'):
            organic_results.append(link_tag.get('href'))

    if not organic_results:
        return {"error": "Could not parse organic results from Google HTML. The page structure might have changed."}

    competitor_urls = list(dict.fromkeys(organic_results[:3]))  # remove duplicates, keep order
    print(f"Found {len(competitor_urls)} competitors to analyze.")
    competitor_reports = []

    for url in competitor_urls:
        if url == user_url:
            continue
        try:
            print(f"Analyzing competitor: {url}")
            competitor_payload = {'api_key': scraperapi_key, 'url': url}
            resp = requests.get(
                "https://api.scraperapi.com",
                params=competitor_payload,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            soup_comp = BeautifulSoup(resp.text[:MAX_CONTENT_SIZE], "html.parser")
            report = build_single_page_report(url, soup_comp, resp.status_code)
            competitor_reports.append(report)
        except Exception as e:
            print(f"Skipping {url} due to error: {e}")

    if not competitor_reports:
        return {"error": "Could not analyze any competitor pages."}

    total_word_count = sum(r.get("Word Count", 0) for r in competitor_reports)
    avg_word_count = total_word_count // len(competitor_reports) if competitor_reports else 0

    all_keywords = Counter()
    for report in competitor_reports:
        all_keywords.update(report.get("Top Keywords", {}))

    benchmarks = {
        "average_word_count": avg_word_count,
        "common_keywords": dict(all_keywords.most_common(20)),
        "competitor_count": len(competitor_reports)
    }

    user_report = {}
    try:
        print(f"Analyzing user URL: {user_url}")
        user_payload = {'api_key': scraperapi_key, 'url': user_url}
        resp = requests.get(
            "https://api.scraperapi.com",
            params=user_payload,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        soup_user = BeautifulSoup(resp.text[:MAX_CONTENT_SIZE], "html.parser")
        user_report = build_single_page_report(user_url, soup_user, resp.status_code)
    except Exception as e:
        return {"error": f"Failed to analyze your URL: {e}"}

    return {
        "user_analysis": user_report,
        "competitor_benchmarks": benchmarks
    }


# --- API Routes ---
@app.route("/")
def home():
    return "✅ SERP SEO Analyzer API is running!", 200


@app.route("/analyze-serp")
def analyze_serp_endpoint():
    keyword = request.args.get("keyword", "").strip()
    user_url = request.args.get("url", "").strip()
    scraperapi_key = os.environ.get("SCRAPERAPI_KEY")

    if not keyword or not user_url:
        return jsonify({"success": False, "error": "Parameters 'keyword' and 'url' are required."}), 400

    if not scraperapi_key:
        return jsonify({"success": False, "error": "Server is missing SCRAPERAPI_KEY configuration."}), 500

    try:
        result = analyze_serp_competitors(keyword, user_url, scraperapi_key)
        if "error" in result:
            print(f"Application error: {result['error']}")
            return jsonify({"success": False, "error": result["error"]}), 500
        return jsonify({"success": True, "data": result})

    except requests.exceptions.Timeout:
        print("A request to ScraperAPI timed out.")
        return jsonify({"success": False, "error": "The request timed out while trying to fetch data."}), 504

    except Exception as e:
        print("--- UNEXPECTED SERVER ERROR ---")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Details: {str(e)}")
        traceback.print_exc()
        print("--- END OF ERROR ---")
        return jsonify({"success": False, "error": "An unexpected server error occurred. The issue has been logged."}), 500


# ✅ Production entrypoint (Fly.io will use Gunicorn in Dockerfile)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
