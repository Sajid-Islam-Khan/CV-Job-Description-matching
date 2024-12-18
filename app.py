from flask import Flask, render_template, request, jsonify, session
import json
import re
import PyPDF2
import nltk
import os
import requests

app = Flask(__name__)

app.secret_key = 'd@3r!v&j2f8#h1s8^p9wz6pQ3d7U0tX'

# Set your TextRazor API key
API_KEY = 'c6169bac8c680f971cdafd7794d0449b65aa50ed914abba0c4055af9'  # Replace with your actual API key

# Ensure you have the necessary resources for sentence tokenization
nltk.download('punkt')

# Ensure 'uploads' directory exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Function to extract job details from job description using TextRazor
def extract_details(job_description):
    url = "https://api.textrazor.com/"
    headers = {
        'x-textrazor-key': API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'text': job_description,
        'extractors': 'entities'
    }

    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        data = response.json()

        # Define the structured job JSON template
        job_json = {
            "skills": [],
            "experience": [],
            "qualifications": [],
            "certifications": [],
            "responsibilities": []
        }

        # Extract skills from entities recognized by TextRazor
        for entity in data.get('response', {}).get('entities', []):
            entity_type = entity.get('type', [])
            entity_id = entity.get('entityId')

            # Classify recognized entities into relevant categories
            if 'ProgrammingLanguage' in entity_type or 'Software' in entity_type:
                job_json["skills"].append(entity_id)
            elif 'Qualification' in entity_type or 'Degree' in entity_type:
                job_json["qualifications"].append(entity_id)
            elif 'Certification' in entity_type:
                job_json["certifications"].append(entity_id)

        # Dynamic skill extraction: Find skills/knowledge after common skill keywords
        skill_patterns = re.findall(r'\b(?:Knowledge and Skills|Skills|Skills Required|Knowledge):\s*(.*?)(?=\.\s*|\n|$)', job_description, re.IGNORECASE)
        for pattern in skill_patterns:
            skills = re.split(r',\s*', pattern)
            job_json["skills"].extend([skill.strip() for skill in skills if skill.strip()])

        # Extract experience using phrases from "Required Experience"
        experience_matches = re.findall(r'\b(?:Required Experience|Experience Required|Minimum Experience):\s*(.*?)(?=\n|$)', job_description, re.IGNORECASE)
        for match in experience_matches:
            years_matches = re.findall(r'(\d+\s*[-–]?\s*\d*\s*years?)', match)
            job_json["experience"].extend(years_matches)

        # Extract qualifications
        qualifications_matches = re.findall(r'\b(?:Qualifications Required|Academic Qualifications Required|Academic Qualifications|Academic Qualification|Qualifications):\s*(.*?)(?=\n|$|\.)', job_description, re.IGNORECASE)
        for match in qualifications_matches:
            match = match.strip()
            degree_match = re.match(r'(.*?)(?:\s*/\s*|\s*,\s*|\s+)(.*)', match)
            if degree_match:
                degree_part = degree_match.group(1).strip()
                specializations = re.split(r'\s*/\s*|\s*,\s*', degree_match.group(2))
                job_json["qualifications"].extend([f"{degree_part} in {specialization.strip()}" for specialization in specializations if specialization.strip()])
            else:
                job_json["qualifications"].append(match)

        job_json["qualifications"] = [
            qualification.replace("Degree in ", "") for qualification in job_json["qualifications"]
        ]

        # Dynamic certification extraction
        certification_patterns = re.findall(r'\b(?:certified|certification|certifications|certificate|certificates|knowledge of|familiarity with)\b[^:]*:\s*([^.\n]*)', job_description, re.IGNORECASE)
        for pattern in certification_patterns:
            certifications = re.split(r',\s*|\s*/\s*', pattern)
            job_json["certifications"].extend([cert.strip() for cert in certifications if cert.strip()])

        # Dynamic responsibilities extraction
        responsibility_sections = re.findall(r'\b(?:Key Responsibilities|Responsibilities|Key Accountabilities)\b.*?:\s*(.*?)(?=\n[A-Z]|\Z)', job_description, re.IGNORECASE | re.DOTALL)
        for section in responsibility_sections:
            responsibilities = re.findall(r'[-•]\s*(.*?)(?=\n|$)', section)
            job_json["responsibilities"].extend([resp.strip() for resp in responsibilities if resp.strip()])

        return job_json  # Return the actual dictionary, not a string
    else:
        print("Error:", response.status_code, response.text)
        return {"error": response.text}

# Function to convert PDF to text from FileStorage object
def pdf_to_text(cv_file):
    # Read the file directly from FileStorage object
    with cv_file.stream as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text.strip()


# Clean text by removing unnecessary spaces and formatting
def clean_text(text):
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*’\s*', "'", text)
    text = re.sub(r'\s*\'\s*', "'", text)
    text = re.sub(r'\bbachelor\s\'s\b', "bachelor's", text)
    text = re.sub(r'\bmaster\s\'s\b', "master's", text)
    return text.strip()

# Extract CV details and match with job description
def extract_cv_details(cv_text, job_json):
    # Patterns for name, email, and phone
    name_pattern = r"(?<!\w)([A-Z][a-zA-Z-]*(?:\s+[A-Z][a-zA-Z-]*){1,3})(?!\w)"
    email_pattern = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(com))"
    phone_pattern = r"(\+?\d[\d -]{8,}\d)"

    # Extract name, email, and phone
    name_match = re.search(name_pattern, cv_text)
    name = name_match.group(0) if name_match else "N/A"
    email_match = re.search(email_pattern, cv_text)
    email = email_match.group(0) if email_match else "N/A"
    phone_match = re.search(phone_pattern, cv_text)
    phone = phone_match.group(0) if phone_match else "N/A"

    # Initialize CV JSON with a score field
    cv_json = {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": [],
        "experience": [],
        "matchedCertifications": [],
        "additionalCertifications": [],
        "qualifications": [],
        "score": 0  # Initialize score
    }

    # Clean the CV text for skills extraction
    cv_text_cleaned = clean_text(cv_text.lower())

    # Total weightage
    total_skills = len(job_json.get("skills", []))
    total_qualifications = len(job_json.get("qualifications", []))
    total_certifications = len(job_json.get("certifications", []))
    total_elements = total_skills + total_qualifications + total_certifications

    skill_weight = (1 / total_elements) * 100 if total_elements > 0 else 0
    qualification_weight = (1 / total_elements) * 100 if total_elements > 0 else 0
    certification_weight = (1 / total_elements) * 100 if total_elements > 0 else 0

    # Extract skills dynamically from job_json and calculate skill score
    skills_pattern = r"(" + "|".join([re.escape(skill.lower()) for skill in job_json["skills"]]) + ")"
    skills_found = re.findall(skills_pattern, cv_text_cleaned)

    # Add skills to CV JSON with hasSkill and experience
    for skill in job_json["skills"]:
        skill_lower = skill.lower()
        has_skill = 1 if skill_lower in [s.lower() for s in skills_found] else 0

        # Extract experience for each skill if found
        experience_matches = re.findall(r'(\b(?:' + re.escape(skill_lower) + r')\b)[\s\S]*?(\d+)\s*years?', cv_text_cleaned)
        experience = next((int(years) for s, years in experience_matches if s.lower() == skill_lower), "N/A")

        # Add the skill with hasSkill and experience
        cv_json["skills"].append({
            "skill": skill,
            "hasSkill": has_skill,
            "experience": experience
        })

        # Add weight for each skill matched
        if has_skill == 1:
            cv_json["score"] += skill_weight

    # Extract matched qualifications from CV text
    job_qualifications = [clean_text(qual.lower()) for qual in job_json.get("qualifications", [])]
    matched_qualifications = []

    for job_qual in job_qualifications:
        if job_qual in cv_text_cleaned:
            matched_qualifications.append(job_qual.strip())
            cv_json["score"] += qualification_weight  # Add weight per matched qualification

    cv_json["matchedQualifications"] = matched_qualifications

    # Extract matched certifications
    job_certifications = job_json.get("certifications", [])
    matched_certifications = []

    for cert in job_certifications:
        cert_pattern = r"\b" + re.escape(cert) + r"\b"
        if re.search(cert_pattern, cv_text, re.IGNORECASE):
            matched_certifications.append(cert.strip())
            cv_json["score"] += certification_weight  # Add weight per matched certification

    # Extract all certifications in CV
    all_cert_pattern = r"(?:Certifications?|Cert)\s*[\n•\*]?\s*([^\n]+(?:\n\s*[\•\*]?\s*[^\n]+)*)"
    all_certifications_raw = re.findall(all_cert_pattern, cv_text, re.IGNORECASE)

    all_certifications_cleaned = []
    for cert in all_certifications_raw:
        certs = [c.strip().replace("\u2022", "").strip() for c in cert.splitlines() if c.strip()]
        all_certifications_cleaned.extend(certs)

    cv_json["matchedCertifications"] = matched_certifications

    additional_certifications = [
        cert for cert in set(all_certifications_cleaned)
        if not any(matched.lower() in cert.lower() for matched in matched_certifications)
        and "Issued By" not in cert
        and "Certificate Link" not in cert
        and any(keyword in cert.lower() for keyword in ["certification","certified","certifications", "certificate", "course", "program", "orientation"])
    ]

    cv_json["additionalCertifications"] = additional_certifications

    return cv_json


# Route for the home page (Job Upload and CV Upload)
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        job_description = request.form["job_description"]
        job_json = extract_details(job_description)
        
        # Handle multiple CV uploads
        cv_files = request.files.getlist("cv_files")
        cv_results = []
        
        for cv_file in cv_files:
            if cv_file.filename.endswith(".pdf"):
                cv_text = pdf_to_text(cv_file)
                cv_json = extract_cv_details(cv_text, job_json)
                
                # Calculate total weight for job JSON
                total_skills = len(job_json["skills"])
                total_qualifications = len(job_json["qualifications"])
                total_certifications = len(job_json["certifications"])
                total_weight = total_skills + total_qualifications + total_certifications

                # Count matches
                matched_skills = sum(skill["hasSkill"] for skill in cv_json["skills"])
                matched_qualifications = len(cv_json["matchedQualifications"])
                matched_certifications = len(cv_json["matchedCertifications"])

                # Calculate percentage score
                if total_weight > 0:  # Avoid division by zero
                    matching_percentage = (
                        (matched_skills + matched_qualifications + matched_certifications) / total_weight
                    ) * 100
                else:
                    matching_percentage = 0

                cv_json["score"] = round(matching_percentage, 2)  # Add percentage score to CV data
                
                cv_results.append(cv_json)
        
        session['cv_results'] = cv_results
        # Sorting in descending order by default
        cv_results.sort(key=lambda x: x["score"], reverse=True)

        return render_template("index.html", cv_results=cv_results)
    
    # Load cv_results from session if available, sorted in descending order
    cv_results = session.get('cv_results', [])
    cv_results.sort(key=lambda x: x["score"], reverse=True)
    
    return render_template("index.html", cv_results=cv_results)

# Route to view the details of a specific CV
@app.route("/cv/<int:cv_index>")
def view_cv(cv_index):
    # Retrieve cv_results from session
    cv_results = session.get('cv_results', [])

    # Ensure the index is valid
    if 0 <= cv_index < len(cv_results):
        cv_data = cv_results[cv_index]
        return render_template("result.html", cv_data=cv_data)
    else:
        return "CV not found", 404


if __name__ == "__main__":
    app.run(debug=True)
