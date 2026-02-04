#!/usr/bin/env python3
"""
Simple Flask server for local demos.

Run with:
    python demo/server.py

Then open http://localhost:5000 in your browser.
"""

import base64
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from api.handler import lambda_handler

app = Flask(__name__, static_folder="static")
CORS(app)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/v1/health", methods=["GET"])
def health():
    event = {
        "httpMethod": "GET",
        "path": "/v1/health",
        "headers": {},
    }
    resp = lambda_handler(event, None)
    return jsonify(json.loads(resp["body"])), resp["statusCode"]


@app.route("/v1/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    event = {
        "httpMethod": "POST",
        "path": "/v1/analyze",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(data),
        "isBase64Encoded": False,
    }
    resp = lambda_handler(event, None)
    return jsonify(json.loads(resp["body"])), resp["statusCode"]


@app.route("/v1/grade", methods=["POST"])
def grade():
    data = request.get_json()
    event = {
        "httpMethod": "POST",
        "path": "/v1/grade",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(data),
        "isBase64Encoded": False,
    }
    resp = lambda_handler(event, None)
    return jsonify(json.loads(resp["body"])), resp["statusCode"]


if __name__ == "__main__":
    print("Starting PreGrade demo server...")
    print("Open http://localhost:5000 in your browser")
    app.run(host="0.0.0.0", port=5000, debug=True)
