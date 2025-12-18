"""
Streamlit Web Application
SHL Assessment Recommendation System
"""

import streamlit as st
import pandas as pd
import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data_loader import DataLoader
from src.embeddings import EmbeddingGenerator
from src.retriever import HybridRetriever
from src.evaluator import RecallEvaluator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="SHL Assessment Recommendation System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
@st.cache_resource
def initialize_system():
    """Initialize retriever system once."""
    try:
        # Load cleaned datasets
        train_df, test_df = DataLoader.load_cleaned_datasets(output_dir="evaluation")
        
        # Create and build retriever
        embedding_gen = EmbeddingGenerator()
        retriever = HybridRetriever(embedding_generator=embedding_gen)
        
        queries = train_df["Query"].tolist()
        assessments = train_df["Assessment_url"].tolist()
        
        retriever.build_index(queries, assessments)
        
        return {
            "retriever": retriever,
            "train_df": train_df,
            "test_df": test_df,
            "status": "✓ System initialized successfully"
        }
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        return {
            "retriever": None,
            "train_df": None,
            "test_df": None,
            "status": f"✗ Error: {str(e)}"
        }

def main():
    """Main Streamlit app."""
    
    # Header
    st.title("🎯 SHL Assessment Recommendation System")
    st.markdown(
        "Find the most relevant SHL assessments for your hiring needs using AI-powered retrieval."
    )
    
    # Sidebar
    with st.sidebar:
        st.header("📊 System Status")
        
        # Initialize system
        system = initialize_system()
        
        # Status indicator
        if system["retriever"] is not None:
            st.success("✓ System Ready")
        else:
            st.error("✗ System Error")
            st.write(system["status"])
            st.stop()
        
        st.divider()
        
        # Dataset info
        st.header("📁 Dataset Information")
        if system["train_df"] is not None:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Training Queries", len(system["train_df"]))
                st.metric("Test Queries", len(system["test_df"]))
            with col2:
                st.metric("Unique Assessments", system["train_df"]["Assessment_url"].nunique())
                st.metric("Total Assessment URLs", len(system["train_df"]))
        
        st.divider()
        
        # Settings
        st.header("⚙️ Settings")
        top_k = st.slider(
            "Number of Recommendations",
            min_value=1,
            max_value=10,
            value=5,
            step=1
        )
        
        use_keyword_boost = st.checkbox(
            "Enable Keyword Boosting",
            value=True,
            help="Boost scores for keyword/skill matches"
        )
        
        st.divider()
        
        # About
        st.header("ℹ️ About")
        st.write(
            """
            **Hybrid Retrieval System:**
            - 🔹 **Semantic Search**: FAISS + Sentence Transformers
            - 🔍 **Keyword Boosting**: Skills & Seniority matching
            - 📊 **Ranking**: Combined score (70% semantic + 30% keyword)
            
            **Model**: all-MiniLM-L6-v2
            """
        )
    
    # Main content
    if system["retriever"] is None:
        st.error("Failed to initialize retrieval system. Please check the logs.")
        return
    
    # Input section
    st.header("📝 Job Description")
    job_description = st.text_area(
        "Enter the job description or hiring requirements:",
        height=150,
        placeholder="e.g., 'Looking for a senior Java developer with 5+ years of experience in microservices...'",
        label_visibility="collapsed"
    )
    
    # Action button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        search_button = st.button("🔍 Find Assessments", use_container_width=True)
    with col2:
        st.button("ℹ️ Example Query", use_container_width=True)
    
    # Handle example query
    if st.session_state.get("load_example"):
        job_description = system["test_df"]["Query"].iloc[0]
        st.session_state["load_example"] = False
        st.rerun()
    
    # Results section
    if search_button and job_description.strip():
        with st.spinner("🔄 Searching for assessments..."):
            try:
                # Retrieve recommendations
                results = system["retriever"].retrieve(
                    job_description,
                    top_k=top_k,
                    use_keyword_boost=use_keyword_boost
                )
                
                # Display results
                st.header(f"📌 Top {len(results)} Recommended Assessments")
                
                for idx, (assessment_url, score) in enumerate(results, 1):
                    # Color code by score
                    if score >= 0.8:
                        color = "🟢"  # High relevance
                    elif score >= 0.6:
                        color = "🟡"  # Medium relevance
                    else:
                        color = "🔵"  # Low relevance
                    
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(
                                f"{color} **#{idx}** [{assessment_url[:70]}...]({assessment_url})",
                                unsafe_allow_html=True
                            )
                        with col2:
                            st.metric(
                                "Score",
                                f"{score:.4f}",
                                label_visibility="collapsed"
                            )
                
                # Summary stats
                st.divider()
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    scores = [s for _, s in results]
                    st.metric("Avg Score", f"{sum(scores)/len(scores):.4f}")
                with col2:
                    st.metric("Top Score", f"{max(scores):.4f}")
                with col3:
                    st.metric("Min Score", f"{min(scores):.4f}")
                with col4:
                    st.metric("Results", f"{len(results)}/{top_k}")
                
            except Exception as e:
                st.error(f"Error during retrieval: {str(e)}")
                logger.error(f"Retrieval error: {e}", exc_info=True)
    
    elif search_button:
        st.warning("⚠️ Please enter a job description")
    
    # Footer
    st.divider()
    st.caption(
        "🚀 SHL Assessment Recommendation System | Built with Streamlit & FAISS"
    )


if __name__ == "__main__":
    main()
