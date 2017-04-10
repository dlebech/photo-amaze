"""Appengine configuration.
"""
# Add libs to import path
from google.appengine.ext import vendor
vendor.add('lib')

###
# Setup Flickr API
###
import flickr_api # NOQA
from photoamaze import config # NOQA
flickr_api.set_keys(api_key=config.Flickr.api_key,
                    api_secret=config.Flickr.api_secret)
flickr_api.enable_cache()


###
# Setup app stats.
###
# Uncomment to enable.
#appstats_CALC_RPC_COSTS = True
#
#
#def webapp_add_wsgi_middleware(app):
#    from google.appengine.ext.appstats import recording
#    app = recording.appstats_wsgi_middleware(app)
#    return app
