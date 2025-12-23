"""
Hybrid Retriever Module
Combines semantic search (FAISS) with keyword boosting for high-recall recommendations.
"""

import numpy as np
import logging
import os
import re
from typing import List, Tuple, Dict, Optional
import sys

# FAISS compatibility: use faiss-cpu for Streamlit Cloud (Linux)
try:
    import faiss
except ImportError:
    # Provide helpful error message
    logging.error(
        "FAISS not installed. Install with: pip install faiss-cpu"
    )
    raise

# Handle imports for both direct and package execution
# Use absolute import strategy compatible with Streamlit Cloud
try:
    from embeddings import EmbeddingGenerator
except ImportError:
    try:
        from src.embeddings import EmbeddingGenerator
    except ImportError:
        raise ImportError(
            "Could not import EmbeddingGenerator. Ensure src/ is in sys.path"
        )

logger = logging.getLogger(__name__)


class KeywordExtractor:
    """
    Extract and score keywords from job descriptions.
    """

    # Common skill keywords
    SKILL_KEYWORDS = {
        # Programming languages
        "java", "python", "javascript", "typescript", "csharp", "c#", "cpp", "c++",
        "ruby", "go", "rust", "php", "swift", "kotlin", "scala", "r", "sql",
        "html", "css", "react", "angular", "vue", "nodejs", "node.js",
        # Data & ML
        "machine learning", "ml", "deep learning", "nlp", "data science",
        "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
        # Cloud & DevOps
        "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "jenkins",
        # Databases
        "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
        # Skills
        "leadership", "management", "communication", "analytical", "problem solving",
        "agile", "scrum", "git", "version control",
        # Domains
        "finance", "healthcare", "ecommerce", "saas", "api", "microservices",
    }

    # Seniority levels
    SENIORITY_KEYWORDS = {
        "entry": ["entry level", "junior", "graduate", "trainee", "intern"],
        "mid": ["mid-level", "senior", "experienced", "professional"],
        "manager": ["manager", "team lead", "lead", "director", "principal", "staff"],
        "c_level": ["cto", "cfo", "ceo", "executive", "vp"],
    }

    @staticmethod
    def extract_keywords(text: str) -> Dict[str, List[str]]:
        """
        Extract skills and seniority levels from text.

        Args:
            text: Job description or query

        Returns:
            Dict with 'skills' and 'seniority' lists
        """
        text_lower = text.lower()

        # Extract skills
        skills = []
        for skill in KeywordExtractor.SKILL_KEYWORDS:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                skills.append(skill)

        # Extract seniority
        seniority = []
        for level, keywords in KeywordExtractor.SENIORITY_KEYWORDS.items():
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    seniority.append(level)

        return {
            "skills": list(set(skills)),  # Remove duplicates
            "seniority": list(set(seniority)),
        }


class HybridRetriever:
    """
    Hybrid retriever combining:
    1. Semantic search via FAISS
    2. Keyword matching
    3. Final ranking with weighted scores
    """

    def __init__(
        self,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ):
        """
        Initialize hybrid retriever.

        Args:
            embedding_generator: EmbeddingGenerator instance
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword overlap (0-1)
        """
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

        self.index = None
        self.assessments = None
        self.assessment_embeddings = None

        logger.info(
            f"✓ HybridRetriever initialized (semantic={semantic_weight}, keyword={keyword_weight})"
        )

    def build_index(self, queries: List[str], assessments: List[str]) -> None:
        """
        Build FAISS index from assessment descriptions.
        Compatible with both Windows and Linux (Streamlit Cloud).

        Args:
            queries: List of training queries (for context, not used directly)
            assessments: List of assessment descriptions/URLs

        Returns:
            None
        """
        if not assessments:
            logger.error("No assessments provided for indexing")
            raise ValueError("Assessments list cannot be empty")

        logger.info(f"Building FAISS index for {len(assessments)} assessments")

        try:
            # Generate embeddings for assessments
            self.assessment_embeddings = self.embedding_generator.encode_batch(
                assessments,
                batch_size=32,
                show_progress_bar=True
            )

            # Create FAISS index - use IndexFlatL2 for exact search
            # This is the most compatible approach across platforms
            embedding_dim = self.assessment_embeddings.shape[1]
            self.index = faiss.IndexFlatL2(embedding_dim)
            self.index.add(self.assessment_embeddings.astype(np.float32))

            self.assessments = assessments

            logger.info(f"✓ FAISS index built with {len(assessments)} assessments")

        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}", exc_info=True)
            raise RuntimeError(f"FAISS index building failed: {str(e)}")

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        use_keyword_boost: bool = True
    ) -> List[Tuple[str, float]]:
        """
        Retrieve top-k most relevant assessments.

        Args:
            query: Job description / hiring query
            top_k: Number of results to return
            use_keyword_boost: Whether to apply keyword boosting

        Returns:
            List of (assessment, score) tuples, sorted by score (descending)
        """
        if self.index is None or self.assessments is None:
            logger.error("Index not built. Call build_index() first")
            raise RuntimeError("Index not initialized")

        # Encode query
        query_embedding = self.embedding_generator.encode(query)
        query_embedding = query_embedding.astype(np.float32)

        # Semantic search: get top-2*k for potential re-ranking
        rerank_k = min(2 * top_k, len(self.assessments))
        distances, indices = self.index.search(query_embedding, rerank_k)

        # Convert distances to similarity scores (L2 distance → similarity)
        # Smaller distance = higher similarity
        semantic_scores = 1.0 / (1.0 + distances[0])  # Normalize

        # Keyword boosting
        query_keywords = KeywordExtractor.extract_keywords(query)
        query_skills = set(query_keywords.get("skills", []))
        query_seniority = set(query_keywords.get("seniority", []))

        final_results = []

        for idx, (result_idx, semantic_score) in enumerate(zip(indices[0], semantic_scores)):
            assessment = self.assessments[int(result_idx)]

            # Extract keywords from assessment
            assessment_keywords = KeywordExtractor.extract_keywords(assessment)
            assessment_skills = set(assessment_keywords.get("skills", []))
            assessment_seniority = set(assessment_keywords.get("seniority", []))

            # Calculate keyword overlap
            skill_overlap = len(query_skills & assessment_skills) / max(
                len(query_skills), 1
            )
            seniority_overlap = len(query_seniority & assessment_seniority) / max(
                len(query_seniority), 1
            )

            keyword_score = (skill_overlap + seniority_overlap) / 2.0 if use_keyword_boost else 0.0

            # Final score: weighted combination
            final_score = (
                self.semantic_weight * float(semantic_score)
                + self.keyword_weight * keyword_score
            )

            final_results.append((assessment, final_score))

        # Sort by score (descending) and return top-k
        final_results.sort(key=lambda x: x[1], reverse=True)
        return final_results[:top_k]

    def save_index(self, output_dir: str = "models/faiss_index") -> None:
        """
        Save FAISS index to disk.

        Args:
            output_dir: Directory to save index
        """
        if self.index is None:
            logger.error("No index to save")
            return

        os.makedirs(output_dir, exist_ok=True)
        index_path = os.path.join(output_dir, "faiss_index.bin")
        assessments_path = os.path.join(output_dir, "assessments.npy")

        faiss.write_index(self.index, index_path)
        np.save(assessments_path, np.array(self.assessments, dtype=object), allow_pickle=True)

        logger.info(f"✓ Index saved to {index_path}")
        logger.info(f"✓ Assessments saved to {assessments_path}")

    def load_index(self, input_dir: str = "models/faiss_index") -> None:
        """
        Load FAISS index from disk.
        Cross-platform compatible (Windows and Linux/Streamlit Cloud).

        Args:
            input_dir: Directory containing saved index
        """
        try:
            index_path = os.path.join(input_dir, "faiss_index.bin")
            assessments_path = os.path.join(input_dir, "assessments.npy")

            if not os.path.exists(index_path):
                raise FileNotFoundError(
                    f"FAISS index not found at {index_path}. "
                    f"Run: python src/retriever.py to build index"
                )
            
            if not os.path.exists(assessments_path):
                raise FileNotFoundError(
                    f"Assessments file not found at {assessments_path}. "
                    f"Run: python src/retriever.py to build index"
                )

            # Load index safely
            self.index = faiss.read_index(index_path)
            self.assessments = list(np.load(assessments_path, allow_pickle=True))

            logger.info(f"✓ Index loaded from {index_path}")
            logger.info(f"✓ Assessments loaded: {len(self.assessments)} items")

        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}", exc_info=True)
            raise RuntimeError(f"Could not load FAISS index: {str(e)}")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    
    from data_loader import DataLoader

    # Load data - check multiple paths
    import os
    current_dir = os.getcwd()
    
    # Try to load from evaluation directory
    if os.path.exists(os.path.join(current_dir, "evaluation")):
        train_df, _ = DataLoader.load_cleaned_datasets(output_dir="evaluation")
    elif os.path.exists(os.path.join(current_dir, "..", "evaluation")):
        train_df, _ = DataLoader.load_cleaned_datasets(output_dir="../evaluation")
    else:
        raise FileNotFoundError("Could not find evaluation directory")

    # Create retriever
    embedding_gen = EmbeddingGenerator()
    retriever = HybridRetriever(embedding_generator=embedding_gen)

    # Build index
    queries = train_df["Query"].tolist()
    assessments = train_df["Assessment_url"].tolist()
    retriever.build_index(queries, assessments)

    # Test retrieval
    test_query = queries[0]
    print(f"\nTest Query: {test_query[:100]}...")
    print("\nTop-5 Retrieved Assessments:")
    results = retriever.retrieve(test_query, top_k=5)
    for i, (assessment, score) in enumerate(results, 1):
        print(f"{i}. Score: {score:.4f} | {assessment[:80]}...")

    # Save index
    retriever.save_index()
