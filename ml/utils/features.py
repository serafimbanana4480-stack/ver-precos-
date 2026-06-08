"""
Feature engineering utilities for ML models.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler, MinMaxScaler
from sklearn.feature_selection import SelectKBest, f_regression, RFE
from sklearn.decomposition import PCA
import re


class FeatureEngineer:
    """Feature engineering utilities for ML models."""
    
    def __init__(self):
        """Initialize feature engineer."""
        self.label_encoders = {}
        self.one_hot_encoders = {}
        self.scalers = {}
        self.feature_selectors = {}
        self.pca_transformers = {}
        self.feature_columns = []
        
    def extract_car_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract car-specific features from raw data."""
        df = df.copy()
        
        # Car age
        current_year = 2024
        df['car_age'] = current_year - df['year']
        
        # Mileage per year
        df['mileage_per_year'] = df['mileage'] / df['car_age'].replace(0, 1)
        
        # Engine size category
        df['engine_size_category'] = pd.cut(
            df['engine_size'], 
            bins=[0, 1.0, 1.6, 2.0, 3.0, float('inf')], 
            labels=['Small', 'Compact', 'Medium', 'Large', 'Extra Large']
        )
        
        # Mileage category
        df['mileage_category'] = pd.cut(
            df['mileage'],
            bins=[0, 20000, 50000, 100000, 150000, float('inf')],
            labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
        )
        
        # Age category
        df['age_category'] = pd.cut(
            df['car_age'],
            bins=[0, 2, 5, 10, 15, float('inf')],
            labels=['New', 'Nearly New', 'Used', 'Old', 'Very Old']
        )
        
        # Make popularity (based on common makes)
        popular_makes = ['Toyota', 'Volkswagen', 'Ford', 'Renault', 'Opel', 'Peugeot', 'Mercedes-Benz', 'BMW', 'Audi']
        df['is_popular_make'] = df['make'].isin(popular_makes).astype(int)
        
        # Fuel efficiency proxy (engine size vs fuel type)
        df['fuel_efficiency_proxy'] = np.where(
            df['fuel_type'] == 'Electric', 5.0,
            np.where(df['fuel_type'] == 'Hybrid', 4.0,
                    np.where(df['fuel_type'] == 'Diesel', 3.0,
                            np.where(df['engine_size'] < 1.5, 4.0,
                                    np.where(df['engine_size'] < 2.0, 3.0, 2.0))))
        )
        
        return df
    
    def encode_categorical_features(self, df: pd.DataFrame, columns: List[str] = None, method: str = 'one_hot') -> pd.DataFrame:
        """Encode categorical features."""
        df = df.copy()
        
        if columns is None:
            columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
                
            if method == 'label':
                if col not in self.label_encoders:
                    self.label_encoders[col] = LabelEncoder()
                    df[f'{col}_encoded'] = self.label_encoders[col].fit_transform(df[col].astype(str))
                else:
                    df[f'{col}_encoded'] = self.label_encoders[col].transform(df[col].astype(str))
                    
            elif method == 'one_hot':
                if col not in self.one_hot_encoders:
                    self.one_hot_encoders[col] = OneHotEncoder(sparse=False, drop='first')
                    encoded = self.one_hot_encoders[col].fit_transform(df[[col]])
                    feature_names = [f'{col}_{cat}' for cat in self.one_hot_encoders[col].categories_[0][1:]]
                    
                    for i, feature_name in enumerate(feature_names):
                        df[feature_name] = encoded[:, i]
                else:
                    encoded = self.one_hot_encoders[col].transform(df[[col]])
                    feature_names = [f'{col}_{cat}' for cat in self.one_hot_encoders[col].categories_[0][1:]]
                    
                    for i, feature_name in enumerate(feature_names):
                        df[feature_name] = encoded[:, i]
        
        return df
    
    def scale_numerical_features(self, df: pd.DataFrame, columns: List[str] = None, method: str = 'standard') -> pd.DataFrame:
        """Scale numerical features."""
        df = df.copy()
        
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
                
            if method == 'standard':
                if col not in self.scalers:
                    self.scalers[col] = StandardScaler()
                    df[f'{col}_scaled'] = self.scalers[col].fit_transform(df[[col]])
                else:
                    df[f'{col}_scaled'] = self.scalers[col].transform(df[[col]])
                    
            elif method == 'minmax':
                if col not in self.scalers:
                    self.scalers[col] = MinMaxScaler()
                    df[f'{col}_scaled'] = self.scalers[col].fit_transform(df[[col]])
                else:
                    df[f'{col}_scaled'] = self.scalers[col].transform(df[[col]])
        
        return df
    
    def create_interaction_features(self, df: pd.DataFrame, feature_pairs: List[tuple] = None) -> pd.DataFrame:
        """Create interaction features."""
        df = df.copy()
        
        if feature_pairs is None:
            # Create common interactions
            numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            feature_pairs = [
                ('year', 'mileage'),
                ('engine_size', 'mileage'),
                ('car_age', 'mileage_per_year'),
                ('engine_size', 'fuel_efficiency_proxy')
            ]
        
        for col1, col2 in feature_pairs:
            if col1 in df.columns and col2 in df.columns:
                # Multiplication interaction
                df[f'{col1}_x_{col2}'] = df[col1] * df[col2]
                
                # Division interaction (avoid division by zero)
                df[f'{col1}_div_{col2}'] = df[col1] / (df[col2] + 1e-8)
                
                # Difference interaction
                df[f'{col1}_minus_{col2}'] = df[col1] - df[col2]
        
        return df
    
    def select_features(self, X: pd.DataFrame, y: pd.Series, method: str = 'k_best', k: int = 10) -> pd.DataFrame:
        """Select best features using various methods."""
        if method == 'k_best':
            if 'k_best' not in self.feature_selectors:
                self.feature_selectors['k_best'] = SelectKBest(score_func=f_regression, k=k)
                X_selected = self.feature_selectors['k_best'].fit_transform(X, y)
            else:
                X_selected = self.feature_selectors['k_best'].transform(X)
            
            selected_features = X.columns[self.feature_selectors['k_best'].get_support()]
            return pd.DataFrame(X_selected, columns=selected_features)
        
        elif method == 'rfe':
            from sklearn.ensemble import RandomForestRegressor
            
            if 'rfe' not in self.feature_selectors:
                estimator = RandomForestRegressor(n_estimators=50, random_state=42)
                self.feature_selectors['rfe'] = RFE(estimator=estimator, n_features_to_select=k)
                X_selected = self.feature_selectors['rfe'].fit_transform(X, y)
            else:
                X_selected = self.feature_selectors['rfe'].transform(X)
            
            selected_features = X.columns[self.feature_selectors['rfe'].get_support()]
            return pd.DataFrame(X_selected, columns=selected_features)
        
        return X
    
    def apply_pca(self, X: pd.DataFrame, n_components: int = 5) -> pd.DataFrame:
        """Apply Principal Component Analysis."""
        if 'pca' not in self.pca_transformers:
            self.pca_transformers['pca'] = PCA(n_components=n_components)
            X_pca = self.pca_transformers['pca'].fit_transform(X)
        else:
            X_pca = self.pca_transformers['pca'].transform(X)
        
        pca_columns = [f'PC{i+1}' for i in range(n_components)]
        return pd.DataFrame(X_pca, columns=pca_columns)
    
    def extract_text_features(self, df: pd.DataFrame, text_column: str) -> pd.DataFrame:
        """Extract features from text columns."""
        df = df.copy()
        
        if text_column not in df.columns:
            return df
        
        # Text length
        df[f'{text_column}_length'] = df[text_column].astype(str).str.len()
        
        # Word count
        df[f'{text_column}_word_count'] = df[text_column].astype(str).str.split().str.len()
        
        # Number of digits (might indicate year, mileage, etc.)
        df[f'{text_column}_digit_count'] = df[text_column].astype(str).str.count(r'\d')
        
        # Uppercase ratio (might indicate emphasis)
        df[f'{text_column}_upper_ratio'] = df[text_column].astype(str).str.count(r'[A-Z]') / df[f'{text_column}_length']
        
        return df
    
    def create_polynomial_features(self, df: pd.DataFrame, columns: List[str], degree: int = 2) -> pd.DataFrame:
        """Create polynomial features."""
        from sklearn.preprocessing import PolynomialFeatures
        
        df = df.copy()
        
        if 'poly' not in self.feature_selectors:
            self.feature_selectors['poly'] = PolynomialFeatures(degree=degree, include_bias=False)
            poly_features = self.feature_selectors['poly'].fit_transform(df[columns])
        else:
            poly_features = self.feature_selectors['poly'].transform(df[columns])
        
        feature_names = self.feature_selectors['poly'].get_feature_names_out(columns)
        
        for i, feature_name in enumerate(feature_names):
            df[f'poly_{feature_name}'] = poly_features[:, i]
        
        return df
    
    def handle_missing_values(self, df: pd.DataFrame, strategy: str = 'mean') -> pd.DataFrame:
        """Handle missing values in the dataset."""
        df = df.copy()
        
        numerical_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        
        # Handle numerical missing values
        for col in numerical_cols:
            if df[col].isnull().sum() > 0:
                if strategy == 'mean':
                    df[col].fillna(df[col].mean(), inplace=True)
                elif strategy == 'median':
                    df[col].fillna(df[col].median(), inplace=True)
                elif strategy == 'mode':
                    df[col].fillna(df[col].mode()[0], inplace=True)
                elif strategy == 'zero':
                    df[col].fillna(0, inplace=True)
        
        # Handle categorical missing values
        for col in categorical_cols:
            if df[col].isnull().sum() > 0:
                df[col].fillna('Unknown', inplace=True)
        
        return df
    
    def detect_outliers(self, df: pd.DataFrame, columns: List[str], method: str = 'iqr') -> pd.DataFrame:
        """Detect and handle outliers."""
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
                
            if method == 'iqr':
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                # Mark outliers
                df[f'{col}_is_outlier'] = ((df[col] < lower_bound) | (df[col] > upper_bound)).astype(int)
                
                # Cap outliers
                df[col] = np.clip(df[col], lower_bound, upper_bound)
        
        return df
    
    def get_feature_importance_ranking(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """Get feature importance ranking."""
        from sklearn.ensemble import RandomForestRegressor
        
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X, y)
        
        importance_df = pd.DataFrame({
            'feature': X.columns,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return importance_df
    
    def get_feature_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get comprehensive feature statistics."""
        stats = {}
        
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                stats[col] = {
                    'type': 'numerical',
                    'count': df[col].count(),
                    'mean': df[col].mean(),
                    'std': df[col].std(),
                    'min': df[col].min(),
                    'max': df[col].max(),
                    'missing': df[col].isnull().sum(),
                    'missing_percentage': (df[col].isnull().sum() / len(df)) * 100
                }
            else:
                stats[col] = {
                    'type': 'categorical',
                    'count': df[col].count(),
                    'unique': df[col].nunique(),
                    'top': df[col].mode()[0] if not df[col].mode().empty else None,
                    'missing': df[col].isnull().sum(),
                    'missing_percentage': (df[col].isnull().sum() / len(df)) * 100
                }
        
        return stats
