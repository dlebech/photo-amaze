"""
    handlers
    ========

    Contains all the handler for PhotoMaze.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import sys
import json
import base64
import logging
import mimetypes
import traceback
from urllib import quote

import webapp2
import flickr_api
from instagram.oauth2 import OAuth2AuthExchangeError
from webapp2_extras import sessions
from google.appengine.api import images as gae_images, memcache, urlfetch
from google.appengine.ext import blobstore, ndb

from photoamaze import models, util, imageutil, mail, auth, config
from photoamaze.config import JINJA, MEMCACHE_TIME, Flickr, Instagram


class BaseHandler(webapp2.RequestHandler):
    def head(self, *args, **kwargs):
        """Fall-back method for head request."""
        pass

    def options(self, *args, **kwargs):
        """Fall-back method for an options request"""
        self.response.headers['Allow'] = 'GET,OPTIONS,HEAD'

    @webapp2.cached_property
    def session(self):
        """Returns the current session."""
        return self.session_store.get_session()

    def get_access(self, access_id):
        """Gets the access settings for the given access ID. Will usually be a
        maze ID."""
        access = self.session.get(access_id)
        if not access:
            access = dict(has_access=False, is_admin=False)
            self.session[access_id] = access
        return access

    def has_access(self, access_id):
        return self.get_access(access_id).get('has_access', False)

    def is_admin(self, access_id):
        return self.get_access(access_id).get('is_admin', False)

    def update_access(self, access_id, **kw):
        access = self.get_access(access_id)
        access.update(**kw)

        # Always explicitly set the session value to ensure that the session
        # backend knows the value has been updated.
        self.session[access_id] = access

    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    def handle_exception(self, exception, debug, *args, **kwargs):
        handle_http_exception(self.request, self.response, exception)

    def prepare_response(self, template_name, **template_vars):
        # Prepare template variables.
        if template_vars is None:
            template_vars = {}

        # Prepare empty html status
        if 'status' not in template_vars:
            template_vars.update(status=util.html_status())

        # Add the maze template variable.
        if hasattr(self, 'maze'):
            template_vars.update(maze=self.maze)
            template_vars.update(**self.get_access(self.maze.key.id()))

        # Add current params.
        template_vars.update(params=self.request.params)

        # Add configuration
        template_vars.update(config=config)

        # Render the template and write.
        resp = JINJA.get_template(template_name).render(**template_vars)
        self.response.write(resp)


class LandingHandler(BaseHandler):
    def get(self):
        self.prepare_response('landing.html')

    def post(self):
        maze_type = self.request.POST.get('maze-type')
        if maze_type == 'public':
            self.create_public()
        elif maze_type == 'private':
            self.create_private()
        else:
            self.abort(400)

    def create_public(self):
        flickr_tags = self.request.POST.get('flickr-tags', '')
        flickr_user = self.request.POST.get('flickr-user', '')

        error = ''
        if not flickr_tags and not flickr_user:
            error = 'Empty search values'
        elif len(flickr_tags) > 100 or len(flickr_user) > 100:
            error = 'Flickr search string is too long'

        if error:
            self.prepare_response('landing.html', public_error=error)
        else:
            self.redirect_to('public-maze',
                             ft=flickr_tags,
                             fu=flickr_user)

    def create_private(self):
        email = self.request.POST.get('maze-email')
        if not email:
            self.prepare_response('landing.html',
                                  private_error='Email is required')
            return
        password = self.request.POST.get('maze-password')
        maze_key = models.Maze.create(email, password=password)
        maze = maze_key.get()
        maze_url = self.uri_for('maze', maze_id=maze.key.id(), _full=True)
        admin_url = self.uri_for('maze-admin',
                                 maze_id=maze.key.id(),
                                 admin_key=maze.admin_key,
                                 _full=True)
        mail.send_welcome(email, maze_url, admin_url)
        self.prepare_response('maze/created.html', maze=maze)


class CreditsHandler(BaseHandler):
    def get(self):
        self.prepare_response('credits.html')


class PrivacyHandler(BaseHandler):
    def get(self):
        self.prepare_response('privacy.html')


class TermsHandler(BaseHandler):
    def get(self):
        self.prepare_response('terms.html')


class ImageHandler(BaseHandler):
    def serve_image(self, image_key):
        decoded = base64.urlsafe_b64decode(image_key)
        img_type, img_url_key, size = decoded.split(';')
        img_ok = False

        if img_type == 'b':  # Blob
            img_ok = self._serve_blob(img_url_key, size)
        elif img_type == imageutil.EXTERNAL_FLICKR:
            img_ok = self._serve_external(img_url_key, Flickr.memcache_time)
        elif img_type == imageutil.EXTERNAL_INSTAGRAM:
            img_ok = self._serve_external(img_url_key, Instagram.memcache_time)

        if not img_ok:
            self.abort(404)

    def _serve_external(self, image_url_key, memcache_time):
        url = base64.b64decode(image_url_key)
        content = memcache.get(url)
        content_type = None

        if content is None:
            resp = urlfetch.fetch(url, validate_certificate=True)
            content = resp.content
            content_type = resp.headers.get('content-type', 'image/jpeg')
            # If the contents are less than 800KB, try and store it in memcache
            # with a timeout of 24 hours.
            if len(content) < 800000:
                try:
                    memcache.set(url, content, time=memcache_time)
                except Exception as e:
                    logging.exception(e)

        if content_type is None:
            guess = mimetypes.guess_type(url)
            if guess[0] is not None:
                content_type = guess[0]
            else:
                content_type = 'image/jpeg'

        self.response.content_type = content_type
        self.response.headers['Cache-Control'] = 'public, max-age=36000'
        self.response.headers['Pragma'] = 'Public'
        self.response.write(content)
        return True

    def _serve_blob(self, image_key, size):
        maze_image = ndb.Key(urlsafe=image_key).get()

        size = int(size)
        if size < 0 or size > 1024:
            size = 1024

        img = None

        if maze_image.image_key:
            blob_info = blobstore.get(maze_image.image_key)
            if blob_info:
                with blob_info.open() as blob_reader:
                    img = gae_images.resize(
                        blob_reader.read(),
                        width=size,
                        height=size,
                        output_encoding=gae_images.JPEG,
                        correct_orientation=gae_images.CORRECT_ORIENTATION)
        elif maze_image.image:
            if size == 1024:  # Image should already be 1024.
                img = maze_image.image
            else:
                img = gae_images.resize(maze_image.image,
                                        width=size,
                                        height=size,
                                        output_encoding=gae_images.JPEG)

        if img:
            self.response.content_type = 'image/jpeg'
            self.response.headers['Cache-Control'] = 'public, max-age=36000'
            self.response.headers['Pragma'] = 'Public'
            self.response.write(img)
            return True

        return False


class PublicImageHandler(ImageHandler):
    def get(self, image_id):
        self.serve_image(image_id)


class PublicMazeHandler(BaseHandler):
    def get(self):
        flickr_tags = self.request.GET.get('ft', '')
        flickr_user = self.request.GET.get('fu', '')
        name = ' | '.join((flickr_tags, flickr_user))
        self.prepare_response('maze/maze.html',
                              name=util.html_escape(name),
                              enable_sharing=True,
                              share_url=quote(self.request.url),
                              public=True)


class PublicImageListHandler(BaseHandler):
    """Handler for returning a list of images for a public maze."""
    def get(self, *args, **kwargs):
        size = int(self.request.GET.get('size', 0))
        flickr_tags = self.request.GET.get('ft', '')
        flickr_user = self.request.GET.get('fu', '')

        images = imageutil.flickr_search(flickr_tags,
                                         flickr_user,
                                         size=size)

        # Prepare the real urls.
        for image in images:
            image.url = self.uri_for(
                'public-image', image_id=base64.urlsafe_b64encode(image.url))

        images = [img.to_dict() for img in images]
        self.response.content_type = 'application/json'
        self.response.write(json.dumps(images))


class AuthInstagramHandler(BaseHandler):
    """Handler for authorizing with Instagram. All parameters are received in
    the query string."""
    def get(self, *args, **kwargs):
        maze_id = self.request.GET.get('maze_id')
        admin_key = self.request.GET.get('admin_key')
        code = self.request.GET.get('code')
        error = self.request.GET.get('error')
        if maze_id and admin_key and code:
            maze = models.Maze.get_by_id(maze_id)
            if maze and maze.admin_key == admin_key:
                try:
                    # The redirect url has to be re-contructed. Otherwise
                    # Instagram does not trust us.
                    redirect_url = self.uri_for('auth-instagram',
                                                maze_id=maze_id,
                                                admin_key=admin_key,
                                                _full=True)
                    api = auth.init_instagram(redirect_url=redirect_url)

                    # Get a permanent access token from the code.
                    token, user = api.exchange_code_for_access_token(code)

                    # Create or update the user access token.
                    user_access = models.InstagramUserAccess.create_or_update(
                        user['id'], token)

                    # Update the maze's Instagram settings with the access key.
                    if maze.instagram is None:
                        maze.instagram = models.InstagramSettings()
                    maze.instagram.user_access = user_access
                    maze.put()
                    self.redirect_to(
                        'maze-admin', maze_id=maze_id, admin_key=admin_key,
                        success='Successfully linked your Instagram account')
                except OAuth2AuthExchangeError as e:
                    logging.exception(e)
                    self.abort(400, explanation=e.description)
                except Exception as e:
                    logging.exception(e)
                    self.abort(400, explanation=e.message)
            else:
                self.abort(400, explanation='Invalid maze or admin key')
        elif maze_id and admin_key and error:
            maze = models.Maze.get_by_id(maze_id)
            if maze and maze.admin_key == admin_key:
                self.redirect_to(
                    'maze-admin', maze_id=maze_id, admin_key=admin_key,
                    error='Something went wrong...')

            else:
                self.abort(400, explanation='Invalid maze or admin key')
        else:
            self.abort(400, explanation='Invalid parameters')


class AuthFlickrHandler(BaseHandler):
    """Handler for authorizing with Flickr. All parameters are received in the
    query string."""
    def get(self, *args, **kwargs):
        maze_id = self.request.GET.get('maze_id')
        admin_key = self.request.GET.get('admin_key')
        request_token = self.request.GET.get('oauth_token')
        verifier = self.request.GET.get('oauth_verifier')
        if maze_id and admin_key and request_token and verifier:
            maze = models.Maze.get_by_id(maze_id)
            if maze and maze.admin_key == admin_key:
                token = models.OAuthToken.get_by_id(request_token, namespace='')
                if token:
                    # Note: Make sure token key, token secret and verifier are
                    # not unicode. Otherwise, oauth will fail in hmac
                    # generation.
                    a = flickr_api.auth.AuthHandler(
                        request_token_key=str(token.key.id()),
                        request_token_secret=str(token.secret))

                    # Set the verification code from Flickr.
                    a.set_verifier(str(verifier))

                    # Get the current user. Use the authhandler as "token"
                    user = flickr_api.Person.getFromToken(token=a)

                    # Create or update user access and save the maze.
                    user_access = models.FlickrUserAccess.create_or_update(
                        user.id, a.access_token.key, a.access_token.secret)
                    if maze.flickr is None:
                        maze.flickr = models.FlickrSettings()
                    maze.flickr.user_access = user_access
                    maze.put()
                    self.redirect_to('maze-admin',
                                     maze_id=maze_id,
                                     admin_key=admin_key)
                else:
                    self.abort(403,
                               explanation='I cannot authorize you right now.')
            else:
                self.abort(400, explanation='Invalid maze or admin key')
        else:
            self.abort(400, explanation='Invalid parameters')


class AuthFacebookHandler(BaseHandler):
    """Handler for authorizing with Facebook. All parameters are received in the
    query string."""
    def get(self, *args, **kwargs):
        maze_id = self.request.GET.get('maze_id')
        admin_key = self.request.GET.get('admin_key')
        code = self.request.GET.get('code')
        error = self.request.GET.get('error')
        if maze_id and admin_key and code:
            maze = models.Maze.get_by_id(maze_id)
            if maze and maze.admin_key == admin_key:
                try:
                    # The redirect url has to be re-contructed. Otherwise
                    # Facebook does not trust us.
                    redirect_url = self.uri_for('auth-facebook',
                                                maze_id=maze_id,
                                                admin_key=admin_key,
                                                _full=True)

                    token = auth.FacebookAuth.get_auth_token_from_code(
                        code, redirect_url)

                    logging.info(token)

                    api = auth.FacebookAuth(token)
                    user = api.get_profile()

                    # Create or update the user access token.
                    user_access = models.FacebookUserAccess.create_or_update(
                        user['id'], token)

                    # Update the maze's Facebook settings with the access key.
                    if maze.facebook is None:
                        maze.facebook = models.FacebookSettings()
                    maze.facebook.user_access = user_access
                    maze.put()
                    self.redirect_to(
                        'maze-admin', maze_id=maze_id, admin_key=admin_key,
                        success='Successfully linked your Facebook account')
                except Exception as e:
                    logging.exception(e)
                    self.abort(400, explanation=e.message)
            else:
                self.abort(400, explanation='Invalid maze or admin key')
        elif maze_id and admin_key and error:
            maze = models.Maze.get_by_id(maze_id)
            if maze and maze.admin_key == admin_key:
                self.redirect_to(
                    'maze-admin', maze_id=maze_id, admin_key=admin_key,
                    error='Something went wrong...')
            else:
                self.abort(400, explanation='Invalid maze or admin key')
        else:
            self.abort(400, explanation='Invalid parameters')


class MazeLoginHandler(BaseHandler):
    def get(self, maze_id, *args, **kwargs):
        self.maze = models.Maze.get_by_id(maze_id)
        self.prepare_response('maze/login.html')

    def post(self, maze_id, *args, **kwargs):
        self.maze = models.Maze.get_by_id(maze_id)
        password = self.request.POST.get('password')
        if self.maze.validate_password(password):
            self.update_access(maze_id, has_access=True)
            referrer = str(self.request.POST.get('referrer'))
            if referrer:
                self.redirect(referrer)
            else:
                self.redirect_to('maze-options', maze_id=maze_id)
        else:
            self.prepare_response('maze/login.html',
                                  error='Wrong password')


def maze_required(handler):
    """Decorator for indicating that a handler method requires a valid maze as
    parameter. Also checks for a password and redirects to login page if the
    access level is not correct.

    """
    def check_maze(self, maze_id, *args, **kwargs):
        maze = models.Maze.get_by_id(maze_id)
        if maze:
            self.maze = maze

            # If there is a password but the access level is False, redirect to
            # login url. Otherwise, proceed with the handler.
            if not maze.password:
                self.update_access(maze_id, has_access=True)
            elif maze.password and not self.has_access(maze_id):
                return self.redirect_to('maze-login',
                                        maze_id=maze_id,
                                        referrer=self.request.url)

            handler(self, maze_id, *args, **kwargs)
        else:
            self.abort(404)

    return check_maze


def maze_admin_required(handler):
    """Decorator for indicating that a handler method requires a valid maze and
    a maze admin.  parameter. Checks for a password and redirects to login page
    if the access level is not correct.

    """
    def check_maze_admin(self, maze_id, admin_key, *args, **kwargs):
        maze = models.Maze.get_by_id(maze_id)
        if maze:
            self.maze = maze

            # If there is a password but the access level is False, redirect to
            # login url. Otherwise, proceed with the handler.
            if not maze.password:
                self.update_access(maze_id, has_access=True)
            elif maze.password and not self.has_access(maze_id):
                return self.redirect_to('maze-login',
                                        maze_id=maze_id,
                                        referrer=self.request.url)

            # Now check the admin key.
            if maze.admin_key == admin_key:
                self.update_access(maze_id, is_admin=True)
                handler(self, maze_id, admin_key, *args, **kwargs)
            else:
                self.abort(403, explanation='Wrong admin key')
        else:
            self.abort(404)

    return check_maze_admin


class MazeHandler(BaseHandler):
    @maze_required
    def get(self, *args, **kwargs):
        self.prepare_response('maze/maze.html',
                              maze_id=self.maze.key.id(),
                              name=self.maze.name or 'A Photo Maze',
                              enable_sharing=self.maze.enable_sharing,
                              share_url=quote(self.request.url))


class MazeAdminHandler(BaseHandler):
    @maze_admin_required
    def get(self, maze_id, admin_key, *args, **kwargs):
        status = util.html_status()
        if 'error' in self.request.GET:
            status.error[''] = self.request.GET['error']
        if 'success' in self.request.GET:
            status.success[''] = self.request.GET['success']
        self.prepare_admin_page(maze_id, admin_key, status=status)

    def prepare_admin_page(self, maze_id, admin_key, **page_variables):
        instagram_user = self.prepare_instagram()
        flickr_user = self.prepare_flickr()
        # TODO: Facebook support when approved.
        # facebook_user = self.prepare_facebook()
        self.prepare_response('maze/admin.html',
                              instagram_user=instagram_user,
                              flickr_user=flickr_user,
                              **page_variables)

    def prepare_instagram(self):
        key = models.MazeCacheKey.instagram_user.format(self.maze.key.id())
        user = memcache.get(key)
        if not user:
            user = auth.check_instagram_user_for_maze(self.maze).get_result()
            if user:
                memcache.set(key, user, time=MEMCACHE_TIME)
        return user

    def prepare_flickr(self):
        key = models.MazeCacheKey.flickr_user.format(self.maze.key.id())
        user = memcache.get(key)
        if not user:
            user = auth.check_flickr_user_for_maze(self.maze).get_result()
            if user:
                user = user.getInfo()
                imageutil.flickr_buddy_icon(user)
                memcache.set(key, user, time=MEMCACHE_TIME)
        return user

    def prepare_facebook(self):
        key = models.MazeCacheKey.facebook_user.format(self.maze.key.id())
        user = memcache.get(key)
        if not user:
            user = auth.check_facebook_user_for_maze(self.maze).get_result()
            if user:
                memcache.set(key, user, time=MEMCACHE_TIME)
        return user


class MazeAdminConnectInstagramHandler(BaseHandler):
    @maze_admin_required
    def get(self, *args, **kwargs):
        redirect_url = self.uri_for('auth-instagram',
                                    maze_id=self.maze.key.id(),
                                    admin_key=self.maze.admin_key,
                                    _full=True)
        api = auth.init_instagram(redirect_url=redirect_url)
        url = api.get_authorize_url(scope=['public_content'])
        self.redirect(url)


class MazeAdminConnectFlickrHandler(BaseHandler):
    @maze_admin_required
    def get(self, *args, **kwargs):
        redirect_url = self.uri_for('auth-flickr',
                                    maze_id=self.maze.key.id(),
                                    admin_key=self.maze.admin_key,
                                    _full=True)

        # Instantiating the AuthHandler requests a request token from Flickr.
        a = flickr_api.auth.AuthHandler(callback=redirect_url)

        # Save the request token so we can find the secret later.
        models.OAuthToken(id=a.request_token.key,
                          secret=a.request_token.secret,
                          namespace='').put()
        url = a.get_authorization_url()
        self.redirect(url)


class MazeAdminConnectFacebookHandler(BaseHandler):
    @maze_admin_required
    def get(self, *args, **kwargs):
        # TODO: Facebook support when approved.
        self.response.write('Not yet')
        # redirect_url = self.uri_for('auth-facebook',
        #                             maze_id=self.maze.key.id(),
        #                             admin_key=self.maze.admin_key,
        #                             _full=True)
        # url = auth.FacebookAuth.get_auth_url(redirect_url)
        # self.redirect(url)


class MazeAdminSettingsHandler(MazeAdminHandler):
    """Handler for general maze settings."""
    @maze_admin_required
    def post(self, maze_id, admin_key, *args, **kwargs):
        status = util.html_status()
        self.maze.name = self.request.POST.get('maze-name')
        self.maze.admin_email = self.request.POST.get('maze-admin-email')
        self.maze.enable_sharing = bool(
            self.request.POST.get('maze-enable-sharing'))
        self.maze.put()
        status.success[''] = 'Settings updated'
        self.prepare_admin_page(maze_id, admin_key, status=status)


class MazeAdminInstagramHandler(MazeAdminHandler):
    """Handler for Instagram maze settings."""
    @maze_admin_required
    def post(self, maze_id, admin_key, *args, **kwargs):
        status = util.html_status()
        ps = self.request.POST
        self.maze.instagram.tag = ps.get('instagram-tag')
        self.maze.instagram.include_recent = bool(
            ps.get('instagram-include-recent'))
        self.maze.instagram.include_feed = bool(
            ps.get('instagram-include-feed'))
        self.maze.put()
        memcache.delete(models.MazeCacheKey.image_list
                        .format(self.maze.key.id()))
        status.success[''] = 'Instagram settings updated'
        self.prepare_admin_page(maze_id, admin_key, status=status)


class MazeAdminFlickrHandler(MazeAdminHandler):
    """Handler for Flickr maze settings."""
    @maze_admin_required
    def post(self, maze_id, admin_key, *args, **kwargs):
        status = util.html_status()
        ps = self.request.POST
        self.maze.flickr.tags = ps.get('flickr-tags')
        self.maze.flickr.user = ps.get('flickr-user')
        self.maze.flickr.include_recent = bool(
            ps.get('flickr-include-recent'))
        self.maze.flickr.include_favs = bool(
            ps.get('flickr-include-favs'))
        self.maze.put()
        memcache.delete(models.MazeCacheKey.image_list
                        .format(self.maze.key.id()))
        status.success[''] = 'Flickr settings updated'
        self.prepare_admin_page(maze_id, admin_key, status=status)


class MazeAdminPasswordHandler(MazeAdminHandler):
    """Handler for password settings."""
    @maze_admin_required
    def post(self, maze_id, admin_key, *args, **kwargs):
        status = util.html_status()

        old_password = self.request.POST.get('old-password')
        new_password = self.request.POST.get('new-password')
        new_password_repeat = self.request.POST.get('new-password-repeat')
        if not self.maze.validate_password(old_password):
            status.error['old-password'] = 'Current password is incorrect'
        elif not new_password:
            status.error['new-password'] = 'New password cannot be empty'
        elif new_password != new_password_repeat:
            status.error['new-password-repeat'] = ('New password and repeat '
                                                   'password must be equal')
        else:
            status.success[''] = 'Password changed successfully'
            self.maze.set_password(new_password)
        self.prepare_admin_page(maze_id, admin_key, status=status)


class MazeImageListHandler(BaseHandler):
    """Handler for returning a list of images for a maze."""
    @maze_required
    def get(self, *args, **kwargs):
        # TODO, add paging.
        size = int(self.request.GET.get('size', 0))
        images = imageutil.prepare_images_for_maze(self.maze,
                                                   size=size).get_result()
        for img in images:
            img.url = self.uri_for('maze-texture',
                                   maze_id=self.maze.key.id(),
                                   image_key=base64.urlsafe_b64encode(img.url))
        images = [img.to_dict() for img in images]
        self.response.content_type = 'application/json'
        self.response.write(json.dumps(images))


class MazeTextureHandler(ImageHandler):
    @maze_required
    def get(self, maze_id, image_key, *args, **kwargs):
        self.serve_image(image_key)


def handle_http_exception(request, response, exception):
    """Custom exception handler for all failed requests.
    """
    # Log the exception and set some standard values
    logging.exception(exception)
    code, title, explanation = _extract_exception_details(request,
                                                          response,
                                                          exception)

    # If the app is in debug mode, we would like to see a stacktrace.
    stacktrace = None
    if request.app.debug:
        stacktrace = ''.join(traceback.format_exception(*sys.exc_info()))

    response.set_status(code)

    # Default template is the html template.
    template = JINJA.get_template('httperror.html')

    rend = template.render(code=code, title=title, explanation=explanation,
                           stacktrace=stacktrace)
    response.write(rend)


def _extract_exception_details(request, response, exception):
    """Extracts exception information from a request-response and an exception.
    """
    # Set some standard values to fall back to if nothing comes of parsing the
    # request and exception details.
    code = 500  # Internal server error
    title = 'Unknown error'
    explanation = 'An unknown error occured, the error has been logged.'

    if hasattr(exception, 'code') and exception.code:
        code = exception.code

    # If the exception was thrown as part of the RequestHandler.abort, the
    # exception will be of the type WSGIHttpException and will contain a
    # comment/an explanation and/or a detail/title. It is confusing the way
    # webapp2 handles these things. "Explanation" is set internally but only
    # comment is available through the abort method.
    if hasattr(exception, 'detail') and exception.detail:
        title = exception.detail
    elif hasattr(exception, 'title') and exception.title:
        title = exception.title
    if hasattr(exception, 'comment') and exception.comment:
        explanation = exception.comment
    elif hasattr(exception, 'explanation') and exception.explanation:
        explanation = exception.explanation
    return (code, title, explanation)
