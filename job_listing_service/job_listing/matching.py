from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .logger import logger

def calculate_match_score(job_skills: list, candidate_skills: list, job_description: str, candidate_profile: str) -> float:
    """Calculate a match score between a job and a candidate."""
    try:
        job_text = f"{' '.join(job_skills)} {job_description}"
        candidate_text = f"{' '.join(candidate_skills)} {candidate_profile}"
        
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        documents = [job_text, candidate_text]
        tfidf_matrix = vectorizer.fit_transform(documents)
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        
        score = round(similarity * 100, 2)
        logger.debug(f"Match score calculated: {score}%")
        return score
    except Exception as e:
        logger.warning(f"Failed to calculate match score: {str(e)}")
        return 0.0