import os
from flask import Flask, render_template, request
import PyPDF2
from skills import SKILLS_DB
import google.generativeai as genai
from dotenv import load_dotenv


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not found in .env file!")
else:
    print("KEY LOADED successfully (not showing full key for security)")


genai.configure(api_key=GEMINI_API_KEY)

# ---------------------------------------
# Flask setup
# ---------------------------------------
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Create uploads folder if missing
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------------------------------
# Extract text from PDF
# ---------------------------------------
def extract_text_from_pdf(filepath):
    text = ""
    try:
        with open(filepath, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                content = page.extract_text()
                if content:
                    text += content + "\n"
    except Exception as e:
        print("PDF Extraction ERROR:", str(e))
        text = ""

    return text.lower()

# ---------------------------------------
# Find skills
# ---------------------------------------
def find_skills(resume_text):
    found = []
    for skill in SKILLS_DB:
        if skill.lower() in resume_text:
            found.append(skill)
    return found

# ---------------------------------------
# Score calculation
# ---------------------------------------
def calculate_score(found_skills):
    if len(SKILLS_DB) == 0:
        return 0
    return min(int((len(found_skills) / len(SKILLS_DB)) * 100), 100)

# ---------------------------------------
# Gemini AI suggestions
# ---------------------------------------
def get_ai_suggestions(resume_text):
    try:
        if not resume_text.strip():
            return "Resume text is empty. Cannot analyze."

        # Truncate to avoid token limit & high cost (~4000 chars ~ 1000 tokens)
        truncated_text = resume_text[:4000]

        prompt = f"""
        You are an expert resume reviewer and ATS specialist.
        Review the following resume text and provide short, actionable bullet-point suggestions 
        to improve:
        - ATS compatibility (keywords, formatting tips)
        - Clarity and impact
        - Quantifiable achievements
        - Missing or weak skills/sections

        Be concise, professional, and constructive.
        Focus only on improvements — do not rewrite the full resume.

        Resume text:
        {truncated_text}
        """

        # Use a current stable fast model (as of Feb 2026)
        response = genai.generate_content(
            model="gemini-2.5-flash",   # ← Recommended fast & capable model
            contents=prompt,
        )

        return response.text.strip()

    except Exception as e:
        error_msg = str(e)
        print("Gemini API Error:", error_msg)

        if "API key" in error_msg or "authentication" in error_msg.lower():
            return "⚠ Gemini API key issue — check your .env file and key validity."

        if "model" in error_msg.lower() and "not found" in error_msg.lower():
            return "⚠ Model not available — try updating to a newer model name."

        # Graceful fallback
        return (
            "⚠ AI suggestions temporarily unavailable (API error or rate limit).\n\n"
            "Quick manual tips:\n"
            "• Use action verbs (Led, Developed, Increased)\n"
            "• Quantify achievements (e.g., 'Boosted sales 35%')\n"
            "• Include keywords from job descriptions\n"
            "• Avoid tables/graphics in PDF for ATS\n"
            "• Add projects, certifications, GitHub links"
        )

# ---------------------------------------
# Home
# ---------------------------------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------------------------------------
# Analyze resume
# ---------------------------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    if "resume" not in request.files:
        return "No file part in request", 400

    file = request.files["resume"]

    if file.filename == "":
        return "No file selected", 400

    # Save file
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    # Extract text
    resume_text = extract_text_from_pdf(filepath)
    print("Extracted text length:", len(resume_text))  # debug

    if not resume_text.strip():
        return "Could not extract text from PDF. Try a different file.", 400

    # Find skills
    found_skills = find_skills(resume_text)
    missing_skills = [s for s in SKILLS_DB if s not in found_skills]

    # Score
    score = calculate_score(found_skills)

    # Rule-based suggestions
    suggestions = []

    if score < 40:
        suggestions.append("Your skill match is low — add more relevant technical skills from job descriptions.")
    elif score < 70:
        suggestions.append("Good start — strengthen by adding more tools/technologies and projects.")
    else:
        suggestions.append("Strong skill match! Focus on quantifying achievements and tailoring further.")

    if "project" not in resume_text and "projects" not in resume_text:
        suggestions.append("Add a Projects section with descriptions and technologies used.")

    if "internship" not in resume_text and "experience" not in resume_text:
        suggestions.append("Include internships, freelance work, or volunteer experience if applicable.")

    if not suggestions:
        suggestions.append("Overall solid — improve formatting, add metrics, and proofread for typos.")

    # Gemini AI feedback
    ai_feedback = get_ai_suggestions(resume_text)

    # Clean up uploaded file (optional but good practice)
    # os.remove(filepath)  # Uncomment if you don't want to keep files

    return render_template(
        "result.html",
        score=score,
        found_skills=found_skills,
        missing_skills=missing_skills,
        suggestions=suggestions,
        ai_feedback=ai_feedback,
    )

# ---------------------------------------
# Run server
# ---------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
