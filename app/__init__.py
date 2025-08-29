
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from .config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from . import models  # noqa
        from .seed_excel import import_from_excel
        db.create_all()
        import_from_excel()  # auto import on first run

        from .auth import auth_bp
        from .routes import main_bp
        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
        return app
