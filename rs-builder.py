import streamlit as st
from io import BytesIO
from xhtml2pdf import pisa
import json
import requests
import os
import socket
from openai import OpenAI
import datetime
import yaml
from github import Github  # pip install PyGithub
from github.GithubException import GithubException

st.set_page_config(page_title="Resume Builder AI", layout="wide")
# — Cloud detection & GitHub setup
def is_cloud(): return "streamlit" in socket.gethostname().lower()

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]  # e.g. "username/repo"
GITHUB_PATH = st.secrets.get("GITHUB_PATH", "resumes/")

gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(GITHUB_REPO)

# — Prompt template example
# Pre-filled user prompt
DEFAULT_USER_PROMPT = (
    "Please generate a resume profile for the role of warehouse assistant in Melbourne. "
    "Include 9 key skills based on the experience: "
    "1. Worked as a warehouse assistant in Melbourne recently."
)

# Detailed system prompt (controls structure and style)
SYSTEM_PROMPT = """
You are a resume content generator. Your task is to create structured JSON with the following fields:
- "profile_summary": A simple, impressive, 3–4 line paragraph. for eg: Friendly and motivated customer service professional with excellent communication skills and a proven ability to handle customer inquiries efficiently and professionally. Experienced in front desk and hospitality roles, with strong skills in problem-solving, multitasking, and maintaining a positive and welcoming environment. Quick to learn new systems and dedicated to providing exceptional service that exceeds customer expectations.
- "key_skills": A list of 6–9 relevant skills, covering both soft and core technical skills.
- "work_experience": A list of experiences, each containing:
    - from_date
    - to_date
    - position
    - workplace
    - location
    - description: A list of 6 short bullet points describing responsibilities
    - achievements: A list with one impactful achievement

Respond strictly in JSON format like:
{
  "profile_summary": "...",
  "key_skills": ["...", "..."],
  "work_experience": [
    {
      "from_date": "...",
      "to_date": "...",
      "position": "...",
      "workplace": "...",
      "location": "...",
      "description": ["...", "..."],
      "achievements": ["..."]
    }
  ]
}
"""

@st.cache_data(ttl=60)
def load_latest_resumes():
    try:
        contents = repo.get_contents(GITHUB_PATH)
        resume_files = [f for f in contents if f.name.startswith("resume_") and f.name.endswith(".json")]
        # Sort by timestamp parsed from filename
        resume_files.sort(
            key=lambda f: datetime.datetime.strptime(f.name.replace("resume_", "").replace(".json", ""), "%Y-%m-%d_%H%M"),
            reverse=True
        )
        latest_files = resume_files[:10]
        return latest_files
    except Exception as e:
        st.sidebar.error(f"Failed to load past resumes: {e}")
        return []
        
if st.sidebar.button("➕ New Resume"):
    st.session_state.prompt = DEFAULT_USER_PROMPT
    st.session_state.resume_data = None
    
st.sidebar.title("🗂 Past Prompts / Resumes")
if "history" not in st.session_state:
    st.session_state.history = []

latest_files = load_latest_resumes()
for f in latest_files:
    label = f.name.replace("resume_", "").replace(".json", "")
    if st.sidebar.button(f"Load {label}"):
        file_content = repo.get_contents(f.path)
        try:
            data = json.loads(file_content.decoded_content.decode())
            st.session_state.prompt = DEFAULT_USER_PROMPT  # optional: keep prompt as is
            st.session_state.resume_data = data
            st.session_state.exp_count = len(data.get("work_experience", []))
            st.success(f"✅ Loaded resume from: {f.name}")
        except Exception as e:
            st.sidebar.error(f"❌ Error parsing {f.name}: {e}")

# — Main prompt editor
col_logo, col_title = st.columns([2, 8])
with col_logo:
    st.image("logo.png", use_container_width=True)  # ✅ updated
with col_title:
    st.markdown("<h1 style='margin-top: 10px;'>BUBU Resume Generator</h1>", unsafe_allow_html=True)
prompt = st.text_area("Enter your prompt:", st.session_state.get("prompt", DEFAULT_USER_PROMPT), height=150)

if st.button("🧩 Generate from AI"):
    with st.spinner("Calling OpenAI…"):
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3
            )
            reply = response.choices[0].message.content
            ai_json = json.loads(reply)

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
            st.session_state.resume_data = ai_json
            st.session_state.exp_count = len(ai_json.get("work_experience", []))  # <- Force update!
            st.session_state.history.append({
                "timestamp": timestamp,
                "prompt": prompt,
                "data": ai_json
            })

            filename = f"{GITHUB_PATH}resume_{timestamp}.json"

            try:
                repo.get_contents(filename)
                st.warning(f"⚠️ File already exists: {filename}. Skipping upload.")
            except GithubException as e:
                if e.status == 404:
                    repo.create_file(
                        path=filename,
                        message=f"Add resume {filename}",
                        content=json.dumps(ai_json, indent=2)
                    )
                    st.success(f"✅ Uploaded to GitHub: {filename}")
                else:
                    st.error(f"❌ GitHub error: {e}")
                    st.stop()

            st.success("✅ Resume JSON generated successfully!")
        except Exception as e:
            st.error(f"❌ OpenAI or JSON parsing error: {e}")

# — Load defaults or data
resume_data = st.session_state.get("resume_data", {}) or {}
# Force update exp_count to match the number of experiences loaded
if "exp_count" not in st.session_state:
    st.session_state.exp_count = max(1, len(resume_data.get("work_experience", [])))

if not resume_data:
    st.info("🤖 Generate resume using the AI button above.")

# — Editable fields form
# Contact & education unchanged, from resume_data
st.subheader("Contact Info")
contact_secret = st.secrets["CONTACT"]
name = st.text_input("Name" , contact_secret.get("name",""))
number = st.text_input("Contact Number", contact_secret.get("number", ""))
email = st.text_input("Email", contact_secret.get("email", ""))
address = st.text_input("Address", contact_secret.get("address", ""))

st.subheader("Profile Summary")
profile_summary = st.text_area("Profile Summary", resume_data.get("profile_summary", ""))

st.subheader("Key Skills")
key_skills = resume_data.get("key_skills", [])
skills = []
for i in range(9):
    skills.append(st.text_input(f"Skill {i+1}", key_skills[i] if i < len(key_skills) else "", key=f"skill_{i}"))
st.subheader("Education History")
edu_secret = st.secrets["EDUCATION_HISTORY"]
education = []
for idx, edu in enumerate(edu_secret):
    st.markdown(f"### Education {idx + 1}")
    course = st.text_input(f"Course {idx+1}", edu.get("course", ""), key=f"course_{idx}")
    institute = st.text_input(f"Institute {idx+1}", edu.get("institute", ""), key=f"institute_{idx}")
    from_date = st.text_input(f"From Year {idx+1}", edu.get("from_date", ""), key=f"edufrom_{idx}")
    to_date = st.text_input(f"To Year {idx+1}", edu.get("to_date", ""), key=f"eduto_{idx}")
    location = st.text_input(f"Location {idx+1}", edu.get("location", ""), key=f"edu_location_{idx}")  # 🔧 Fix

    education.append({
        "course": course,
        "institute": institute,
        "from_date": from_date,
        "to_date": to_date,
        "location": location
    })

# Work experience
st.subheader("Work Experience")
existing = resume_data.get("work_experience", [])
exp_count = st.session_state.exp_count
col1, col2 = st.columns(2)
if col1.button("➕ Add Experience"):
    exp_count += 1
if col2.button("➖ Remove"):
    exp_count = max(1, exp_count - 1)
st.session_state.exp_count = exp_count

experiences = []
for i in range(exp_count):
    st.markdown(f"### Experience {i+1}")
    d = existing[i] if i < len(existing) else {}
    from_date = st.text_input(f"From Date {i+1}", d.get("from_date",""), key=f"from_{i}")
    to_date = st.text_input(f"To Date {i+1}", d.get("to_date",""), key=f"to_{i}")
    position = st.text_input(f"Position {i+1}", d.get("position",""), key=f"pos_{i}")
    workplace = st.text_input(f"Workplace {i+1}", d.get("workplace",""), key=f"work_{i}")
    location = st.text_input(f"Location {i+1}", d.get("location",""), key=f"loc_{i}")
    descs = d.get("description", [])
    descriptions = [st.text_input(f"Desc {i+1}-{j+1}", descs[j] if j< len(descs) else "", key=f"desc_{i}_{j}") for j in range(max(len(descs),3))]
    achs = d.get("achievements", [])
    achievements = [st.text_input(f"Achieve {i+1}-{j+1}", achs[j] if j< len(achs) else "", key=f"ach_{i}_{j}") for j in range(max(len(achs),1))]
    experiences.append({
        "from_date": from_date, "to_date": to_date,
        "position": position, "workplace": workplace,
        "location": location, "description": descriptions,
        "achievements": achievements
    })
st.subheader("References")
existing_refs = resume_data.get("reference_details", [])
ref_count = st.number_input(
    "Number of references",
    min_value=0, max_value=5,
    value=max(len(existing_refs), 0),  # prefill if any exist
    step=1,
    key="ref_count"  # ✅ keeps the value across reruns (e.g., when you click Preview)
)
references = []
for i in range(ref_count):
    prev = existing_refs[i] if i < len(existing_refs) else {}
    st.markdown(f"### Reference {i+1}")
    ref_name = st.text_input(f"Name {i+1}", prev.get("name", ""), key=f"ref_name_{i}")
    ref_pos = st.text_input(f"Position {i+1}", prev.get("position", ""), key=f"ref_pos_{i}")
    ref_contact = st.text_input(f"Contact {i+1}", prev.get("contact", ""), key=f"ref_contact_{i}")
    references.append({"name": ref_name, "position": ref_pos, "contact": ref_contact})

# ✅ Keep only refs where at least one field is filled
references = [r for r in references if any(v.strip() for v in r.values() if isinstance(v, str))]

def build_html(name, contact, summary, skills, education, experiences, references):
    def bullet_list(items):
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items if item) + "</ul>"

    html = f"""
    <html>
    <head>
        <style>
            @page {{
                size: A4;
                margin: 15mm 15mm 15mm 15mm;
            }}
            body {{
                width: 180mm;
                font-family: 'Arial', sans-serif;
                font-size: 10pt;
                line-height: 1.22; /* slightly tighter than 1.3 */
                color: #000;
                margin: 0;
                padding: 0;
            }}
            h1 {{
                font-size: 20pt;  
                margin-bottom: 1px; /* reduced further */
            }}
            .contact {{
                font-size: 10pt;
                margin-bottom: 6px; /* reduced gap after contact */
                line-height: 1.15;  /* tighter lines */
            }}
            .contact div {{
                margin-bottom: 0;  /* no gap between lines */
            }}
            .subheading {{
                font-size: 12pt;
                font-weight: bold;
                color: #003366;
                margin-top: 8px;  /* less gap between sections */
                margin-bottom: 2px;
            }}
            .bold {{
                font-weight: bold;
            }}
            .section {{
                margin-bottom: 4px; /* tighter spacing between entries */
            }}
            ul {{
                margin: 1px 0 0 15px;
                padding-left: 0;
            }}
            li {{
                margin-bottom: 1px; /* less gap between bullets */
            }}
            em {{
                font-style: italic;
                color: #000;
                display: block;
                margin: 0;
            }}
            .experience-meta {{
                margin-top: 0;
                margin-bottom: 0;
            }}
        </style>
    </head>
    <body>
        <h1>{contact.get('name', '')}</h1>
        <div class="contact">
            <div><span class="bold">Address:</span> {contact.get('address', '')}</div>
            <div><span class="bold">Phone:</span> {contact.get('number', '')}</div>
            <div><span class="bold">Email:</span> {contact.get('email', '')}</div>
        </div>

        <div class="subheading">Profile</div>
        <div>{summary}</div>

        <div class="subheading">Key Skills</div>
        {bullet_list(skills)}

        <div class="subheading">Education</div>
    """
    for edu in education:
        html += f"""
        <div class="section">
            <div class="bold">{edu.get('course', '')}</div>
            <div><em>{edu.get('institute', '')}, {edu.get('location', '')}</em></div>
            <div>{edu.get('from_date', '')} – {edu.get('to_date', '')}</div>
        </div>
        """

    html += '<div class="subheading">Employment History</div>'
    for exp in experiences:
        html += f"""
        <div class="section">
            <div class="bold">{exp.get('position', '')}</div>
            <div class="experience-meta">{exp.get('workplace', '')} – {exp.get('location', '')}</div>
            <div class="experience-meta">{exp.get('from_date', '')} – {exp.get('to_date', '')}</div>
            {bullet_list(exp.get('description', []))}
        """
        if exp.get("achievements"):
            html += "<div><em>Achievements</em>" + bullet_list(exp["achievements"]) + "</div>"
        html += "</div>"

    if references:
        html += '<div class="subheading">Reference</div>'
        for ref in references:
            html += f"""
            <div class="section">
                <div class="bold">{ref.get('name', '')}</div>
                <div>{ref.get('position', '')} – {ref.get('contact', '')}</div>
            </div>
            """

    html += "</body></html>"
    return html

def convert_html_to_pdf(source_html):
    output = BytesIO()
    pisa_status = pisa.CreatePDF(src=source_html, dest=output)
    return None if pisa_status.err else output.getvalue()

if st.button("💡 Preview HTML"):
    # Truncate key skills if more than 1 experience
    adjusted_skills = skills[:7] if len(experiences) >= 2 else skills
    # Truncate education to 1 section if more than 1 experience
    adjusted_education = education[:1] if len(experiences) >= 2 else education
    # Truncate each experience description to 5 points if more than 1 experience
    adjusted_experiences = []
    for exp in experiences:
        trimmed_desc = exp.get("description", [])[:5] if len(experiences) >= 2 else exp.get("description", [])
        trimmed_ach = exp.get("achievements", [])  # leave achievement unchanged
        adjusted_experiences.append({
            **exp,
            "description": trimmed_desc,
            "achievements": trimmed_ach,
        })
    html = build_html(
        name=resume_data.get("name", ""),
        contact={"name": name, "number": number, "email": email, "address": address},
        summary=profile_summary,
        skills=adjusted_skills,
        education=adjusted_education,
        experiences=adjusted_experiences,
        references=references  # ✅ use the collected references
    )
    st.session_state.html_preview = html

if "html_preview" in st.session_state:
    st.subheader("🔍 HTML Preview")
    st.components.v1.html(st.session_state.html_preview, height=800, scrolling=True)
    if st.button("📄 Generate & Download PDF"):
        pdf_bytes = convert_html_to_pdf(st.session_state.html_preview)
        if pdf_bytes:
            st.success("✅ PDF generated!")
            st.download_button("⬇️ Download Resume", data=pdf_bytes, file_name="resume.pdf", mime="application/pdf")
        else:
            st.error("❌ PDF generation failed")






