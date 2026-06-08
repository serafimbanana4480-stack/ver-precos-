"""
Data preprocessing utilities for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, LabelEncoder, OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer, KNNImputer
import warnings
warnings.filterwarnings('ignore')


class DataPreprocessor:
    """Data preprocessing utilities for ML models."""
    
    def __init__(self):
        """Initialize data preprocessor."""
        self.scalers = {}
        self.encoders = {}
        self.imputers = {}
        self.feature_columns = []
        self.target_column = None
        self.preprocessing_steps = []
        
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean raw data."""
        df = df.copy()
        
        # Remove duplicates
        initial_rows = len(df)
        df = df.drop_duplicates()
        duplicates_removed = initial_rows - len(df)
        
        # Remove rows with all NaN values
        df = df.dropna(how='all')
        
        # Standardize text columns
        text_columns = df.select_dtypes(include=['object']).columns
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].str.title()
        
        # Clean numeric columns
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if col in df.columns:
                # Remove non-numeric characters from numeric columns
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce')
        
        print(f"Data cleaning completed. Removed {duplicates_removed} duplicate rows.")
        
        return df
    
    def handle_missing_values(self, df: pd.DataFrame, strategy: str = 'auto') -> pd.DataFrame:
        """Handle missing values in the dataset."""
        df = df.copy()
        
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns
        
        # Handle numeric missing values
        for col in numeric_columns:
            if df[col].isnull().sum() > 0:
                if strategy == 'auto':
                    # Use median for skewed data, mean for normal distribution
                    skewness = df[col].skew()
                    if abs(skewness) > 1:
                        fill_value = df[col].median()
                    else:
                        fill_value = df[col].mean()
                elif strategy == 'mean':
                    fill_value = df[col].mean()
                elif strategy == 'median':
                    fill_value = df[col].median()
                elif strategy == 'mode':
                    fill_value = df[col].mode()[0] if not df[col].mode().empty else 0
                else:
                    fill_value = 0
                
                df[col].fillna(fill_value, inplace=True)
        
        # Handle categorical missing values
        for col in categorical_columns:
            if df[col].isnull().sum() > 0:
                if strategy == 'knn':
                    # Use KNN imputer for categorical
                    if 'knn_categorical' not in self.imputers:
                        self.imputers['knn_categorical'] = SimpleImputer(strategy='most_frequent')
                    
                    df[col] = self.imputers['knn_categorical'].fit_transform(df[[col]]).ravel()
                else:
                    df[col].fillna('Unknown', inplace=True)
        
        return df
    
    def remove_outliers(self, df: pd.DataFrame, method: str = 'iqr', columns: List[str] = None) -> pd.DataFrame:
        """Remove outliers from the dataset."""
        df = df.copy()
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        initial_rows = len(df)
        
        for col in columns:
            if col not in df.columns:
                continue
                
            if method == 'iqr':
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]
                
            elif method == 'zscore':
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                df = df[z_scores < 3]
                
            elif method == 'modified_zscore':
                median = df[col].median()
                mad = np.median(np.abs(df[col] - median))
                modified_z_scores = 0.6745 * (df[col] - median) / mad
                df = df[np.abs(modified_z_scores) < 3.5]
        
        final_rows = len(df)
        outliers_removed = initial_rows - final_rows
        
        print(f"Outlier removal completed. Removed {outliers_removed} outlier rows.")
        
        return df
    
    def encode_categorical_features(self, df: pd.DataFrame, encoding_method: str = 'auto') -> pd.DataFrame:
        """Encode categorical features."""
        df = df.copy()
        
        categorical_columns = df.select_dtypes(include=['object', 'category']).columns
        
        for col in categorical_columns:
            if col in df.columns:
                unique_values = df[col].nunique()
                
                if encoding_method == 'auto':
                    # Use label encoding for high cardinality, one-hot for low cardinality
                    if unique_values > 10:
                        method = 'label'
                    else:
                        method = 'onehot'
                else:
                    method = encoding_method
                
                if method == 'label':
                    if col not in self.encoders:
                        self.encoders[col] = LabelEncoder()
                        df[f'{col}_encoded'] = self.encoders[col].fit_transform(df[col])
                    else:
                        df[f'{col}_encoded'] = self.encoders[col].transform(df[col])
                        
                elif method == 'onehot':
                    if col not in self.encoders:
                        self.encoders[col] = OneHotEncoder(sparse=False, drop='first')
                        encoded = self.encoders[col].fit_transform(df[[col]])
                        
                        # Create column names
                        feature_names = [f'{col}_{cat}' for cat in self.encoders[col].categories_[0][1:]]
                        
                        # Add to dataframe
                        for i, feature_name in enumerate(feature_names):
                            df[feature_name] = encoded[:, i]
                    else:
                        encoded = self.encoders[col].transform(df[[col]])
                        feature_names = [f'{col}_{cat}' for cat in self.encoders[col].categories_[0][1:]]
                        
                        for i, feature_name in enumerate(feature_names):
                            df[feature_name] = encoded[:, i]
        
        return df
    
    def scale_features(self, df: pd.DataFrame, scaling_method: str = 'standard', columns: List[str] = None) -> pd.DataFrame:
        """Scale numerical features."""
        df = df.copy()
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
                
            if scaling_method == 'standard':
                if col not in self.scalers:
                    self.scalers[col] = StandardScaler()
                    df[f'{col}_scaled'] = self.scalers[col].fit_transform(df[[col]])
                else:
                    df[f'{col}_scaled'] = self.scalers[col].transform(df[[col]])
                    
            elif scaling_method == 'minmax':
                if col not in self.scalers:
                    self.scalers[col] = MinMaxScaler()
                    df[f'{col}_scaled'] = self.scalers[col].fit_transform(df[[col]])
                else:
                    df[f'{col}_scaled'] = self.scalers[col].transform(df[[col]])
                    
            elif scaling_method == 'robust':
                if col not in self.scalers:
                    self.scalers[col] = RobustScaler()
                    df[f'{col}_scaled'] = self.scalers[col].fit_transform(df[[col]])
                else:
                    df[f'{col}_scaled'] = self.scalers[col].transform(df[[col]])
        
        return df
    
    def split_data(self, 
                   df: pd.DataFrame, 
                   target_column: str, 
                   test_size: float = 0.2, 
                   validation_size: float = 0.2,
                   random_state: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """Split data into train, validation, and test sets."""
        
        self.target_column = target_column
        
        # Separate features and target
        X = df.drop(columns=[target_column])
        y = df[target_column]
        
        # First split: train+val vs test
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        
        # Second split: train vs val
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=validation_size, random_state=random_state
        )
        
        print(f"Data split completed:")
        print(f"  Train: {len(X_train)} samples")
        print(f"  Validation: {len(X_val)} samples")
        print(f"  Test: {len(X_test)} samples")
        
        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def create_feature_engineering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create engineered features."""
        df = df.copy()
        
        # Age-related features
        if 'year' in df.columns:
            current_year = 2024
            df['car_age'] = current_year - df['year']
            df['is_new'] = (df['car_age'] <= 2).astype(int)
            df['is_old'] = (df['car_age'] >= 10).astype(int)
        
        # Mileage-related features
        if 'mileage' in df.columns and 'car_age' in df.columns:
            df['mileage_per_year'] = df['mileage'] / (df['car_age'] + 1)
            df['is_low_mileage'] = (df['mileage'] < 50000).astype(int)
            df['is_high_mileage'] = (df['mileage'] > 150000).astype(int)
        
        # Engine-related features
        if 'engine_size' in df.columns:
            df['engine_category'] = pd.cut(
                df['engine_size'],
                bins=[0, 1.0, 1.6, 2.0, 3.0, float('inf')],
                labels=['Small', 'Compact', 'Medium', 'Large', 'Extra Large']
            )
            
            df['is_large_engine'] = (df['engine_size'] > 2.5).astype(int)
            df['is_small_engine'] = (df['engine_size'] < 1.5).astype(int)
        
        # Price-related features (if available)
        if 'price' in df.columns:
            df['price_per_year'] = df['price'] / (df['car_age'] + 1)
            df['price_per_mile'] = df['price'] / (df['mileage'] + 1)
        
        # Interaction features
        if 'year' in df.columns and 'mileage' in df.columns:
            df['year_mileage_interaction'] = df['year'] * df['mileage']
        
        if 'engine_size' in df.columns and 'mileage' in df.columns:
            df['engine_mileage_ratio'] = df['engine_size'] / (df['mileage'] + 1)
        
        return df
    
    def validate_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate data quality and return report."""
        report = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'missing_values': {},
            'data_types': {},
            'duplicates': df.duplicated().sum(),
            'numeric_stats': {},
            'categorical_stats': {}
        }
        
        # Missing values
        for col in df.columns:
            missing_count = df[col].isnull().sum()
            if missing_count > 0:
                report['missing_values'][col] = {
                    'count': missing_count,
                    'percentage': (missing_count / len(df)) * 100
                }
        
        # Data types
        for col in df.columns:
            report['data_types'][col] = str(df[col].dtype)
        
        # Numeric statistics
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            report['numeric_stats'][col] = {
                'mean': df[col].mean(),
                'std': df[col].std(),
                'min': df[col].min(),
                'max': df[col].max(),
                'skewness': df[col].skew(),
                'kurtosis': df[col].kurtosis()
            }
        
        # Categorical statistics
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            report['categorical_stats'][col] = {
                'unique_values': df[col].nunique(),
                'most_frequent': df[col].mode()[0] if not df[col].mode().empty else None,
                'frequency': df[col].value_counts().to_dict()
            }
        
        return report
    
    def preprocess_pipeline(self, 
                           df: pd.DataFrame,
                           target_column: str,
                           clean_data: bool = True,
                           handle_missing: bool = True,
                           remove_outliers: bool = True,
                           encode_categorical: bool = True,
                           scale_features: bool = True,
                           create_features: bool = True) -> Tuple[pd.DataFrame, pd.Series]:
        """Complete preprocessing pipeline."""
        
        print("Starting data preprocessing pipeline...")
        
        # Step 1: Clean data
        if clean_data:
            print("Step 1: Cleaning data...")
            df = self.clean_data(df)
        
        # Step 2: Handle missing values
        if handle_missing:
            print("Step 2: Handling missing values...")
            df = self.handle_missing_values(df)
        
        # Step 3: Remove outliers
        if remove_outliers:
            print("Step 3: Removing outliers...")
            df = self.remove_outliers(df)
        
        # Step 4: Create engineered features
        if create_features:
            print("Step 4: Creating engineered features...")
            df = self.create_feature_engineering(df)
        
        # Step 5: Encode categorical features
        if encode_categorical:
            print("Step 5: Encoding categorical features...")
            df = self.encode_categorical_features(df)
        
        # Step 6: Scale features
        if scale_features:
            print("Step 6: Scaling features...")
            df = self.scale_features(df)
        
        # Step 7: Separate features and target
        if target_column in df.columns:
            X = df.drop(columns=[target_column])
            y = df[target_column]
        else:
            raise ValueError(f"Target column '{target_column}' not found in dataset")
        
        print("Data preprocessing pipeline completed!")
        print(f"Final dataset shape: {X.shape}")
        
        return X, y
    
    def get_preprocessing_summary(self) -> Dict[str, Any]:
        """Get summary of preprocessing steps applied."""
        return {
            'scalers_applied': list(self.scalers.keys()),
            'encoders_applied': list(self.encoders.keys()),
            'imputers_applied': list(self.imputers.keys()),
            'feature_columns': self.feature_columns,
            'target_column': self.target_column,
            'preprocessing_steps': self.preprocessing_steps
        }
    
    def transform_new_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform new data using fitted preprocessors."""
        df = df.copy()
        
        # Apply same transformations as training data
        for col, encoder in self.encoders.items():
            if col in df.columns:
                if isinstance(encoder, LabelEncoder):
                    df[f'{col}_encoded'] = encoder.transform(df[col])
                elif isinstance(encoder, OneHotEncoder):
                    encoded = encoder.transform(df[[col]])
                    feature_names = [f'{col}_{cat}' for cat in encoder.categories_[0][1:]]
                    for i, feature_name in enumerate(feature_names):
                        df[feature_name] = encoded[:, i]
        
        for col, scaler in self.scalers.items():
            if f'{col}_scaled' in df.columns:
                df[f'{col}_scaled'] = scaler.transform(df[[col]])
        
        return df
