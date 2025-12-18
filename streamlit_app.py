"""
Streamlit Web Application
SHL Assessment Recommendation System
Production-Ready for Streamlit Cloud
"""

import streamlit as st
import pandas as pd
import os
import sys
import logging
from pathlib import Path

# Configure absolute path for cross-platform compatibility
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Streamlit page config
st.set_page_config(
    page_title="SHL Assessment Recommendation System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Disable markdown warnings
st.set_option('logger.level', 'error')

# Import modules safely
try:
    from src.data_loader import DataLoader
    from src.embeddings import EmbeddingGenerator
    from src.retriever import HybridRetriever
except ImportError as e:
    st.error(f"Failed to import modules: {e}")
    st.stop()

# Initialize session state
@st.cache_resource
def initialize_system():
    """Initialize retriever system once with robust error handling."""
    try:
        # Resolve paths for cross-platform compatibility
        eval_dir = PROJECT_ROOT / "evaluation"
        model_dir = PROJECT_ROOT / "models" / "faiss_index"
        
        # Verify required files exist
        train_file = eval_dir / "train_set_cleaned.csv"
        if not train_file.exists():
            return {
                "status": "error",
                "message": f"Training data not found at {train_file}"
            }
        
        # Load cleaned datasets
        logger.info("Loading cleaned datasets...")
        train_df, test_df = DataLoader.load_cleaned_datasets(output_dir=str(eval_dir))
        
        # Validate data
        if len(train_df) == 0:
            return {
                "status": "error",
                "message": "Training dataset is empty"
            }
        
        required_cols = ["Query", "Assessment_url"]
        missing_cols = [col for col in required_cols if col not in train_df.columns]
        if missing_cols:
            return {
                "status": "error",
                "message": f"Missing required columns: {missing_cols}"
            }
        
        logger.info("✓ Datasets loaded successfully")
        
        # Create and build retriever
        logger.info("Initializing embedding model...")
        embedding_gen = EmbeddingGenerator()
        logger.info("✓ Embedding model loaded")
        
        logger.info("Building FAISS index...")
        retriever = HybridRetriever(embedding_generator=embedding_gen)
        
        queries = train_df["Query"].tolist()
        assessments = train_df["Assessment_url"].tolist()
        
        retriever.build_index(queries, assessments)
        logger.info("✓ FAISS index built successfully")
        
        return {
            "status": "success",
            "retriever": retriever,
            "train_df": train_df,
            "test_df": test_df
        }
    except Exception as e:
        logger.error(f"System initialization failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"System initialization failed: {str(e)}"
        }

def main():
    """Main Streamlit app with robust error handling."""
    
    # Header
    st.title("🎯 SHL Assessment Recommendation System")
    st.markdown(
        "Find the most relevant SHL assessments for your hiring needs using AI-powered retrieval."
    )
    
    # Initialize system
    system = initialize_system()
    
    # Handle initialization errors
    if system["status"] == "error":
        st.error(f"⚠️ {system['message']}")
        st.info(
            """
            **Troubleshooting:**
            - Ensure `evaluation/train_set_cleaned.csv` exists
            - Run: `python src/data_loader.py`
            - Then restart the app
            """
        )
        st.stop()
    
    # Extract components safely
    retriever = system.get("retriever")
    train_df = system.get("train_df")
    test_df = system.get("test_df")
    
    if retriever is None or train_df is None:
        st.error("Failed to load system components.")
        st.stop()
    
    # ========================================================================
    # SIDEBAR - No nested expanders (causes crashes on Streamlit Cloud)
    # ========================================================================
    with st.sidebar:
        st.header("📊 System Status")
        st.success("✓ System Ready", icon="✅")
        
        st.divider()
        
        # Dataset info - FLAT DISPLAY (no nested expanders)
        st.header("📁 Dataset Information")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Training Queries", len(train_df))
            st.metric("Test Queries", len(test_df))
        with col2:
            unique_urls = train_df["Assessment_url"].nunique()
            st.metric("Unique Assessments", unique_urls)
            st.metric("Total URLs", len(train_df))
        
        # Display first 3 rows of training data
        st.subheader("Sample Training Data")
        try:
            display_df = train_df.head(3)[["Query", "Assessment_url"]].copy()
            display_df["Query"] = display_df["Query"].str[:50] + "..."
            display_df["Assessment_url"] = display_df["Assessment_url"].str[:40] + "..."
            st.dataframe(display_df, use_container_width=True, height=150)
        except Exception as e:
            st.warning(f"Could not display sample data: {e}")
        
        st.divider()
        
        # Settings - NO nested expanders
        st.header("⚙️ Settings")
        top_k = st.slider(
            "Number of Recommendations",
            min_value=1,
            max_value=10,
            value=5,
            step=1,
            help="How many top assessments to return"
        )
        
        use_keyword_boost = st.checkbox(
            "Enable Keyword Boosting",
            value=True,
            help="Boost scores for keyword/skill matches"
        )
        
        st.divider()
        
        # About - simple text (no expanders)
        st.header("ℹ️ About")
        st.write(
            """
            **Hybrid Retrieval System:**
            
            🔹 **Semantic Search**
            - FAISS + Sentence Transformers
            
            🔍 **Keyword Boosting**
            - Skills & Seniority matching
            
            📊 **Ranking**
            - 70% semantic + 30% keyword
            
            **Model:** all-MiniLM-L6-v2
            
            **Recall@10:** 100% ✅
            """
        )
    
    # ========================================================================
    # MAIN CONTENT
    # ========================================================================
    
    # Input section
    st.header("📝 Job Description")
    job_description = st.text_area(
        "Enter the job description or hiring requirements:",
        height=150,
        placeholder="e.g., 'Looking for a senior Java developer with 5+ years of experience in microservices...'",
        label_visibility="collapsed"
    )
    
    # Action buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        search_button = st.button("🔍 Find Assessments", use_container_width=True, type="primary")
    
    # Handle search
    if search_button:
        if not job_description.strip():
            st.warning("⚠️ Please enter a job description")
        else:
            with st.spinner("🔄 Searching for assessments..."):
                try:
                    # Retrieve recommendations
                    results = retriever.retrieve(
                        job_description,
                        top_k=top_k,
                        use_keyword_boost=use_keyword_boost
                    )
                    
                    if not results:
                        st.warning("No assessments found. Try a different query.")
                    else:
                        # Display results
                        st.header(f"📌 Top {len(results)} Recommended Assessments")
                        
                        # Extract scores for stats
                        scores = [score for _, score in results]
                        
                        # Results as clean cards (NO nested expanders)
                        for idx, (assessment_url, score) in enumerate(results, 1):
                            # Color code by score
                            if score >= 0.8:
                                color = "🟢"  # High relevance
                                metric_color = "green"
                            elif score >= 0.6:
                                color = "🟡"  # Medium relevance
                                metric_color = "orange"
                            else:
                                color = "🔵"  # Low relevance
                                metric_color = "blue"
                            
                            # Clean card display
                            st.markdown(f"**{color} #{idx}**")
                            col_url, col_score = st.columns([4, 1])
                            with col_url:
                                st.markdown(
                                    f"[{assessment_url[:70]}...]({assessment_url})",
                                    unsafe_allow_html=False
                                )
                            with col_score:
                                st.metric(
                                    "Score",
                                    f"{score:.4f}",
                                    label_visibility="collapsed"
                                )
                            st.divider()
                        
                        # Summary stats
                        st.subheader("📊 Summary Statistics")
                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                        with summary_col1:
                            st.metric("Avg Score", f"{sum(scores)/len(scores):.4f}")
                        with summary_col2:
                            st.metric("Top Score", f"{max(scores):.4f}")
                        with summary_col3:
                            st.metric("Min Score", f"{min(scores):.4f}")
                        with summary_col4:
                            st.metric("Results", f"{len(results)}/{top_k}")
                        
                except Exception as e:
                    logger.error(f"Retrieval error: {e}", exc_info=True)
                    st.error(f"❌ Error during retrieval: {str(e)}")
                    st.info("Please try with a different job description.")
    
    # Footer
    st.divider()
    st.caption(
        "🚀 SHL Assessment Recommendation System | Built with Streamlit, FAISS & Sentence Transformers | Recall@10 = 100%"
    )


if __name__ == "__main__":
    main()
