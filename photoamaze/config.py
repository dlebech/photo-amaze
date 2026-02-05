"""
    config
    ======

    Configuration.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import os

from photoamaze.util import ReadOnly


DEBUG = os.environ.get('GAE_ENV', '') != 'standard'
PEPPER = os.environ.get('AUTH_PEPPER')
EMAIL = os.environ.get('NO_REPLY_EMAIL')
MEMCACHE_TIME = 600 if not DEBUG else 1


class Flickr(ReadOnly):
    api_key = os.environ.get('FLICKR_API_KEY')
    api_secret = os.environ.get('FLICKR_API_SECRET')
    memcache_time = 86400 if not DEBUG else 1


class Twitter(ReadOnly):
    share_button = os.environ.get('TWITTER_SHARE_BUTTON') == 'yes'
