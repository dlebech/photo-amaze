"""
    auth
    ====

    Authentication module.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import logging

import flickr_api
from flickr_api.flickrerrors import FlickrAPIError
from google.appengine.ext import ndb

from photoamaze import config


def init_flickr_auth(access_token_key, access_token_secret):
    return flickr_api.auth.AuthHandler(
        access_token_key=str(access_token_key),
        access_token_secret=str(access_token_secret))


@ndb.tasklet
def check_flickr_user_for_maze(maze):
    user = None
    if maze.flickr.user_access:
        user_access = yield maze.flickr.user_access.get_async()
        if user_access:
            try:
                a = init_flickr_auth(user_access.access_token,
                                     user_access.access_token_secret)
                user = flickr_api.Person.getFromToken(token=a)
                user.setToken(token=a)
            except FlickrAPIError as e:
                logging.exception(e)
                # If status 98, token has probably been revoked so we should
                # delete the link.
                if e.code == 98:
                    maze.flickr.user_access = None
                    yield user_access.key.delete_async(), maze.put_async()
    raise ndb.Return(user)
