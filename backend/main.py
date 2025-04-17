from fastapi import FastAPI, File, UploadFile
from pdfminer.converter import HTMLConverter
from pdfminer.high_level import extract_text
import tempfile
import re
import phonenumbers
from geotext import GeoText
from typing import List



def normalize_field(value, unwanted_prefixes=None):
    if not value:
        return None
    value = value.strip().lower()

    if unwanted_prefixes:
        for prefix in unwanted_prefixes:
            if value.startswith(prefix):
                value = value.replace(prefix, "")
    value = value.strip()
    
    # Filter out junk values
    # More comprehensive junk value filtering
    junk_values = {"name", "unknown", "location", "loc", "city", "state", "institute", "college", "university", "null", "nil", "none"}
    if value in junk_values:
        return None

    return value


def detect_bias(results):
    from collections import Counter

    location_counts = Counter()
    institute_counts = Counter()
    total_valid = 0

    for res in results:
        info = res.get("info", {})
        
        # Apply normalized filtering to both fields
        loc = normalize_field(info.get("location"), ["location:", "loc:", "city:"])
        inst = normalize_field(info.get("institute"), ["institute:", "university:", "college:"])

        # Additional validation for geographic relevance
        if loc and len(loc.split()) > 3:  # Filter overlong location strings
            loc = None

        if loc:
            location_counts[loc] += 1
        if inst:
            institute_counts[inst] += 1

        # Only count towards total if location is valid
        if loc:
            total_valid += 1

    # Avoid division by zero
    if total_valid == 0:
        return {"message": "Not enough valid data to detect bias."}

    report = {}

    for loc, count in location_counts.items():
        if count / total_valid > 0.5:
            report["location_bias"] = f"Bias detected towards candidates from location: {loc.title()}"
            break

    for inst, count in institute_counts.items():
        if count / total_valid > 0.5:
            report["institute_bias"] = f"Bias detected towards institute: {inst.upper()}"
            break

    if not report:
        report["message"] = "No significant bias detected."

    return report





def ats_score_with_bias(info):
    score = 50

    # Bias for email domain
    if info["email"]:
        email = info["email"].lower()
        if "iit" in email:
            score += 15
        elif "gmail.com" in email:
            score += 5

    # Bias for location
    if info["location"]:
        if any(city in info["location"].lower() for city in ["delhi", "bengaluru", "mumbai"]):
            score += 10

    # Bias for top institutes
    if info["institute"]:
        if any(kw in info["institute"].lower() for kw in ["iit", "iiit", "nit"]):
            score += 15

    # Bias based on education text
    if "bachelor" in info.get("education", "").lower() or "master" in info.get("education", "").lower():
        score += 5

    # Bonus for name
    if info["name"] and info["name"][0].lower() in ['a', 's']:
        score += 5

    return min(score, 100)



def extract_candidate_info(text: str):
    info = {}

    # Extract email
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    info["email"] = email_match.group(0) if email_match else None

    # Extract phone number
    phone = None
    for match in phonenumbers.PhoneNumberMatcher(text, "IN"):
        phone = match.raw_string
        break
    info["phone"] = phone

    # Guess name from top of resume (first 5 lines)
    lines = text.strip().split('\n')[:5]
    possible_name = [line.strip() for line in lines if len(line.strip().split()) <= 4 and len(line.strip()) > 3]
    info["name"] = possible_name[0] if possible_name else "Name not found"

    # Try extracting a location (city/state)
    # Improved location detection with geotext
    locations = GeoText(text).cities
    info["location"] = locations[0] if locations else None
    
    # Fallback regex pattern for state detection
    if not info["location"]:
        state_match = re.search(r"\b(?:Andhra Pradesh|Arunachal Pradesh|Assam|Bihar|Chhattisgarh|Goa|Gujarat|Haryana|Himachal Pradesh|Jharkhand|Karnataka|Kerala|Madhya Pradesh|Maharashtra|Manipur|Meghalaya|Mizoram|Nagaland|Odisha|Punjab|Rajasthan|Sikkim|Tamil Nadu|Telangana|Tripura|Uttar Pradesh|Uttarakhand|West Bengal)\b", text, re.IGNORECASE)
        info["location"] = state_match.group(0).title() if state_match else None

    # Try extracting college/university
    edu_match = re.search(r"(?:University|Institute|College|IIT|NIT|IIIT)[^\n]{0,50}", text)
    info["institute"] = edu_match.group(0).strip() if edu_match else None

    return info


app = FastAPI()

@app.post("/upload-resume/")
async def bias_check(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        text = extract_text(tmp_path)
        info = extract_candidate_info(text)
        score = ats_score_with_bias(info)

        results.append({
            "filename": file.filename,
            "info": info,
            "score": score
        })

    bias_report = detect_bias(results)
    return {"results": results, "bias_report": bias_report}

