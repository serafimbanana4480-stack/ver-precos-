"""
Auto-setup script for Ollama
Automatically installs, configures, and starts Ollama service
"""
from __future__ import annotations
import subprocess
import platform
import time
import requests
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_ollama_installed() -> bool:
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"Ollama installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        logger.warning("Ollama not found in PATH")
    except Exception as e:
        logger.error(f"Error checking Ollama: {e}")
    return False


def install_ollama() -> bool:
    """Install Ollama based on platform"""
    system = platform.system()
    logger.info(f"Installing Ollama on {system}")
    
    try:
        if system == "Windows":
            # Use winget on Windows
            logger.info("Installing Ollama via winget...")
            result = subprocess.run(
                ["winget", "install", "Ollama.Ollama", "--silent"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info("Ollama installed successfully via winget")
                return True
            else:
                logger.error(f"Winget install failed: {result.stderr}")
                # Fallback: download installer
                logger.info("Attempting manual download...")
                return install_ollama_manual()
                
        elif system == "Darwin":  # macOS
            logger.info("Installing Ollama via brew...")
            result = subprocess.run(
                ["brew", "install", "ollama"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info("Ollama installed successfully via brew")
                return True
            else:
                logger.error(f"Brew install failed: {result.stderr}")
                return False
                
        elif system == "Linux":
            logger.info("Installing Ollama via curl...")
            result = subprocess.run(
                ["curl", "-fsSL", "https://ollama.com/install.sh", "|", "sh"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info("Ollama installed successfully")
                return True
            else:
                logger.error(f"Install failed: {result.stderr}")
                return False
        else:
            logger.error(f"Unsupported platform: {system}")
            return False
            
    except Exception as e:
        logger.error(f"Error installing Ollama: {e}")
        return False


def install_ollama_manual() -> bool:
    """Manual fallback installation for Windows"""
    try:
        import urllib.request
        
        # Download Ollama installer
        url = "https://ollama.com/download/OllamaSetup.exe"
        installer_path = Path.home() / "Downloads" / "OllamaSetup.exe"
        
        logger.info(f"Downloading Ollama installer to {installer_path}")
        urllib.request.urlretrieve(url, installer_path)
        
        # Run installer silently
        logger.info("Running Ollama installer...")
        result = subprocess.run(
            [str(installer_path), "/S"],
            capture_output=True,
            timeout=300
        )
        
        if result.returncode == 0:
            logger.info("Ollama installed successfully")
            # Clean up installer
            installer_path.unlink(missing_ok=True)
            return True
        else:
            logger.error(f"Installer failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Manual install failed: {e}")
        return False


def start_ollama_service() -> bool:
    """Start Ollama service in background"""
    try:
        logger.info("Starting Ollama service...")
        
        # Start ollama serve in background
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
        )
        
        # Wait for service to start
        logger.info("Waiting for Ollama service to start...")
        time.sleep(5)
        
        # Check if service is running
        if check_ollama_running():
            logger.info("Ollama service started successfully")
            return True
        else:
            logger.error("Ollama service failed to start")
            return False
            
    except Exception as e:
        logger.error(f"Error starting Ollama service: {e}")
        return False


def check_ollama_running() -> bool:
    """Check if Ollama service is running"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def pull_model(model_name: str = "qwen2.5:7b") -> bool:
    """Pull Ollama model"""
    try:
        logger.info(f"Pulling model {model_name}...")
        
        # Check if model already exists
        if check_model_exists(model_name):
            logger.info(f"Model {model_name} already exists")
            return True
        
        # Pull model
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout for large models
        )
        
        if result.returncode == 0:
            logger.info(f"Model {model_name} pulled successfully")
            return True
        else:
            logger.error(f"Failed to pull model: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error pulling model: {e}")
        return False


def check_model_exists(model_name: str) -> bool:
    """Check if model exists in Ollama"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            return any(model_name in name for name in model_names)
    except Exception:
        pass
    return False


def test_ollama_connection() -> bool:
    """Test Ollama connection with a simple request"""
    try:
        logger.info("Testing Ollama connection...")
        
        # Test with a simple generation request
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:7b",
                "prompt": "Say 'Ollama is working'",
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Ollama test successful: {result.get('response', '')[:100]}")
            return True
        else:
            logger.error(f"Ollama test failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error testing Ollama: {e}")
        return False


def main():
    """Main setup function"""
    logger.info("=" * 60)
    logger.info("Ollama Auto-Setup Script")
    logger.info("=" * 60)
    
    # Step 1: Check if Ollama is installed
    if not check_ollama_installed():
        logger.info("Ollama not installed, installing...")
        if not install_ollama():
            logger.error("Failed to install Ollama")
            return False
        logger.info("Ollama installed, please restart your terminal and run this script again")
        return True  # Return True to indicate installation was attempted
    
    # Step 2: Start Ollama service
    if not check_ollama_running():
        logger.info("Ollama service not running, starting...")
        if not start_ollama_service():
            logger.error("Failed to start Ollama service")
            return False
    
    # Step 3: Pull model
    logger.info("Pulling required model...")
    if not pull_model("qwen2.5:7b"):
        logger.error("Failed to pull model")
        return False
    
    # Step 4: Test connection
    if not test_ollama_connection():
        logger.error("Ollama connection test failed")
        return False
    
    logger.info("=" * 60)
    logger.info("✅ Ollama setup completed successfully!")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
