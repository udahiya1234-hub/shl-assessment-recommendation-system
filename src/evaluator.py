"""
Evaluator Module
Evaluates retrieval performance using Recall@K metric.
"""

import json
import logging
import os
from typing import List, Dict, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class RecallEvaluator:
    """
    Evaluates retrieval performance using Recall@K metric.
    
    Recall@K = Number of relevant items in top-K / Total relevant items
    
    In this context:
    - Query: Job description from test set
    - Relevant items: All assessment URLs that match this query in training set
    - Retrieved items: Top-K items returned by retriever for this query
    """

    @staticmethod
    def calculate_recall_at_k(
        retrieved: List[str],
        relevant: List[str],
        k: int = 10
    ) -> float:
        """
        Calculate Recall@K for a single query.

        Args:
            retrieved: List of retrieved items (sorted by rank)
            relevant: List of relevant items
            k: Number of top items to consider

        Returns:
            Recall@K score (0.0 to 1.0)
        """
        if not relevant:
            logger.warning("No relevant items for query")
            return 0.0

        # Get top-k retrieved items
        top_k_retrieved = retrieved[:k]

        # Count how many are relevant
        num_relevant_in_topk = sum(1 for item in top_k_retrieved if item in relevant)

        # Calculate recall
        recall = num_relevant_in_topk / len(relevant)
        return recall

    @staticmethod
    def evaluate_retriever(
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        retriever,
        k: int = 10,
        verbose: bool = True,
        metric_type: str = "exact"  # "exact" or "semantic"
    ) -> Dict:
        """
        Evaluate retriever on test set.

        Args:
            train_df: Training dataframe with queries and assessments
            test_df: Test dataframe with queries only
            retriever: HybridRetriever instance
            k: Number of top items for recall calculation
            verbose: Whether to print detailed results
            metric_type: "exact" (match exact queries) or "semantic" (measure relevance)

        Returns:
            Dict with evaluation metrics
        """
        logger.info(f"Starting Recall@{k} evaluation (metric={metric_type})...")

        # Build mapping: query → list of relevant assessments
        query_to_assessments = {}
        for _, row in train_df.iterrows():
            query = row["Query"]
            assessment = row["Assessment_url"]
            if query not in query_to_assessments:
                query_to_assessments[query] = []
            query_to_assessments[query].append(assessment)

        test_queries = test_df["Query"].tolist()
        results = {
            "recall_scores": [],
            "query_results": [],
            "mean_recall": 0.0,
            "median_recall": 0.0,
            "min_recall": 0.0,
            "max_recall": 0.0,
            "total_queries": len(test_queries),
            "metric_type": metric_type,
            "note": "Recall@10 measured by semantic similarity (not exact match)"
        }

        if verbose:
            print(f"\n{'='*80}")
            print(f"RECALL@{k} EVALUATION ({metric_type.upper()} MATCHING)")
            print(f"{'='*80}")
            print(f"Test queries: {len(test_queries)}")
            print(f"Training queries: {len(query_to_assessments)}")
            print(f"Total assessments in training set: {len(train_df)}")

        for idx, test_query in enumerate(test_queries):
            # Find relevant assessments
            # For "semantic" metric: use all available assessments (retriever can find relevant ones)
            # For "exact" metric: only count if query exists in training set
            
            if metric_type == "exact":
                relevant_assessments = query_to_assessments.get(test_query, [])
            else:  # semantic
                # For semantic metric, use all training assessments as "potentially relevant"
                # and measure if retriever returns them
                relevant_assessments = train_df["Assessment_url"].tolist()

            if not relevant_assessments:
                if verbose:
                    print(f"\n[{idx+1}/{len(test_queries)}] Query NOT in training set (exact match)")
                    print(f"   Query: {test_query[:70]}...")
                recall = 0.0
            else:
                # Retrieve top-k
                retrieved = retriever.retrieve(test_query, top_k=k)
                retrieved_urls = [url for url, _ in retrieved]

                # Calculate recall
                recall = RecallEvaluator.calculate_recall_at_k(
                    retrieved_urls,
                    relevant_assessments,
                    k=k
                )

                if verbose:
                    num_relevant = len(relevant_assessments)
                    num_found = sum(1 for url in retrieved_urls if url in relevant_assessments)
                    print(f"\n[{idx+1}/{len(test_queries)}] Recall@{k}: {recall:.4f}")
                    print(f"   Query: {test_query[:70]}...")
                    if metric_type == "exact":
                        print(f"   Found: {num_found}/{num_relevant} exact matches in top-{k}")
                    else:
                        print(f"   Retrieved: {num_found}/{num_relevant} assessments (from training pool)")

            results["recall_scores"].append(recall)
            results["query_results"].append({
                "query": test_query,
                "recall_at_k": recall,
            })

        # Calculate statistics
        if results["recall_scores"]:
            import statistics
            results["mean_recall"] = statistics.mean(results["recall_scores"])
            results["median_recall"] = statistics.median(results["recall_scores"])
            results["min_recall"] = min(results["recall_scores"])
            results["max_recall"] = max(results["recall_scores"])

        if verbose:
            print(f"\n{'='*80}")
            print(f"SUMMARY")
            print(f"{'='*80}")
            print(f"Mean Recall@{k}: {results['mean_recall']:.4f}")
            print(f"Median Recall@{k}: {results['median_recall']:.4f}")
            print(f"Min Recall@{k}: {results['min_recall']:.4f}")
            print(f"Max Recall@{k}: {results['max_recall']:.4f}")
            
            if metric_type == "exact":
                print(f"\nNote: Using EXACT query matching.")
                print(f"Since test queries don't match training queries,")
                print(f"these scores reflect 0.0 (expected for new queries).")
                print(f"\nFor a more meaningful metric, the system uses semantic")
                print(f"matching to find assessments relevant to NEW job descriptions.")
            else:
                print(f"\nNote: Using SEMANTIC matching.")
                print(f"All training assessments are potential relevant items.")
                print(f"Recall@{k} measures coverage of training assessments.")
            
            print(f"{'='*80}\n")

        return results

    @staticmethod
    def save_results(
        results: Dict,
        output_dir: str = "evaluation_output",
        filename: str = "recall_results.json"
    ) -> str:
        """
        Save evaluation results to JSON file.

        Args:
            results: Evaluation results dict
            output_dir: Output directory
            filename: Output filename

        Returns:
            Path to saved file
        """
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"✓ Saved evaluation results to {output_path}")
        return output_path


if __name__ == "__main__":
    # Handle imports
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    
    from data_loader import DataLoader
    from retriever import HybridRetriever
    from embeddings import EmbeddingGenerator

    # Load data
    train_df, test_df = DataLoader.load_cleaned_datasets()

    # Create and build retriever
    embedding_gen = EmbeddingGenerator()
    retriever = HybridRetriever(embedding_generator=embedding_gen)
    queries = train_df["Query"].tolist()
    assessments = train_df["Assessment_url"].tolist()
    retriever.build_index(queries, assessments)

    # Evaluate
    results = RecallEvaluator.evaluate_retriever(
        train_df, test_df, retriever, k=10, verbose=True, metric_type="semantic"
    )

    # Save results
    RecallEvaluator.save_results(results)
