# app.py

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import OrderedDict, Counter
import spacy
from serpapi import GoogleSearch

# --- Basic Setup ---
app = Flask(__name__)

# --- Load the spaCy model once on startup ---
# This will download the model if it's not present.
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model... (This will happen only once on Render during build)")
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# --- CORS Configuration ---
# Allow requests from any origin. For production, you might want to restrict this.
CORS(app)

# --- Constants ---
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
REQUEST_TIMEOUT = 15
MAX_CONTENT_SIZE = 500000 # Limit content size to avoid memory issues

# --- Utility Functions ---

def clean_text(text: str) -> str:
    """Removes special characters and converts to lowercase."""
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text or "")
    return text.lower()

def extract_keywords(text: str, top_n: int = 20) -> dict:
    """Extracts top keywords from text, excluding common stopwords."""
    # A more comprehensive stopword list could be used here
    stopwords = {"the", "and", "to", "of", "a", "in", "for", "is", "on", "with", "that", "as", "by", "it", "are"}
    words = clean_text(text).split()
    words = [w for w in words if w not in stopwords and len(w) > 2]
    freq = Counter(words)
    return dict(freq.most_common(top_n))

def analyze_semantic_clusters(text: str) -> dict:
    """Analyzes text to find semantically related keyword clusters using spaCy."""
    doc = nlp(text[:100000]) # Limit text size for performance
    
    # Extract noun phrases as potential topics
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
            if doc1.similarity(doc2) > 0.70: # Similarity threshold
                related.append(doc2.text)
        if related:
            clusters[phrase] = list(set(related))
            
    return clusters if clusters else {"message": "No strong semantic clusters identified."}


def build_single_page_report(url: str, soup: BeautifulSoup, response_status: int) -> OrderedDict:
    """Builds a detailed SEO report for a single URL."""
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

    top_keywords = extract_keywords(full_text)
    report["Top Keywords"] = top_keywords
    
    try:
        report["Semantic Keyword Clusters"] = analyze_semantic_clusters(full_text)
    except Exception as e:
        report["Semantic Keyword Clusters"] = {"error": f"Semantic analysis failed: {str(e)}"}

    return report

# --- Core SERP Analysis Function ---

def analyze_serp_competitors(keyword: str, user_url: str, serpapi_key: str) -> dict:
    """
    Analyzes top 10 Google search results for a keyword, benchmarks them,
    and compares the user's URL against the average.
    """
    print(f"Fetching SERP for keyword: {keyword}")
    search = GoogleSearch({
        "q": keyword,
        "engine": "google",
        "gl": "us",
        "hl": "en",
        "api_key": serpapi_key
    })
    results = search.get_dict()
    organic_results = results.get("organic_results", [])

    if not organic_results:
        return {"error": "Could not fetch organic results from Google."}

    competitor_urls = [res["link"] for res in organic_results[:10]]
    competitor_reports = []

    for url in competitor_urls:
        if url == user_url: continue
        try:
            print(f"Analyzing competitor: {url}")
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text[:MAX_CONTENT_SIZE], "html.parser")
            report = build_single_page_report(url, soup, resp.status_code)
            competitor_reports.append(report)
        except Exception as e:
            print(f"Skipping {url} due to error: {e}")

    if not competitor_reports:
        return {"error": "Could not analyze any competitor pages."}

    # Aggregate competitor data
    total_word_count = sum(r.get("Word Count", 0) for r in competitor_reports)
    avg_word_count = total_word_count // len(competitor_reports)
    
    all_keywords = Counter()
    for report in competitor_reports:
        all_keywords.update(report.get("Top Keywords", {}))

    benchmarks = {
        "average_word_count": avg_word_count,
        "common_keywords": dict(all_keywords.most_common(20)),
        "competitor_count": len(competitor_reports)
    }

    # Analyze the user's URL
    user_report = {}
    try:
        print(f"Analyzing user URL: {user_url}")
        resp = requests.get(user_url, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text[:MAX_CONTENT_SIZE], "html.parser")
        user_report = build_single_page_report(user_url, soup, resp.status_code)
    except Exception as e:
        return {"error": f"Failed to analyze your URL: {e}"}

    return {
        "user_analysis": user_report,
        "competitor_benchmarks": benchmarks
    }

# --- API Routes ---

@app.route("/")
def home():
    return "✅ SERP SEO Analyzer API is running!"

@app.route("/analyze-serp")
def analyze_serp_endpoint():
    keyword = request.args.get("keyword", "").strip()
    user_url = request.args.get("url", "").strip()
    serpapi_key = os.environ.get("SERPAPI_KEY")

    if not keyword or not user_url:
        return jsonify({"success": False, "error": "Parameters 'keyword' and 'url' are required."}), 400
    
    if not serpapi_key:
        return jsonify({"success": False, "error": "Server is missing SERPAPI_KEY configuration."}), 500

    try:
        result = analyze_serp_competitors(keyword, user_url, serpapi_key)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 500
        return jsonify({"success": True, "data": result})
    except Exception as e:
        print(f"Unexpected error in /analyze-serp: {str(e)}")
        return jsonify({"success": False, "error": "An unexpected server error occurred."}), 500

if __name__ == "__main__":
    app.run(debug=True)

