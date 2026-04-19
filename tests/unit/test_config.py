"""
Unit tests for configuration
"""
import pytest
import os
from pathlib import Path
from config import Settings, BASE_DIR, DATA_DIR, MODELS_DIR, LOGS_DIR


class TestSettingsInitialization:
    """Test Settings initialization"""
    
    def test_settings_default_values(self):
        """Test Settings with default values"""
        settings = Settings()
        assert settings.use_sqlite is True
        assert settings.database_url == "sqlite:///autodeal.db"
        assert settings.scraping_interval_hours == 6
        assert settings.max_listings_per_source == 100
        assert settings.dashboard_port == 8501
        assert settings.log_level == "INFO"
    
    def test_settings_from_environment(self):
        """Test Settings loaded from environment variables"""
        os.environ["DASHBOARD_PORT"] = "8502"
        os.environ["LOG_LEVEL"] = "DEBUG"
        settings = Settings()
        assert settings.dashboard_port == 8502
        assert settings.log_level == "DEBUG"
        # Clean up
        del os.environ["DASHBOARD_PORT"]
        del os.environ["LOG_LEVEL"]
    
    def test_settings_validation_port_range(self):
        """Test Settings port validation"""
        with pytest.raises(ValueError, match="port must be between 1 and 65535"):
            Settings(dashboard_port=70000)
    
    def test_settings_validation_positive_float(self):
        """Test Settings positive float validation"""
        with pytest.raises(ValueError, match="value must be positive"):
            Settings(min_profit_margin_eur=-100)
    
    def test_settings_validation_database_url(self):
        """Test Settings database_url validation"""
        with pytest.raises(ValueError, match="database_url cannot be empty"):
            Settings(database_url="")


class TestSettingsProperties:
    """Test Settings properties"""
    
    def test_model_path_property(self):
        """Test model_path property"""
        settings = Settings()
        assert settings.model_path == MODELS_DIR / "xgboost_model.json"
    
    def test_log_file_property(self):
        """Test log_file property"""
        settings = Settings()
        assert settings.log_file == LOGS_DIR / "autodeal.log"
    
    def test_export_dir_property(self):
        """Test export_dir property"""
        settings = Settings()
        assert settings.export_dir == DATA_DIR / "exports"
    
    def test_watchlist_file_property(self):
        """Test watchlist_file property"""
        settings = Settings()
        assert settings.watchlist_file == DATA_DIR / "watchlist.json"
    
    def test_user_agents_property(self):
        """Test user_agents property returns list"""
        settings = Settings()
        user_agents = settings.user_agents
        assert isinstance(user_agents, list)
        assert len(user_agents) > 0
        assert "Mozilla" in user_agents[0]
    
    def test_olx_base_url_property(self):
        """Test olx_base_url property"""
        settings = Settings()
        assert settings.olx_base_url == "https://www.olx.pt"
    
    def test_standvirtual_base_url_property(self):
        """Test standvirtual_base_url property"""
        settings = Settings()
        assert settings.standvirtual_base_url == "https://www.standvirtual.com"
    
    def test_autosapo_base_url_property(self):
        """Test autosapo_base_url property"""
        settings = Settings()
        assert settings.autosapo_base_url == "https://autos.sapo.pt"
    
    def test_vehicle_types_property(self):
        """Test vehicle_types property"""
        settings = Settings()
        vehicle_types = settings.vehicle_types
        assert isinstance(vehicle_types, list)
        assert "carros" in vehicle_types
        assert "motos" in vehicle_types
    
    def test_model_features_property(self):
        """Test model_features property"""
        settings = Settings()
        features = settings.model_features
        assert isinstance(features, list)
        assert "year" in features
        assert "km" in features
        assert "price" in features


class TestSettingsValidation:
    """Test Settings validation method"""
    
    def test_validate_returns_true(self):
        """Test validate method returns True for valid config"""
        settings = Settings()
        assert settings.validate_config() is True


class TestDirectoryCreation:
    """Test directory creation"""
    
    def test_base_dir_exists(self):
        """Test BASE_DIR exists"""
        assert BASE_DIR.exists()
        assert BASE_DIR.is_dir()
    
    def test_data_dir_exists(self):
        """Test DATA_DIR exists"""
        assert DATA_DIR.exists()
        assert DATA_DIR.is_dir()
    
    def test_models_dir_exists(self):
        """Test MODELS_DIR exists"""
        assert MODELS_DIR.exists()
        assert MODELS_DIR.is_dir()
    
    def test_logs_dir_exists(self):
        """Test LOGS_DIR exists"""
        assert LOGS_DIR.exists()
        assert LOGS_DIR.is_dir()


class TestEmailParsing:
    """Test email parsing validator"""
    
    def test_email_to_string(self):
        """Test email_to accepts string"""
        settings = Settings(email_to="user@example.com")
        assert settings.email_to == "user@example.com"
    
    def test_email_to_list(self):
        """Test email_to converts list to comma-separated string"""
        settings = Settings(email_to=["user1@example.com", "user2@example.com"])
        assert settings.email_to == "user1@example.com,user2@example.com"
