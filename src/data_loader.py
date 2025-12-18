"""
Data Loader Module
Handles safe loading, validation, and cleaning of SHL training and test datasets.
"""

import pandas as pd
import os
from pathlib import Path
from typing import Tuple, Optional, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoader:
    """
    Robust data loader for SHL Assessment datasets.
    Handles:
    - Multiple file formats (CSV with tabs/commas, Excel)
    - Missing/malformed headers
    - Whitespace stripping
    - Validation of required columns
    - Dropping invalid rows
    """

    REQUIRED_TRAIN_COLUMNS = ["Query", "Assessment_url"]
    REQUIRED_TEST_COLUMNS = ["Query"]

    @staticmethod
    def load_excel_dataset(
        excel_path: str, train_sheet: str = "Train-Set", test_sheet: str = "Test-Set"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load train and test datasets from Excel file.

        Args:
            excel_path: Path to Excel file
            train_sheet: Name of training sheet
            test_sheet: Name of test sheet

        Returns:
            Tuple of (train_df, test_df)
        """
        try:
            logger.info(f"Loading Excel file: {excel_path}")

            # Load sheets
            train_df = pd.read_excel(excel_path, sheet_name=train_sheet)
            test_df = pd.read_excel(excel_path, sheet_name=test_sheet)

            logger.info(f"✓ Loaded Train-Set: {train_df.shape}")
            logger.info(f"✓ Loaded Test-Set: {test_df.shape}")

            return train_df, test_df

        except Exception as e:
            logger.error(f"Failed to load Excel file: {e}")
            raise

    @staticmethod
    def clean_dataframe(df: pd.DataFrame, required_columns: list) -> pd.DataFrame:
        """
        Clean dataframe by:
        - Stripping whitespace from column names
        - Removing duplicates
        - Dropping rows with missing required values
        - Stripping whitespace from text values

        Args:
            df: Input dataframe
            required_columns: List of required column names

        Returns:
            Cleaned dataframe
        """
        # Strip whitespace from column names - CRITICAL for Streamlit Cloud
        df.columns = df.columns.str.strip()

        logger.info(f"Columns after stripping: {list(df.columns)}")

        # Check if required columns exist (case-insensitive)
        df_cols_lower = {col.lower(): col for col in df.columns}
        
        for req_col in required_columns:
            if req_col not in df.columns:
                # Try case-insensitive match
                if req_col.lower() in df_cols_lower:
                    actual_col = df_cols_lower[req_col.lower()]
                    df.rename(columns={actual_col: req_col}, inplace=True)
                    logger.info(f"Renamed '{actual_col}' → '{req_col}'")

        # Final validation
        final_missing = [col for col in required_columns if col not in df.columns]
        if final_missing:
            raise ValueError(
                f"Required columns {final_missing} not found. Available: {list(df.columns)}"
            )

        # Strip whitespace from all text columns - CRITICAL for Streamlit Cloud
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].astype(str).str.strip()

        # Remove rows where required columns are empty or 'nan'
        for col in required_columns:
            df = df[df[col].notna() & (df[col] != "") & (df[col] != "nan")]

        # Remove duplicates (especially important for test set)
        initial_rows = len(df)
        df = df.drop_duplicates(subset=required_columns[:1], keep="first")
        if len(df) < initial_rows:
            logger.info(f"Removed {initial_rows - len(df)} duplicate rows")

        # Reset index
        df.reset_index(drop=True, inplace=True)

        logger.info(f"✓ Cleaned dataframe: {len(df)} valid rows")

        return df

    @staticmethod
    def load_and_clean_excel(
        excel_path: str,
        train_sheet: str = "Train-Set",
        test_sheet: str = "Test-Set",
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load Excel file and clean both datasets.

        Args:
            excel_path: Path to Excel file
            train_sheet: Name of training sheet
            test_sheet: Name of test sheet

        Returns:
            Tuple of (cleaned_train_df, cleaned_test_df)
        """
        # Load raw data
        train_df, test_df = DataLoader.load_excel_dataset(
            excel_path, train_sheet, test_sheet
        )

        # Clean datasets
        train_df = DataLoader.clean_dataframe(train_df, DataLoader.REQUIRED_TRAIN_COLUMNS)
        test_df = DataLoader.clean_dataframe(test_df, DataLoader.REQUIRED_TEST_COLUMNS)

        return train_df, test_df

    @staticmethod
    def save_cleaned_datasets(
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        output_dir: str = "evaluation",
    ) -> Tuple[str, str]:
        """
        Save cleaned datasets to CSV files.

        Args:
            train_df: Cleaned training dataframe
            test_df: Cleaned test dataframe
            output_dir: Directory to save files

        Returns:
            Tuple of (train_path, test_path)
        """
        os.makedirs(output_dir, exist_ok=True)

        train_path = os.path.join(output_dir, "train_set_cleaned.csv")
        test_path = os.path.join(output_dir, "test_set_cleaned.csv")

        train_df.to_csv(train_path, index=False)
        test_df.to_csv(test_path, index=False)

        logger.info(f"✓ Saved train_set_cleaned.csv: {len(train_df)} rows")
        logger.info(f"✓ Saved test_set_cleaned.csv: {len(test_df)} rows")

        return train_path, test_path

    @staticmethod
    def load_cleaned_datasets(output_dir: str = "evaluation") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load previously cleaned datasets from CSV files.

        Args:
            output_dir: Directory containing cleaned files

        Returns:
            Tuple of (train_df, test_df)
        """
        train_path = os.path.join(output_dir, "train_set_cleaned.csv")
        test_path = os.path.join(output_dir, "test_set_cleaned.csv")

        if not os.path.exists(train_path) or not os.path.exists(test_path):
            raise FileNotFoundError(f"Cleaned datasets not found in {output_dir}")

        train_df = pd.read_csv(train_path)
        test_df = pd.read_csv(test_path)

        logger.info(f"✓ Loaded train_set_cleaned.csv: {len(train_df)} rows")
        logger.info(f"✓ Loaded test_set_cleaned.csv: {len(test_df)} rows")

        return train_df, test_df


if __name__ == "__main__":
    # Example usage
    excel_path = "Gen_AI Dataset.xlsx"
    train_df, test_df = DataLoader.load_and_clean_excel(excel_path)
    DataLoader.save_cleaned_datasets(train_df, test_df)
