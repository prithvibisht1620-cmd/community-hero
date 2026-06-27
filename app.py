import os
import json
import sqlite3
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal
from PIL import Image

app = Flask(__name__)

# 🛑 CRITICAL FIX: Pulls key from the server environment, NOT from this text!
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def init_db():
    conn = sqlite3.connect('community_hero.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            analysis TEXT NOT NULL,
            latitude TEXT,
            longitude TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

class IssueAnalysis(BaseModel):
    category: Literal["Pothole", "Waste Management", "Streetlight", "Water Leakage", "Other"] = Field(description="Categorize the civic issue shown in the image.")
    severity: Literal["Low", "Medium", "High"] = Field(description="Determine the severity and immediate danger of the issue.")
    ai_analysis: str = Field(description="A brief, 2-sentence description of what is visible and the potential hazard.")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_issue():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "Empty file"}), 400

    latitude = request.form.get('latitude', '')
    longitude = request.form.get('longitude', '')

    try:
        img = Image.open(file.stream)
        prompt = "You are an automated civic triage assistant. Analyze this image of public infrastructure damage. Categorize it, determine severity, and provide a brief analysis."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=IssueAnalysis,
            ),
        )
        
        gemini_data = json.loads(response.text)
        
        conn = sqlite3.connect('community_hero.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO reports (category, severity, analysis, latitude, longitude)
            VALUES (?, ?, ?, ?, ?)
        ''', (gemini_data['category'], gemini_data['severity'], gemini_data['ai_analysis'], latitude if latitude else "Not Provided", longitude if longitude else "Not Provided"))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "data": gemini_data})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    # Required for Cloud Deployments
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)