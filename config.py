import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '..', '.env') # Assuming .env is in the root directory
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-very-secret-key-for-flask-sessions'

    # Supabase Configuration
    SUPABASE_URL = os.environ.get('SUPABASE_URL') or 'YOUR_SUPABASE_URL_HERE'
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY') or 'YOUR_SUPABASE_ANON_KEY_HERE'

    # Google Maps API Key Configuration
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY') or 'YOUR_GOOGLE_MAPS_API_KEY_HERE'

    # SQLite Database Configuration
    # Assuming ctrc_database.db will be in the 'data' directory at the root of the project
    DATABASE_FILE = os.environ.get('DATABASE_FILE') or os.path.join(basedir, '..', 'data', 'ctrc_database.db')
    DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

    # Configuration for data_extraction.py specific settings
    # Path to the JSON file holding cookies and headers for ssw.inf.br
    SSW_CONFIG_PATH = os.environ.get('SSW_CONFIG_PATH') or os.path.join(basedir, '..', 'data', 'config.json')

    # Add other general configurations as needed
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    TESTING = os.environ.get('FLASK_TESTING', 'False').lower() in ('true', '1', 't')

# Example of different configs for different environments
# class DevelopmentConfig(Config):
#     DEBUG = True

# class ProductionConfig(Config):
#     DEBUG = False
#     # Ensure sensitive keys are ONLY from env vars in production
#     SUPABASE_URL = os.environ.get('SUPABASE_URL')
#     SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
#     GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
#     SECRET_KEY = os.environ.get('SECRET_KEY') # Should be a strong, unique key

# config_by_name = dict(
#     development=DevelopmentConfig,
#     production=ProductionConfig,
#     default=DevelopmentConfig
# )

# def get_config():
#     env = os.getenv('FLASK_ENV', 'default')
#     return config_by_name.get(env, DevelopmentConfig)
