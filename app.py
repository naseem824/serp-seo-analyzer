# app.py

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlencode
from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import OrderedDict, Counter
import spacy

# --- Basic Setup ---
app = Flask(__name__)

# --- Load the spaCy model once on startup ---
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model... (This will happen only once on Render during build)")
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

CORS(app)

# --- Constants ---
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
REQUEST_TIMEOUT = 20 # Increased timeout for scraper APIs
MAX_CONTENT_SIZE = 500000

# --- Utility Functions (These are unchanged) ---

def clean_text(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text or "")
    return text.lower()

def extract_keywords(text: str, top_n: int = 20) -> dict:
    stopwords = {"the", "and", "to", "of", "a", "in", "for", "is", "on", "with", "that", "as", "by", "it", "are"}
    words = clean_text(text).split()
    words = [w for w in words if w not in stopwords and len(w) > 2]
    freq = Counter(words)
    return dict(freq.most_common(top_n))

def analyze_semantic_clusters(text: str) -> dict:
    doc = nlp(text[:100000])
    key_phrases = [chunk.text.lower() for chunk in doc.noun_chunks if len(chunk.text.split()) > 1]
    if not key_phrases:
        return {"message": "Not enough key phrases found for semantic analysis."}

    phrase_counts = Counter(key_phrases)
    main_phrases = [phrase for phrase, count in phrase_counts.most_common(10)]
    main_phrase_docs = {phrase: nlp(phrase) for phrase in main_phrases}

    clusters = OrderedDict()
    all_phrase_docs = [nlp(phrase) for phrase in set(key_phrases)]

    for phrase, doc1 in main_phrase_docs.items():
        if not doc1.has_vector: continue
        related = []
        for doc2 in all_phrase_docs:
            if doc1.text == doc2.text or not doc2.has_vector: continue
            if doc1.similarity(doc2) > 0.70:
                related.append(doc2.text)
        if related:
            clusters[phrase] = list(set(related))
    return clusters if clusters else {"message": "No strong semantic clusters identified."}

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
    try:
        report["Semantic Keyword Clusters"] = analyze_semantic_clusters(full_text)
    except Exception as e:
        report["Semantic Keyword Clusters"] = {"error": f"Semantic analysis failed: {str(e)}"}
    return report

# --- CORRECTED Core SERP Analysis Function for ScraperAPI ---

def analyze_serp_competitors(keyword: str, user_url: str, scraperapi_key: str) -> dict:
    print(f"Fetching SERP for keyword: {keyword} using ScraperAPI")
    
    google_search_url = "https://www.google.com/search?" + urlencode({'q': keyword})
    scraperapi_payload = {'api_key': scraperapi_key, 'url': google_search_url}
    
    response = requests.get("http://api.scraperapi.com", params=scraperapi_payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    organic_results = []
    # This selector targets the main organic result links on Google
    for result_div in soup.select("div.g"):
        link_tag = result_div.find("a")
        if link_tag and link_tag.get('href') and link_tag.get('href').startswith('http'):
            organic_results.append({'link': link_tag.get('href')})

    if not organic_results:
        return {"error": "Could not parse organic results from Google HTML. The page structure might have changed."}

    competitor_urls = [res["link"] for res in organic_results[:10]]
    competitor_reports = []

    for url in competitor_urls:
        if url == user_url: continue
        try:
            print(f"Analyzing competitor: {url}")
            competitor_payload = {'api_key': scraperapi_key, 'url': url}
            resp = requests.get("http://api.scraperapi.com", params=competitor_payload, timeout=REQUEST_TIMEOUT)
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
        resp = requests.get("http://api.scraperapi.com", params=user_payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup_user = BeautifulSoup(resp.text[:MAX_CONTENT_SIZE], "html.parser")
        user_report = build_single_page_report(user_url, soup_user, resp.status_code)
    except Exception as e:
        return {"error": f"Failed to analyze your URL: {e}"}

    return {
        "user_analysis": user_report,
        "competitor_benchmarks": benchmarks
    }

# --- API Routes (Using SCRAPERAPI_KEY) ---

@app.route("/")
def home():
    return "✅ SERP SEO Analyzer API is running!"

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
            return jsonify({"success": False, "error": result["error"]}), 500
        return jsonify({"success": True, "data": result})
    except Exception as e:
        print(f"Unexpected error in /analyze-serp: {str(e)}")
        return jsonify({"success": False, "error": "An unexpected server error occurred."}), 500

if __name__ == "__main__":
    # This part is for local testing and won't run on Render
    app.run(debug=True)
