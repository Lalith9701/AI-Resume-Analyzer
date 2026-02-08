import os
from flask import Flask, render_template, request
import PyPDF2
from skills import SKILLS_DB

# Gemini new SDK
from google import genai
from dotenv import load_dotenv

# ---------------------------------------
# Load environment variables
# ---------------------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("KEY LOADED:", GEMINI_API_KEY)  # debug

# Create Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------
# Flask setup
# ---------------------------------------
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


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
                    text += content
    except Exception as e:
        print("PDF ERROR:", e)
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
# Gemini AI suggestions (FIXED VERSION)
# ---------------------------------------
def get_ai_suggestions(resume_text):
    try:
        if not resume_text.strip():
            return "Resume text is empty. Cannot analyze."

        prompt = f"""
        Review this resume and give short bullet point suggestions
        to improve ATS score, clarity, impact and missing skills.

        Resume:
        {resume_text}
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )

        return response.text

    except Exception as e:
        # 🔥 Graceful fallback (IMPORTANT)
        return (
            "⚠ AI suggestions are temporarily unavailable due to API limits.\n\n"
            "Meanwhile, consider these improvements:\n"
            "- Add measurable achievements (numbers, impact)\n"
            "- Use strong action verbs\n"
            "- Tailor skills to the job description\n"
            "- Improve formatting for ATS compatibility\n"
            "- Add relevant projects or internships"
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
        return "No file uploaded"

    file = request.files["resume"]

    if file.filename == "":
        return "No selected file"

    # Save file
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    # Extract text
    resume_text = extract_text_from_pdf(filepath)
    print("TEXT LENGTH:", len(resume_text))  # debug

    # Find skills
    found_skills = find_skills(resume_text)
    missing_skills = [s for s in SKILLS_DB if s not in found_skills]

    # Score
    score = calculate_score(found_skills)

    # ---------------------------------------
    # Rule suggestions
    # ---------------------------------------
    suggestions = []

    if score < 40:
        suggestions.append("Add more technical skills.")
    elif score < 70:
        suggestions.append("Improve resume by adding more relevant tools.")
    else:
        suggestions.append("Strong profile. Add measurable achievements.")

    if "project" not in resume_text:
        suggestions.append("Add project experience.")

    if "internship" not in resume_text:
        suggestions.append("Add internship details.")

    if not suggestions:
        suggestions.append("Improve formatting and readability.")

    # ---------------------------------------
    # Gemini suggestions
    # ---------------------------------------
    ai_feedback = get_ai_suggestions(resume_text)

    # Render
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
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    app.run(debug=True)
