"""
    routes
    ======

    All the routes for Photo Amaze.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
from flask import Blueprint

bp = Blueprint('main', __name__)

# Import handlers to register route decorators
from photoamaze import handlers  # noqa: E402, F401
