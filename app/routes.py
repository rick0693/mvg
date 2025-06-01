from flask import Blueprint, render_template

# Create a Blueprint named 'main'
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return render_template('index.html')
