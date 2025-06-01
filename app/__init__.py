from flask import Flask
from config import Config
from app.services.database import init_app_db_handlers

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)

    # Initialize app handlers for database connections
    init_app_db_handlers(app)

    # Register Blueprints
    from flask import Blueprint
    main_bp = Blueprint('main', __name__)

    @main_bp.route('/')
    def index():
        # Test config loading (optional)
        # google_api_key = app.config.get('GOOGLE_MAPS_API_KEY')
        # return f"Hello, Flask World! Google API Key configured: {google_api_key != 'YOUR_GOOGLE_MAPS_API_KEY_HERE' and bool(google_api_key)}"

        # Test database connection (optional)
        # from app.services.database import get_db_connection
        # try:
        #     conn = get_db_connection()
        #     # You could perform a simple query here if a table is known to exist
        #     return "Hello, Flask World! Core backend setup in progress. DB connection successful."
        # except Exception as e:
        #     current_app.logger.error(f"DB connection failed: {e}")
        #     return "Hello, Flask World! Core backend setup in progress. DB connection FAILED."
        return "Hello, Flask World! Core backend setup in progress."


    app.register_blueprint(main_bp)

    # Placeholder for painel blueprint
    # from .painel.routes import painel_bp # Example, assuming routes are in module subfolders
    # app.register_blueprint(painel_bp, url_prefix='/painel')

    return app
