"""
    config
    ======

    Configuration.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import os
import jinja2
import webapp2

from util import ReadOnly


DEBUG = os.environ.get('SERVER_SOFTWARE', 'Google').startswith('Dev')
PEPPER = os.environ.get('AUTH_PEPPER')
EMAIL = os.environ.get('NO_REPLY_EMAIL')
MEMCACHE_TIME = 600 if not DEBUG else 1

# Has to be a dict.
WEBAPP_CONFIG = {
    'webapp2_extras.sessions': {
        'secret_key': os.environ.get('SESSION_KEY'),
        'cookie_name': os.environ.get('SESSION_COOKIE')
    }
}


class Instagram(ReadOnly):
    client_id = os.environ.get('INSTAGRAM_CLIENT_ID')
    client_secret = os.environ.get('INSTAGRAM_CLIENT_SECRET')
    memcache_time = 86400 if not DEBUG else 1


class Flickr(ReadOnly):
    api_key = os.environ.get('FLICKR_API_KEY')
    api_secret = os.environ.get('FLICKR_API_SECRET')
    memcache_time = 86400 if not DEBUG else 1


class Facebook(ReadOnly):
    app_id = os.environ.get('FACEBOOK_APP_ID')
    app_secret = os.environ.get('FACEBOOK_APP_SECRET')
    share_button = os.environ.get('FACEBOOK_SHARE_BUTTON') == 'yes'


class GooglePlus(ReadOnly):
    share_button = os.environ.get('GOOGLE_PLUS_SHARE_BUTTON') == 'yes'


class Twitter(ReadOnly):
    share_button = os.environ.get('TWITTER_SHARE_BUTTON') == 'yes'


def create_jinja2_env():
    """Sets up a jinja environment."""
    template_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'templates'))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_path))
    env.globals.update({'uri_for': webapp2.uri_for})
    return env

JINJA = create_jinja2_env()
