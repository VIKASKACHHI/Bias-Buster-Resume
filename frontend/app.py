import streamlit as st
import requests

st.set_page_config(page_title="AI Resume Picker", layout="wide")
st.title("📄 AI Resume Picker & Bias Buster")

st.markdown("Upload multiple resumes (PDFs) to analyze their ATS score and detect any bias.")

uploaded_files = st.file_uploader("Upload Resumes", type=["pdf"], accept_multiple_files=True)

if st.button("Analyze Resumes"):
    if not uploaded_files:
        st.warning("Please upload at least one resume.")
    else:
        with st.spinner("Uploading and analyzing..."):
            files = [("files", (file.name, file.read(), "application/pdf")) for file in uploaded_files]
            response = requests.post("http://127.0.0.1:8000/upload-resume/", files=files)

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
