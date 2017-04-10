"""
    photoamaze
    ==========

    Creating photo mazes since 2014. Or something.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import webapp2

from photoamaze import config, routes
from photoamaze.handlers import handle_http_exception

app = webapp2.WSGIApplication(routes=routes.routes,
                              debug=config.DEBUG,
                              config=config.WEBAPP_CONFIG)
app.error_handlers[400] = handle_http_exception
app.error_handlers[401] = handle_http_exception
app.error_handlers[402] = handle_http_exception
app.error_handlers[403] = handle_http_exception
app.error_handlers[404] = handle_http_exception
app.error_handlers[500] = handle_http_exception
