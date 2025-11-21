import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration centralizing environment variables"""
    # Core Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False

    # Vaulta API
    VAULTA_BASE_URL = os.getenv('VAULTA_BASE_URL', 'https://backend.vaulta.digital')

    # Gemini AI
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-001')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_active_config():
    """Return an instance of the active configuration based on APP_ENV env var."""
    env = os.getenv('APP_ENV', 'development').lower()
    cfg_class = config.get(env, config['default'])
    return cfg_class()
