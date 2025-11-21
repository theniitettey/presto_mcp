from flask import Blueprint
from .chat_routes import chat_bp
from .web_routes import web_bp

def register_routes(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(web_bp)
    app.register_blueprint(chat_bp)
