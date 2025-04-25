import streamlit as st
import requests

st.set_page_config(page_title="AI Resume Picker", layout="wide")
st.title("📄 AI Resume Picker & Bias Buster")

st.markdown("Upload multiple resumes (PDFs) to analyze their ATS score and detect any bias.")

with st.form(key='criteria_form'):
    target_count = st.number_input("Candidates Needed", min_value=1, value=5)
    role = st.text_input("Target Role")
    
    # Organize skills by categories
    skill_categories = {
        "HR": ["Recruitment", "Employee Relations", "HRIS", "Performance Management", "Benefits Administration", "Training & Development", "Workday", "SAP SuccessFactors", "ATS Systems", "Talent Acquisition", "Compensation Planning", "Labor Laws"],
        "Sales": ["B2B Sales", "Lead Generation", "CRM", "Sales Strategy", "Account Management", "Business Development", "Sales Force", "Pipeline Management", "Contract Negotiation", "Solution Selling", "Enterprise Sales", "Sales Analytics"],
        "Marketing": ["Digital Marketing", "Content Strategy", "SEO", "Social Media", "Market Research", "Brand Management", "Google Analytics 4", "Marketing Automation", "Email Marketing", "Marketing Analytics", "Paid Advertising", "Marketing Attribution"],
        "Project Management": ["Agile", "Scrum", "Risk Management", "Project Planning", "Stakeholder Management", "JIRA", "Prince2", "Six Sigma", "PMI-ACP", "MS Project", "Kanban", "Portfolio Management"],
        "Finance": ["Financial Analysis", "Budgeting", "Forecasting", "Financial Reporting", "Excel", "QuickBooks", "SAP Finance", "Risk Assessment", "Investment Analysis", "Financial Modeling", "Bloomberg Terminal", "Business Valuation"],
        "Technical": ["Python", "Java", "JavaScript", "C++", "Go", "Rust", "SQL", "NoSQL", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Jenkins", "Terraform", "Git", "React", "Angular", "Vue.js", "Node.js", "Spring Boot", "Django", "FastAPI", "GraphQL", "Redis", "MongoDB", "PostgreSQL", "Microservices", "CI/CD", "DevOps"],
        "Operations": ["Supply Chain", "Inventory Management", "Process Improvement", "Quality Control", "Logistics", "Lean Six Sigma", "ERP Systems", "Warehouse Management", "Demand Planning", "Vendor Management", "Operations Analytics", "ISO Standards"],
        "Design": ["UI/UX", "Figma", "Adobe Creative Suite", "Wireframing", "Design Systems", "Prototyping", "Sketch", "InVision", "User Research", "Information Architecture", "Accessibility Design", "Motion Design"]
    }
    
    # Create expandable sections for each category
    selected_skills = []
    for category, skills in skill_categories.items():
        with st.expander(f"{category} Skills"):
            selected = st.multiselect(f"Select {category} Skills", skills, key=category)
            selected_skills.extend(selected)
    
    uploaded_files = st.file_uploader("Upload Resumes", type=["pdf"], accept_multiple_files=True)
    
    if st.form_submit_button("Analyze Resumes"):
        if not uploaded_files:
            st.warning("Please upload at least one resume.")
        else:
            with st.spinner("Uploading and analyzing..."):
                files = [("files", (file.name, file.read(), "application/pdf")) for file in uploaded_files]
                response = requests.post(
                    "http://127.0.0.1:8000/upload-resume/",
                    files=files,
                    json={
                        "target_count": target_count,
                        "role": role,
                        "required_skills": skills
                    }
                )

        if response.status_code == 200:
            data = response.json()

            st.subheader("🎯 ATS Results")
            for result in data["results"]:
                st.markdown(f"**Filename:** {result['filename']}")
                st.markdown(f"- **Score:** {result['score']}")
                st.markdown(f"- **Email:** {result['info']['email']}")
                st.markdown(f"- **Location:** {result['info']['location']}")
                st.markdown(f"- **Institute:** {result['info']['institute']}")
                st.markdown("---")

            st.subheader("⚖️ Bias Report")
            for key, val in data["bias_report"].items():
                st.markdown(f"- **{key.replace('_', ' ').title()}:** {val}")
        else:
            st.error("Something went wrong with the backend.")
