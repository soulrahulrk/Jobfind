from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("JOBFINDER_DATA_DIR", BASE_DIR / "data"))
CONFIG_DIR = Path(os.getenv("JOBFINDER_CONFIG_DIR", BASE_DIR / "config"))
DB_PATH = Path(os.getenv("JOBFINDER_DB_PATH", DATA_DIR / "jobfinder.sqlite3"))
RESUME_PATH = Path(os.getenv("JOBFINDER_RESUME_PATH", r"C:\Users\rahul\Downloads\rahul.pdf"))

TIMEZONE = "Asia/Kolkata"
SALARY_FLOOR_INR_MONTHLY = 10_000

ROLE_TERMS = [
    "ai ml fresher",
    "machine learning fresher",
    "data science fresher",
    "python developer fresher",
    "fastapi python",
    "llm engineer intern",
    "nlp fresher",
    "computer vision fresher",
    "data analyst fresher",
]

SAVED_SEARCHES = [
    {
        "name": "LinkedIn AI ML Fresher India",
        "url": "https://www.linkedin.com/jobs/search/?keywords=ai%20ml%20fresher&location=India",
    },
    {
        "name": "LinkedIn Python Fresher India",
        "url": "https://www.linkedin.com/jobs/search/?keywords=python%20developer%20fresher&location=India",
    },
    {
        "name": "Naukri Data Science Fresher",
        "url": "https://www.naukri.com/data-science-fresher-jobs",
    },
    {
        "name": "Internshala AI ML Internships",
        "url": "https://internshala.com/internships/artificial-intelligence-ai,python,machine-learning-internship/",
    },
    {
        "name": "Wellfound Machine Learning India",
        "url": "https://wellfound.com/jobs?keyword=machine%20learning&location=India",
    },
    {
        "name": "Cutshort Python Fresher",
        "url": "https://cutshort.io/jobs/python-fresher-jobs",
    },
]

DEFAULT_PROFILE = {
    "name": "Rahul",
    "location": "India",
    "phone": "",
    "email": "",
    "linkedin": "",
    "github": "",
    "leetcode": "",
    "summary": (
        "Aspiring AI/ML Engineer with hands-on experience building LLM-powered "
        "applications, recommendation systems, computer vision systems, and "
        "predictive models."
    ),
    "education": "B.Tech Computer Science (AI & ML), Panipat Institute of Engineering and Technology",
    "salary_floor_inr_monthly": SALARY_FLOOR_INR_MONTHLY,
    "preferred_roles": [
        "AI/ML Engineer",
        "Data Scientist",
        "Machine Learning Engineer",
        "Python Backend Developer",
        "FastAPI Developer",
        "LLM/NLP Engineer",
        "Computer Vision Engineer",
        "Data Analyst",
    ],
    "skills": [
        "Python",
        "SQL",
        "Scikit-learn",
        "TensorFlow",
        "LangChain",
        "LangGraph",
        "NumPy",
        "Pandas",
        "Matplotlib",
        "Seaborn",
        "OpenCV",
        "Git",
        "Docker",
        "FastAPI",
        "Power BI",
        "PostgreSQL",
        "MySQL",
        "ChromaDB",
        "LLM Integration",
        "Semantic Search",
        "NLP",
        "Deep Learning",
        "Model Deployment",
        "API Development",
    ],
    "projects": [
        "AI Voyage Estimation & Decision System",
        "SHL Assessment Recommendation Engine",
        "Placement LLM - College Placement Management System",
    ],
    "leetcode_solved": "1020+",
    "raw_text": "",
}
