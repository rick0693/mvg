import sqlite3
from flask import current_app, g
import os # Added to check for database file existence

def get_db_connection():
    if 'db_conn' not in g:
        db_path = current_app.config['DATABASE_FILE']
        # Check if the database directory exists, create if not
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Check if db_path exists, sqlite3.connect will create the file if it doesn't.
        # However, you might want to log this or handle initial schema creation elsewhere.
        # if not os.path.exists(db_path):
        #     current_app.logger.info(f"Database file not found at {db_path}. It will be created on connection.")

        g.db_conn = sqlite3.connect(db_path)
        g.db_conn.row_factory = sqlite3.Row # Optional: access columns by name
    return g.db_conn

def close_db_connection(e=None):
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        db_conn.close()

def init_app_db_handlers(app):
    # Register a function to close the database connection when the app context is torn down
    app.teardown_appcontext(close_db_connection)
    # You could also register the Supabase client closer here if it had one
    # app.teardown_appcontext(close_supabase_client)
