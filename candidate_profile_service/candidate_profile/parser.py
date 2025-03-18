import re
import spacy
import fitz
from .logger import logger
import functools
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dateutil.parser import parse as date_parse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.conf import settings
from .models import Candidate, Education, WorkExperience, Skill, Certification

class ResumeParserError(Exception):
    """Custom exception for resume parsing errors."""
    pass

class ResumeParser:
    CONFIG = {
        "email_pattern": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "phone_pattern": r'(?:(?:\+|00)\d{1,3}[\s.-]*)\d{6,10}',
        "linkedin_pattern": r'(?:http[s]?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9-]+',
        "github_pattern": r'(?:http[s]?://)?(?:www\.)?github\.com/[a-zA-Z0-9-]+',
        "date_pattern": r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2})\s*/?\s*\d{2,4}|\d{4})\s*[-–]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2})\s*/?\s*\d{2,4}|\d{4}|Present|Current)?',
        "section_headers": [
            "summary", "professional summary", "objective", "profile",
            "experience", "professional experience", "work experience", "employment history",
            "education", "academic background",
            "skills", "technical skills", "technical and soft skills", "core competencies",
            "certifications", "licenses", "credentials",
            "projects", "personal projects", "portfolio",
            "achievements", "accomplishments",
            "personal details", "contact information"
        ],
        "bullet_markers": ['•', '-', '*', '◦', '·', '➢', '✓'],
        "min_skill_length": 2,
        "max_description_lines": 20
    }

    def __init__(self, candidate_id: str, job_role: str, job_description: str, key_skills: List[str]):
        self.candidate_id = candidate_id
        self.job_role = job_role
        self.job_description = job_description
        self.key_skills = key_skills
        try:
            self.nlp = spacy.load("en_core_web_lg")
        except OSError:
            logger.warning("en_core_web_lg not found. Using en_core_web_sm.")
            self.nlp = spacy.load("en_core_web_sm")

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        @functools.lru_cache(maxsize=128)
        def _extract(pdf_bytes: bytes) -> str:
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                if not text.strip():
                    raise ResumeParserError("Empty or unreadable PDF content")
                logger.debug(f"Extracted text: {text[:100]}...")
                return text
            except Exception as e:
                logger.error(f"Failed to extract text from PDF: {str(e)}")
                raise ResumeParserError(f"Failed to extract text from PDF: {str(e)}")
        return _extract(pdf_content)

    def find_section_bounds(self, lines: List[str]) -> Dict[str, Tuple[int, Optional[int]]]:
        bounds = {}
        for i, line in enumerate(lines):
            line = line.strip()
            lower_line = line.lower()
            for header in self.CONFIG["section_headers"]:
                if header in lower_line and len(lower_line.split()) <= 5:
                    if bounds and list(bounds.keys())[-1] != line:
                        bounds[list(bounds.keys())[-1]] = (bounds[list(bounds.keys())[-1]][0], i)
                    bounds[line] = (i + 1, None)
                    logger.debug(f"Found section: {line} at line {i}")
                    break
        if bounds:
            last_key = list(bounds.keys())[-1]
            bounds[last_key] = (bounds[last_key][0], len(lines))
        else:
            bounds["personal details"] = (0, len(lines))
        return bounds

    def get_section_lines(self, lines: List[str], bounds: Dict, sections: List[str]) -> List[str]:
        result = []
        seen_indices = set()
        for section in sections:
            for key in bounds:
                if section.lower() in key.lower():
                    start, end = bounds[key]
                    cleaned_lines = [line.strip() for line in lines[start:end] if line.strip() and start not in seen_indices]
                    result.extend(cleaned_lines)
                    seen_indices.update(range(start, end))
                    logger.debug(f"Extracted {len(cleaned_lines)} lines for {section}")
                    break
        return result

    def is_bullet_line(self, line: str) -> bool:
        return any(line.startswith(marker) for marker in self.CONFIG["bullet_markers"]) or \
               (line and not line[0].isupper() and not re.match(r'^\d+\b', line))

    def parse_personal_info(self, doc: spacy.tokens.Doc, text: str) -> Dict:
        lines = text.split('\n')
        personal_info = {
            "first_name": None,
            "last_name": None,
            "location": None,
            "email": next(iter(re.findall(self.CONFIG["email_pattern"], text)), None),
            "phone": next(iter(re.findall(self.CONFIG["phone_pattern"], text)), None),
            "linkedin": next(iter(re.findall(self.CONFIG["linkedin_pattern"], text)), None),
            "github": next(iter(re.findall(self.CONFIG["github_pattern"], text)), None)
        }

        for ent in doc.ents:
            if ent.label_ == "PERSON" and not personal_info["first_name"] and len(ent.text.split()) >= 2:
                names = ent.text.split()
                personal_info["first_name"] = names[0]
                personal_info["last_name"] = " ".join(names[1:])
                logger.debug(f"NER found name: {ent.text}")
            elif ent.label_ in ["GPE", "LOC"] and not personal_info["location"]:
                personal_info["location"] = ent.text
                logger.debug(f"NER found location: {ent.text}")

        if not personal_info["first_name"]:
            for line in lines:
                if (re.search(r'[A-Za-z]+\s+[A-Za-z]+', line) and not any(h.lower() in line.lower() for h in self.CONFIG["section_headers"])
                    and len(line.split()) <= 5 and personal_info["email"] not in line):
                    names = line.strip().split()
                    personal_info["first_name"] = names[0]
                    personal_info["last_name"] = " ".join(names[1:]) if len(names) > 1 else "Unknown"
                    logger.debug(f"Heuristic found name: {line.strip()}")
                    break

        if not personal_info["location"]:
            for line in lines:
                if "India" in line or re.search(r'[A-Za-z]+,\s*[A-Za-z]+', line):
                    personal_info["location"] = line.strip()
                    logger.debug(f"Heuristic found location: {line.strip()}")
                    break

        if not personal_info["first_name"]:
            personal_info["first_name"] = "Unknown"
            personal_info["last_name"] = "Unknown"
            logger.warning("No valid name found, using placeholder.")
        return personal_info

    def parse_skills(self, lines: List[str]) -> List[str]:
        skills = set(self.key_skills)
        for line in lines:
            clean_line = re.sub(r'^[•\-\*◦]\s*', '', line).strip()
            if ':' in clean_line:
                parts = re.split(r':', clean_line)[1].strip()
                skill_parts = re.split(r'[,:;]', parts)
                for part in skill_parts:
                    part = part.strip()
                    if (part and len(part) >= self.CONFIG["min_skill_length"] and
                        not re.match(r'^\d+$', part) and
                        not any(kw in part.lower() for kw in ["experience", "education", "intern"])):
                        skills.add(part)
                        logger.debug(f"Extracted skill from colon: {part}")
            elif self.is_bullet_line(line) and not re.search(self.CONFIG["date_pattern"], line):
                skill_parts = re.split(r'[,:;]', clean_line)
                for part in skill_parts:
                    part = part.strip()
                    if (part and len(part) >= self.CONFIG["min_skill_length"] and
                        not re.match(r'^\d+$', part) and
                        not any(kw in part.lower() for kw in ["experience", "education", "intern"])):
                        skills.add(part)
                        logger.debug(f"Extracted skill from bullet: {part}")
        return sorted(list(skills))

    def parse_experience(self, lines: List[str]) -> List[Dict]:
        experiences = []
        current_exp = {}
        description_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]
            date_match = re.search(self.CONFIG["date_pattern"], line)
            if date_match:
                if current_exp.get("title") and description_lines:
                    current_exp["description"] = " ".join(description_lines[:self.CONFIG["max_description_lines"]])
                    experiences.append(current_exp)
                    logger.debug(f"Added experience: {current_exp['title']}")
                    current_exp = {}
                    description_lines = []
                current_exp["duration"] = date_match.group()
                i += 1
                if i < len(lines) and not self.is_bullet_line(lines[i]):
                    if not current_exp.get("title"):
                        current_exp["title"] = lines[i]
                    elif not current_exp.get("company"):
                        current_exp["company"] = lines[i]
                    i += 1
                continue

            if (not self.is_bullet_line(line) and not date_match and i + 1 < len(lines) and
                (re.search(self.CONFIG["date_pattern"], lines[i + 1]) or (current_exp.get("duration") and not current_exp.get("title")))):
                current_exp["title"] = line
                i += 1
                continue

            if ((self.is_bullet_line(line) or (description_lines and not re.match(r'[A-Z]', line))) and
                current_exp.get("title") and not re.search(self.CONFIG["date_pattern"], line)):
                description_lines.append(re.sub(r'^[•\-\*◦]\s*', '', line).strip())
                i += 1
                continue

            i += 1

        if current_exp.get("title") and description_lines:
            current_exp["description"] = " ".join(description_lines[:self.CONFIG["max_description_lines"]])
            experiences.append(current_exp)
            logger.debug(f"Added final experience: {current_exp['title']}")
        return experiences

    def parse_education(self, lines: List[str]) -> List[Dict]:
        education = []
        current_edu = {}
        i = 0

        while i < len(lines):
            line = lines[i]
            if any(kw in line.lower() for kw in ["bachelor", "master", "diploma", "b.tech", "mtech"]):
                if current_edu.get("degree") and any(current_edu.get(k) for k in ["start_year", "institution"]):
                    education.append(current_edu)
                    current_edu = {}
                current_edu["degree"] = line
                i += 1
                while i < len(lines) and not any(h.lower() in lines[i].lower() for h in self.CONFIG["section_headers"]):
                    year_match = re.search(r'\b\d{4}\b', lines[i])
                    if year_match:
                        current_edu["start_year"] = year_match.group()
                        institution = re.sub(r'\b\d{4}[-–]?\s*(?:\d{4}|Present)?', '', lines[i]).strip()
                        if institution and not current_edu.get("institution"):
                            current_edu["institution"] = institution
                    elif not current_edu.get("institution") and lines[i].strip() and not re.match(r'^\d+$', lines[i]) and not self.is_bullet_line(lines[i]):
                        current_edu["institution"] = lines[i].strip()
                    i += 1
                continue
            i += 1

        if current_edu.get("degree") and any(current_edu.get(k) for k in ["start_year", "institution"]):
            education.append(current_edu)
            logger.debug(f"Added education: {current_edu['degree']}")
        return education

    def parse_certifications(self, lines: List[str]) -> List[Dict]:
        certifications = []
        for line in lines:
            clean_line = re.sub(r'^[•\-\*◦]\s*', '', line).strip()
            if self.is_bullet_line(line) and len(clean_line) > 5 and not any(kw in clean_line.lower() for kw in ["email", "phone", "@"]):
                certifications.append({"title": clean_line})
                logger.debug(f"Extracted certification: {clean_line}")
        return certifications

    def calculate_skill_match(self, extracted_skills: List[str]) -> float:
        if not self.key_skills:
            logger.warning("No key skills provided for matching.")
            return 0.0
        matched = sum(1 for key_skill in self.key_skills if any(key_skill.lower() in skill.lower() for skill in extracted_skills))
        score = round((matched / len(self.key_skills)) * 100, 2)
        logger.debug(f"Skill match score: {score}% (Matched {matched}/{len(self.key_skills)})")
        return score

    def calculate_relevance_score(self, resume_text: str) -> float:
        try:
            vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
            documents = [resume_text, f"{self.job_description} {self.job_role}"]
            tfidf_matrix = vectorizer.fit_transform(documents)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            score = round(similarity * 100, 2)
            logger.debug(f"Relevance score: {score}%")
            return score
        except Exception as e:
            logger.error(f"Failed to calculate relevance score: {str(e)}")
            return 0.0

    def save_to_db(self, parsed_data: Dict):
        try:
            candidate = Candidate.objects.get(id=self.candidate_id)
            personal_info = parsed_data["personal_info"]
            candidate.first_name = personal_info["first_name"]
            candidate.last_name = personal_info["last_name"]
            candidate.location = personal_info["location"]
            candidate.phone = personal_info["phone"]
            candidate.save()

            for edu in parsed_data["education"]:
                Education.objects.create(
                    candidate=candidate,
                    degree=edu["degree"],
                    university=edu.get("institution"),
                    start_year=int(edu["start_year"]) if edu.get("start_year") else None
                )

            for exp in parsed_data["experience"]:
                duration = exp["duration"].split('–')
                start_date = date_parse(duration[0].strip()) if duration[0] else None
                end_date = date_parse(duration[1].strip()) if len(duration) > 1 and duration[1].strip() not in ["Present", "Current"] else None
                WorkExperience.objects.create(
                    candidate=candidate,
                    company_name=exp.get("company"),
                    job_title=exp["title"],
                    start_date=start_date,
                    end_date=end_date
                )

            for skill in parsed_data["skills"]:
                Skill.objects.create(candidate=candidate, skill_name=skill)

            for cert in parsed_data["certifications"]:
                Certification.objects.create(candidate=candidate, title=cert["title"])

            logger.info(f"Saved parsed data to DB for candidate {self.candidate_id}")
        except Candidate.DoesNotExist:
            logger.error(f"Candidate {self.candidate_id} not found during DB save")
            raise ResumeParserError(f"Candidate {self.candidate_id} does not exist")
        except Exception as e:
            logger.error(f"Failed to save parsed data to DB: {str(e)}")
            raise ResumeParserError(f"Database save failed: {str(e)}")

    def parse(self, pdf_content: bytes) -> Dict:
        start_time = datetime.now()
        try:
            logger.info(f"Starting resume parsing for candidate {self.candidate_id}")
            text = self.extract_text_from_pdf(pdf_content)
            doc = self.nlp(text)
            lines = text.split('\n')
            bounds = self.find_section_bounds(lines)

            skills_lines = self.get_section_lines(lines, bounds, ["skills", "technical skills", "core competencies"])
            exp_lines = self.get_section_lines(lines, bounds, ["experience", "professional experience"])
            edu_lines = self.get_section_lines(lines, bounds, ["education"])
            cert_lines = self.get_section_lines(lines, bounds, ["certifications"])

            parsed_data = {
                "candidate_id": self.candidate_id,
                "job_role": self.job_role,
                "personal_info": self.parse_personal_info(doc, text),
                "skills": self.parse_skills(skills_lines),
                "experience": self.parse_experience(exp_lines),
                "education": self.parse_education(edu_lines),
                "certifications": self.parse_certifications(cert_lines),
                "skill_match_score": 0.0,
                "relevance_score": 0.0,
                "metadata": {
                    "processing_time": None,
                    "resume_length": len(text),
                    "status": "success",
                    "sections_detected": list(bounds.keys())
                }
            }

            parsed_data["skill_match_score"] = self.calculate_skill_match(parsed_data["skills"])
            parsed_data["relevance_score"] = self.calculate_relevance_score(text)
            parsed_data["metadata"]["processing_time"] = (datetime.now() - start_time).total_seconds()

            self.save_to_db(parsed_data)

            logger.info(f"Successfully parsed resume for candidate {self.candidate_id}")
            return parsed_data

        except ResumeParserError as e:
            logger.error(f"Resume parsing failed for {self.candidate_id}: {str(e)}")
            return {
                "candidate_id": self.candidate_id,
                "error": str(e),
                "metadata": {"status": "error", "processing_time": (datetime.now() - start_time).total_seconds()}
            }
        except Exception as e:
            logger.error(f"Unexpected error for {self.candidate_id}: {str(e)}", exc_info=True)
            return {
                "candidate_id": self.candidate_id,
                "error": "Internal server error",
                "metadata": {"status": "error", "processing_time": (datetime.now() - start_time).total_seconds()}
            }