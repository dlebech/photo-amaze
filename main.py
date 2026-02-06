"""
    main
    ====

    Flask application entry point for Google App Engine.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import os

from dotenv import load_dotenv
load_dotenv()

import flickr_api
from flask import Flask, send_from_directory
from google.appengine.api import wrap_wsgi_app

from photoamaze import config
from photoamaze.routes import bp as main_bp, handle_http_exception
from photoamaze.mail import bp as mail_bp

# Setup Flickr API
flickr_api.set_keys(api_key=config.Flickr.api_key,
                    api_secret=config.Flickr.api_secret)
flickr_api.enable_cache()

# Create Flask app
app = Flask(__name__, template_folder='templates')
app.wsgi_app = wrap_wsgi_app(app.wsgi_app)
app.secret_key = os.environ.get('SESSION_KEY')
app.debug = config.DEBUG

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(mail_bp)

# Register error handlers
for code in (400, 401, 403, 404, 500):
    app.register_error_handler(code, handle_http_exception)

# Static file handlers to match app.yaml mappings for local development.
# On GAE, these are served by the infrastructure directly.
@app.route('/js/<path:filename>')
def static_js(filename):
    return send_from_directory('static/js/dist', filename)

@app.route('/css/<path:filename>')
def static_css(filename):
    return send_from_directory('static/css/dist', filename)

@app.route('/img/<path:filename>')
def static_img(filename):
    return send_from_directory('static/img', filename)

@app.route('/fonts/<path:filename>')
def static_fonts(filename):
    return send_from_directory('static/fonts', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
