import streamlit as st
from io import BytesIO
from xhtml2pdf import pisa
import json
import requests
import os
import socket
import openai
import datetime
import yaml
from github import Github  # pip install PyGithub

st.set_page_config(page_title="Resume Builder AI", layout="wide")

# — Cloud detection & GitHub setup
def is_cloud(): return "streamlit" in socket.gethostname().lower()

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]  # e.g. "username/repo"
GITHUB_PATH = st.secrets.get("GITHUB_PATH", "resumes/")

gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(GITHUB_REPO)

# — Prompt template example
EXAMPLE_PROMPT = '''
Generate JSON with keys: profile_summary (string), key_skills (list of strings),
work_experience (list of records with from_date, to_date, position, workplace, location,
description (list), achievements (list)). Use this example format.

{ "profile_summary": "…", "key_skills": ["…"], "work_experience": [ { "from_date": "…", ... } ] }
'''

# Sidebar: past queries
st.sidebar.title("🗂 Past Prompts / Resumes")
if "history" not in st.session_state:
    st.session_state.history = []

if st.sidebar.button("➕ New Resume"):
    st.session_state.prompt = EXAMPLE_PROMPT
    st.session_state.resume_data = None

for idx, entry in enumerate(st.session_state.history):
    if st.sidebar.button(f"Load {entry['timestamp']}"):
        st.session_state.prompt = entry["prompt"]
        st.session_state.resume_data = entry["data"]

# — Main prompt editor
st.header("🧠 AI‑Assisted Resume Generator")
prompt = st.text_area("Enter your prompt (edit as needed):", st.session_state.get("prompt", EXAMPLE_PROMPT), height=200)

if st.button("🧩 Generate from AI"):
    with st.spinner("Calling OpenAI…"):
        response = openai.ChatCompletion.create(
            model="gpt‑4",
            messages=[
                {"role":"system", "content":"You are a resume JSON generator."},
                {"role":"user", "content": prompt},
            ],
            temperature=0.2
        )
        try:
            ai_json = json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error("❌ Failed to parse JSON: " + str(e))
            st.stop()
        st.success("✅ AI JSON generated")
        st.session_state.resume_data = ai_json
        st.session_state.history.append({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d_%H%M"),
            "prompt": prompt,
            "data": ai_json
        })
        # optionally save to GitHub
        filename = f"{GITHUB_PATH}resume_{st.session_state.history[-1]['timestamp']}.json"
        repo.create_file(path=filename, message=f"Add resume {filename}", content=json.dumps(ai_json, indent=2))

# — Load defaults or data
resume_data = st.session_state.get("resume_data", {}) or {}
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
    
    education.append({
        "course": course,
        "institute": institute,
        "from_date": from_date,
        "to_date": to_date
    })
# Work experience
st.subheader("Work Experience")
existing = resume_data.get("work_experience", [])
exp_count = st.session_state.get("exp_count", len(existing) or 1)
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
                line-height: 1.3;
                color: #000;
            }}
            h1 {{
                font-size: 16pt;
                margin-bottom: 4px;
            }}
            .contact {{
                font-size: 9pt;
                margin-bottom: 15px;
            }}
            .contact div {{
                margin-bottom: 2px;
            }}
            .subheading {{
                font-size: 11pt;
                font-weight: bold;
                color: #003366;
                margin-top: 16px;
                margin-bottom: 5px;
            }}
            .bold {{
                font-weight: bold;
            }}
            .section {{
                margin-bottom: 8px; /* tighter spacing */
            }}
            ul {{
                margin: 3px 0 0 15px;  /* reduced top margin between bullet items */
                padding-left: 0;
            }}
            li {{
                margin-bottom: 2px;  /* tighter space between skill lines */
            }}
            em {{
                font-style: italic;
                color: #000;
                display: block;
                margin-top: 1px;  /* less space between course and college name */
                margin-bottom: 1px;  /* less space between college name and years */
            }}
            .experience-meta {{
                margin-top: 1px;
                margin-bottom: 1px;  /* tighter block between position, location, and year */
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
            <div><em>{edu.get('institute', '')}</em></div>
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
        html += '<div class="subheading">Referees</div>'
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
    html = build_html(
        name=resume_data.get("name", ""),
        contact={"name": name, "number": number, "email": email, "address": address},
        summary=profile_summary,
        skills=skills,
        education=education,
        experiences=experiences,
        references=resume_data.get("reference_details", [])
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
