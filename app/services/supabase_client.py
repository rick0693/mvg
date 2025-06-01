from supabase import create_client, Client
from flask import current_app, g

def get_supabase_client() -> Client:
    if 'supabase_client' not in g:
        if not current_app.config.get('SUPABASE_URL') or \
           current_app.config.get('SUPABASE_URL') == 'YOUR_SUPABASE_URL_HERE' or \
           not current_app.config.get('SUPABASE_KEY') or \
           current_app.config.get('SUPABASE_KEY') == 'YOUR_SUPABASE_ANON_KEY_HERE':
            raise ValueError("Supabase URL or Key is not configured properly or is using placeholder values. Please check your .env file or environment variables.")

        g.supabase_client = create_client(
            current_app.config['SUPABASE_URL'],
            current_app.config['SUPABASE_KEY']
        )
    return g.supabase_client

# You might also want a function to close the client if needed, though Supabase client typically manages its own connections.
# def close_supabase_client(e=None):
#     client = g.pop('supabase_client', None)
#     if client is not None:
#         # Supabase client doesn't have an explicit close method in the Python library
#         # Connections are managed by the underlying httpx client.
#         pass
