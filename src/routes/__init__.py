# src/routes/__init__.py
from src.routes.routes_admin import admin_bp
from src.routes.routes_lehrkraft import lehrkraft_bp
from src.routes.routes_main import main_bp


def register_routes(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(lehrkraft_bp, url_prefix="/lehrkraft")
