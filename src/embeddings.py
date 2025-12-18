"""
Embeddings Module
Generates semantic embeddings using Sentence Transformers.
"""

import numpy as np
import logging
from typing import List, Union
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates semantic embeddings using pre-trained Sentence Transformers.
    Model: all-MiniLM-L6-v2 (lightweight, fast, effective for retrieval)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding generator.

        Args:
            model_name: Name of Sentence Transformers model to use
        """
        self.model_name = model_name
        try:
            logger.info(f"Loading embedding model: {model_name}")
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"✓ Model loaded. Embedding dimension: {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def encode(self, texts: Union[str, List[str]], show_progress_bar: bool = False) -> np.ndarray:
        """
        Encode text(s) to embeddings.

        Args:
            texts: Single text or list of texts
            show_progress_bar: Whether to show progress bar

        Returns:
            numpy array of embeddings (shape: [n, embedding_dim])
        """
        try:
            # Handle single string
            if isinstance(texts, str):
                texts = [texts]

            # Encode
            embeddings = self.model.encode(
                texts, 
                convert_to_numpy=True,
                show_progress_bar=show_progress_bar
            )

            return embeddings

        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise

    def encode_batch(
        self, 
        texts: List[str], 
        batch_size: int = 32,
        show_progress_bar: bool = True
    ) -> np.ndarray:
        """
        Encode texts in batches (more efficient for large datasets).

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding
            show_progress_bar: Whether to show progress bar

        Returns:
            numpy array of embeddings
        """
        try:
            logger.info(f"Encoding {len(texts)} texts in batches of {batch_size}")
            
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=show_progress_bar
            )

            logger.info(f"✓ Generated embeddings: shape {embeddings.shape}")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to encode batch: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        return self.embedding_dim


if __name__ == "__main__":
    # Test embedding generator
    generator = EmbeddingGenerator()
    
    test_texts = [
        "Java developer with SQL experience",
        "Senior Python engineer",
        "Leadership and management skills"
    ]
    
    embeddings = generator.encode(test_texts, show_progress_bar=True)
    print(f"Generated {len(embeddings)} embeddings of dimension {generator.get_embedding_dimension()}")
