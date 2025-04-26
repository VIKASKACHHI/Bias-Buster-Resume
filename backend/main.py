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

    # Detect all locations with significant bias
    location_biases = [
        f"Bias towards {loc.title()} ({count/total_valid:.0%})"
        for loc, count in location_counts.items()
        if count / total_valid > 0.3  # Lowered threshold to 30%
    ]
    if location_biases:
        report["location_biases"] = location_biases

    # Detect all institutes with significant bias
    institute_biases = [
        f"Bias towards {inst.upper()} ({count/total_valid:.0%})"
        for inst, count in institute_counts.items()
        if count / total_valid > 0.3  # Lowered threshold to 30%
    ]
    if institute_biases:
        report["institute_biases"] = institute_biases

    if not report:
        report["message"] = "No significant bias detected."

    return report





def ats_score_with_bias(info, criteria):
    score = 50

    # Bias for email domain (hardcoded for demonstration, not configurable by recruiter)
    if info["email"]:
        email = info["email"].lower()
        if "iit" in email:
            score += 15
        elif "gmail.com" in email:
            score += 5

    # Bias for location (hardcoded for demonstration, not configurable by recruiter)
    if info["location"]:
        metro_cities = ["delhi", "bengaluru", "mumbai", "chennai", "kolkata"]
        if any(city in info["location"].lower() for city in metro_cities):
            score += 10

    # Bias for top institutes (hardcoded for demonstration, not configurable by recruiter)
    if info["institute"]:
        if any(kw in info["institute"].lower() for kw in ["iit", "iiit", "nit"]):
            score += 15

    # Bias based on education text (hardcoded for demonstration, not configurable by recruiter)
    if "bachelor" in info.get("education", "").lower() or "master" in info.get("education", "").lower():
        score += 5

    # Bonus for name (hardcoded for demonstration, not configurable by recruiter)
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

    # Try extracting college/university with improved pattern
    edu_pattern = r"(?:(?:B\.?Tech|M\.?Tech|Degree|Graduate|Education at|Student at|(?:Indian Institute of|National Institute of|[A-Z][a-zA-Z]+ University|[A-Z][a-zA-Z]+ College|IIT|NIT|IIIT))[^\n,.]{2,100})"
    edu_matches = re.finditer(edu_pattern, text)
    best_match = None
    for match in edu_matches:
        candidate = match.group(0).strip()
        # Filter out matches that are too short or contain unwanted words
        if len(candidate.split()) >= 2 and not any(x in candidate.lower() for x in ['address', 'contact', 'phone', 'email', 'certification', 'course', 'achievement', 'exam', 'test', 'score']):
            best_match = candidate
            break
    info["institute"] = best_match

    return info


app = FastAPI()

from pydantic import BaseModel

class SelectionCriteria(BaseModel):
    target_count: int
    role: str
    required_skills: List[str]

@app.post("/upload-resume/")
async def bias_check(
    files: List[UploadFile] = File(...),
    criteria: SelectionCriteria = None
):
    results = []
    for file in files:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        text = extract_text(tmp_path)
        info = extract_candidate_info(text)
        score = ats_score_with_bias(info, criteria)

        results.append({
            "filename": file.filename,
            "info": info,
            "score": score
        })

    bias_report = detect_bias(results)
    return {"results": results, "bias_report": bias_report}

