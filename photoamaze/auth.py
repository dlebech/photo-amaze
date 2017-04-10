"""
    auth
    ====

    Authentication module.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import json
import urllib
import urlparse
import logging

import flickr_api
from flickr_api.flickrerrors import FlickrAPIError
from instagram import InstagramAPI, InstagramAPIError
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from photoamaze import config


class FacebookAuthError(Exception):
    pass


class FacebookAuth(object):
    GRAPH_URL = 'https://graph.facebook.com'
    VERSION = 'v2.1'

    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = '{}/{}'.format(self.GRAPH_URL, self.VERSION)

    @classmethod
    def get_auth_url(cls, redirect_url):
        url = 'https://www.facebook.com/dialog/oauth?'
        args = {
            'client_id': config.Facebook.app_id,
            'redirect_uri': redirect_url,
            'scope': 'user_photos'
        }
        return url + urllib.urlencode(args)

    @classmethod
    def get_auth_token_from_code(cls, code, redirect_url):
        url = cls.GRAPH_URL + '/oauth/access_token?'
        args = {
            'code': code,
            'redirect_uri': redirect_url,
            'client_id': config.Facebook.app_id,
            'client_secret': config.Facebook.app_secret
        }
        url += urllib.urlencode(args)
        resp = urlfetch.fetch(url)
        res = dict(urlparse.parse_qsl(resp.content))
        if not res:  # Not url-form
            res = json.loads(resp.content)
        if 'access_token' in res:
            return res['access_token']
        elif 'error' in res:
            raise FacebookAuthError(res['error']['message'])
        else:
            raise Exception('Unknown error')

    def get_profile(self):
        args = {
            'access_token': self.access_token,
            'fields': 'id,name,picture'
        }
        url = self.base_url + '/me?{}'.format(urllib.urlencode(args))
        return self.make_request(url, args)

    def make_request(self, url, args):
        resp = urlfetch.fetch(url)
        res = json.loads(resp.content)
        if 'error' in res:
            raise FacebookAuthError(res['error']['message'])
        else:
            return res


def init_instagram(access_token=None, redirect_url=None):
    return InstagramAPI(client_id=config.Instagram.client_id,
                        client_secret=config.Instagram.client_secret,
                        access_token=access_token,
                        redirect_uri=redirect_url)


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


@ndb.tasklet
def check_instagram_user_for_maze(maze):
    user = None
    if maze.instagram.user_access:
        user_access = yield maze.instagram.user_access.get_async()
        if user_access:
            try:
                api = init_instagram(access_token=user_access.access_token)
                user = api.user(user_access.key.id())
            except InstagramAPIError as e:
                logging.exception(e)
                # If status 400, token has probably been revoked so we
                # should delete the link.
                if e.status_code == 400:
                    maze.instagram.user_access = None
                    yield user_access.key.delete_async(), maze.put_async()
    raise ndb.Return(user)


@ndb.tasklet
def check_facebook_user_for_maze(maze):
    user = None
    if maze.facebook.user_access:
        user_access = yield maze.facebook.user_access.get_async()
        if user_access:
            try:
                api = FacebookAuth(user_access.access_token)
                user = api.get_profile()
            except FacebookAuthError as e:
                logging.exception(e)
                maze.facebook.user_access = None
                yield user_access.key.delete_async(), maze.put_async()
    raise ndb.Return(user)
