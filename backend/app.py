"""
Hotel Lazzy-Kitchen — Flask backend entrypoint.
Creates the Flask app, wires up config, DB, CORS, blueprints and logging.
"""
import logging
from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from utils.db import db
from utils.helpers import error_response
from routes.auth import auth_bp
from routes.menu import menu_bp
from routes.orders import orders_bp
from routes.payments import payments_bp
from routes.staff import staff_bp

# --- Logging setup (never logs secrets/card data — see utils & services) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lazzy_kitchen")


def create_app(config_overrides=None):
    """config_overrides lets tests point at SQLite *before* the engine is built."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)

    for bp in (auth_bp, menu_bp, orders_bp, payments_bp, staff_bp):
        app.register_blueprint(bp, url_prefix="/api")

    @app.route("/api/health", methods=["GET"])
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            return jsonify({"status": "healthy"}), 200
        except Exception:
            logger.exception("Health check DB connection failed.")
            return jsonify({"status": "unhealthy"}), 503

    @app.after_request
    def no_store_api(resp):
        # API responses are per-customer; never let a browser/proxy cache them.
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    # --- Secure error handling: never leak stack traces to the client ---
    @app.errorhandler(404)
    def not_found(_e):
        return error_response("Resource not found.", 404)

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return error_response("Method not allowed.", 405)

    @app.errorhandler(500)
    def internal_error(_e):
        logger.exception("Unhandled server error.")
        return error_response("Something went wrong. Please try again.", 500)

    logger.info("Hotel Lazzy-Kitchen backend started.")
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
