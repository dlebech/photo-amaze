"""
    handlers
    ========

    Contains all the handlers for PhotoMaze.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import sys
import json
import base64
import logging
import mimetypes
import traceback
from urllib.parse import quote
from functools import wraps

import flickr_api
from flask import (request, session, render_template, redirect, url_for,
                   abort, Response, make_response)
from google.appengine.api import images as gae_images, memcache, urlfetch
from google.appengine.ext import blobstore, ndb

from photoamaze import models, util, imageutil, mail, auth, config
from photoamaze.config import MEMCACHE_TIME, Flickr
from photoamaze.routes import bp


# --- Session helpers ---

def get_access(access_id):
    access = session.get(access_id)
    if not access:
        access = dict(has_access=False, is_admin=False)
        session[access_id] = access
    return access


def has_access(access_id):
    return get_access(access_id).get('has_access', False)


def is_admin(access_id):
    return get_access(access_id).get('is_admin', False)


def update_access(access_id, **kw):
    access = get_access(access_id)
    access.update(**kw)
    session[access_id] = access


# --- Template helpers ---

def prepare_response(template_name, maze=None, **template_vars):
    if 'status' not in template_vars:
        template_vars['status'] = util.html_status()

    if maze is not None:
        template_vars['maze'] = maze
        template_vars.update(**get_access(maze.key.id()))

    template_vars['params'] = request.args if request.method == 'GET' else request.form
    template_vars['config'] = config

    return render_template(template_name, **template_vars)


# --- Decorators ---

def maze_required(f):
    @wraps(f)
    def decorated(maze_id, *args, **kwargs):
        maze = models.Maze.get_by_id(maze_id)
        if not maze:
            abort(404)

        if not maze.password:
            update_access(maze_id, has_access=True)
        elif maze.password and not has_access(maze_id):
            return redirect(url_for('main.maze_login', maze_id=maze_id,
                                    referrer=request.url))

        return f(maze_id, maze=maze, *args, **kwargs)
    return decorated


def maze_admin_required(f):
    @wraps(f)
    def decorated(maze_id, admin_key, *args, **kwargs):
        maze = models.Maze.get_by_id(maze_id)
        if not maze:
            abort(404)

        if not maze.password:
            update_access(maze_id, has_access=True)
        elif maze.password and not has_access(maze_id):
            return redirect(url_for('main.maze_login', maze_id=maze_id,
                                    referrer=request.url))

        if maze.admin_key != admin_key:
            abort(403)

        update_access(maze_id, is_admin=True)
        return f(maze_id, admin_key, maze=maze, *args, **kwargs)
    return decorated


# --- Route handlers ---

@bp.route('/', methods=['GET', 'POST'])
def landing():
    if request.method == 'GET':
        return prepare_response('landing.html')

    maze_type = request.form.get('maze-type')
    if maze_type == 'public':
        return _create_public()
    elif maze_type == 'private':
        return _create_private()
    else:
        abort(400)


def _create_public():
    flickr_tags = request.form.get('flickr-tags', '')
    flickr_user = request.form.get('flickr-user', '')

    error = ''
    if not flickr_tags and not flickr_user:
        error = 'Empty search values'
    elif len(flickr_tags) > 100 or len(flickr_user) > 100:
        error = 'Flickr search string is too long'

    if error:
        return prepare_response('landing.html', public_error=error)
    else:
        return redirect(url_for('main.public_maze', ft=flickr_tags,
                                fu=flickr_user))


def _create_private():
    email = request.form.get('maze-email')
    if not email:
        return prepare_response('landing.html',
                                private_error='Email is required')
    password = request.form.get('maze-password')
    maze_key = models.Maze.create(email, password=password)
    maze = maze_key.get()
    maze_url = url_for('main.maze', maze_id=maze.key.id(), _external=True)
    admin_url = url_for('main.maze_admin', maze_id=maze.key.id(),
                        admin_key=maze.admin_key, _external=True)
    mail.send_welcome(email, maze_url, admin_url)
    return prepare_response('maze/created.html', maze=maze)


@bp.route('/credits')
def credits():
    return prepare_response('credits.html')


@bp.route('/privacy')
def privacy():
    return prepare_response('privacy.html')


@bp.route('/terms')
def terms():
    return prepare_response('terms.html')


# --- Image serving ---

def _serve_external(image_url_key, memcache_time):
    url = base64.b64decode(image_url_key).decode()
    content = memcache.get(url)
    content_type = None

    if content is None:
        resp = urlfetch.fetch(url, validate_certificate=True)
        content = resp.content
        content_type = resp.headers.get('content-type', 'image/jpeg')
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

    response = make_response(content)
    response.content_type = content_type
    response.headers['Cache-Control'] = 'public, max-age=36000'
    response.headers['Pragma'] = 'Public'
    return response


def _serve_blob(image_key, size):
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
        if size == 1024:
            img = maze_image.image
        else:
            img = gae_images.resize(maze_image.image,
                                    width=size,
                                    height=size,
                                    output_encoding=gae_images.JPEG)

    if img:
        response = make_response(img)
        response.content_type = 'image/jpeg'
        response.headers['Cache-Control'] = 'public, max-age=36000'
        response.headers['Pragma'] = 'Public'
        return response

    return None


def serve_image(image_key):
    decoded = base64.urlsafe_b64decode(image_key).decode()
    img_type, img_url_key, size = decoded.split(';')
    result = None

    if img_type == 'b':
        result = _serve_blob(img_url_key, size)
    elif img_type == imageutil.EXTERNAL_FLICKR:
        result = _serve_external(img_url_key, Flickr.memcache_time)

    if result is None:
        abort(404)
    return result


@bp.route('/public/image/<path:image_id>')
def public_image(image_id):
    return serve_image(image_id)


@bp.route('/public/maze')
def public_maze():
    flickr_tags = request.args.get('ft', '')
    flickr_user = request.args.get('fu', '')
    name = ' | '.join((flickr_tags, flickr_user))
    return prepare_response('maze/maze.html',
                            name=util.html_escape(name),
                            enable_sharing=True,
                            share_url=quote(request.url),
                            public=True)


@bp.route('/public/image/list')
def public_image_list():
    size = int(request.args.get('size', 0))
    flickr_tags = request.args.get('ft', '')
    flickr_user = request.args.get('fu', '')

    images = imageutil.flickr_search(flickr_tags, flickr_user, size=size)

    for image in images:
        image.url = url_for('main.public_image',
                            image_id=base64.urlsafe_b64encode(
                                image.url.encode()).decode())

    images = [img.to_dict() for img in images]
    return Response(json.dumps(images), content_type='application/json')


# --- Auth routes ---

@bp.route('/auth/flickr')
def auth_flickr():
    maze_id = request.args.get('maze_id')
    admin_key = request.args.get('admin_key')
    request_token = request.args.get('oauth_token')
    verifier = request.args.get('oauth_verifier')
    if maze_id and admin_key and request_token and verifier:
        maze = models.Maze.get_by_id(maze_id)
        if maze and maze.admin_key == admin_key:
            token = models.OAuthToken.get_by_id(request_token, namespace='')
            if token:
                a = flickr_api.auth.AuthHandler(
                    request_token_key=str(token.key.id()),
                    request_token_secret=str(token.secret))

                a.set_verifier(str(verifier))
                user = flickr_api.Person.getFromToken(token=a)

                user_access = models.FlickrUserAccess.create_or_update(
                    user.id, a.access_token.key, a.access_token.secret)
                if maze.flickr is None:
                    maze.flickr = models.FlickrSettings()
                maze.flickr.user_access = user_access
                maze.put()
                return redirect(url_for('main.maze_admin',
                                        maze_id=maze_id,
                                        admin_key=admin_key))
            else:
                abort(403)
        else:
            abort(400)
    else:
        abort(400)


# --- Maze routes ---

@bp.route('/maze/<maze_id>/login', methods=['GET', 'POST'])
def maze_login(maze_id):
    maze = models.Maze.get_by_id(maze_id)
    if not maze:
        abort(404)

    if request.method == 'GET':
        return prepare_response('maze/login.html', maze=maze)

    password = request.form.get('password')
    if maze.validate_password(password):
        update_access(maze_id, has_access=True)
        referrer = request.form.get('referrer', '')
        if referrer:
            return redirect(referrer)
        else:
            return redirect(url_for('main.maze', maze_id=maze_id))
    else:
        return prepare_response('maze/login.html', maze=maze,
                                error='Wrong password')


@bp.route('/maze/<maze_id>/')
@bp.route('/maze/<maze_id>')
@maze_required
def maze(maze_id, maze=None):
    return prepare_response('maze/maze.html',
                            maze=maze,
                            maze_id=maze.key.id(),
                            name=maze.name or 'A Photo Maze',
                            enable_sharing=maze.enable_sharing,
                            share_url=quote(request.url))


@bp.route('/maze/<maze_id>/texture/<image_key>')
@maze_required
def maze_texture(maze_id, image_key, maze=None):
    return serve_image(image_key)


@bp.route('/maze/<maze_id>/image/list')
@maze_required
def maze_image_list(maze_id, maze=None):
    size = int(request.args.get('size', 0))
    images = imageutil.prepare_images_for_maze(maze, size=size).get_result()
    for img in images:
        img.url = url_for('main.maze_texture',
                          maze_id=maze.key.id(),
                          image_key=base64.urlsafe_b64encode(
                              img.url.encode()).decode())
    images = [img.to_dict() for img in images]
    return Response(json.dumps(images), content_type='application/json')


# --- Admin routes ---

def _prepare_admin_page(maze, **page_variables):
    flickr_user = _prepare_flickr(maze)
    return prepare_response('maze/admin.html', maze=maze,
                            flickr_user=flickr_user,
                            **page_variables)


def _prepare_flickr(maze):
    key = models.MazeCacheKey.flickr_user.format(maze.key.id())
    user = memcache.get(key)
    if not user:
        user = auth.check_flickr_user_for_maze(maze).get_result()
        if user:
            user = user.getInfo()
            imageutil.flickr_buddy_icon(user)
            memcache.set(key, user, time=MEMCACHE_TIME)
    return user


@bp.route('/maze/<maze_id>/admin/<admin_key>')
@maze_admin_required
def maze_admin(maze_id, admin_key, maze=None):
    status = util.html_status()
    if 'error' in request.args:
        status.error[''] = request.args['error']
    if 'success' in request.args:
        status.success[''] = request.args['success']
    return _prepare_admin_page(maze, status=status)


@bp.route('/maze/<maze_id>/admin/<admin_key>/settings', methods=['POST'])
@maze_admin_required
def maze_admin_settings(maze_id, admin_key, maze=None):
    status = util.html_status()
    maze.name = request.form.get('maze-name')
    maze.admin_email = request.form.get('maze-admin-email')
    maze.enable_sharing = bool(request.form.get('maze-enable-sharing'))
    maze.put()
    status.success[''] = 'Settings updated'
    return _prepare_admin_page(maze, status=status)


@bp.route('/maze/<maze_id>/admin/<admin_key>/password', methods=['POST'])
@maze_admin_required
def maze_admin_password(maze_id, admin_key, maze=None):
    status = util.html_status()

    old_password = request.form.get('old-password')
    new_password = request.form.get('new-password')
    new_password_repeat = request.form.get('new-password-repeat')
    if not maze.validate_password(old_password):
        status.error['old-password'] = 'Current password is incorrect'
    elif not new_password:
        status.error['new-password'] = 'New password cannot be empty'
    elif new_password != new_password_repeat:
        status.error['new-password-repeat'] = ('New password and repeat '
                                               'password must be equal')
    else:
        status.success[''] = 'Password changed successfully'
        maze.set_password(new_password)
    return _prepare_admin_page(maze, status=status)


@bp.route('/maze/<maze_id>/admin/<admin_key>/flickr', methods=['POST'])
@maze_admin_required
def maze_admin_flickr(maze_id, admin_key, maze=None):
    status = util.html_status()
    maze.flickr.tags = request.form.get('flickr-tags')
    maze.flickr.user = request.form.get('flickr-user')
    maze.flickr.include_recent = bool(request.form.get('flickr-include-recent'))
    maze.flickr.include_favs = bool(request.form.get('flickr-include-favs'))
    maze.put()
    memcache.delete(models.MazeCacheKey.image_list.format(maze.key.id()))
    status.success[''] = 'Flickr settings updated'
    return _prepare_admin_page(maze, status=status)


@bp.route('/maze/<maze_id>/admin/<admin_key>/connect/flickr')
@maze_admin_required
def maze_admin_connect_flickr(maze_id, admin_key, maze=None):
    redirect_url = url_for('main.auth_flickr',
                           maze_id=maze.key.id(),
                           admin_key=maze.admin_key,
                           _external=True)

    a = flickr_api.auth.AuthHandler(callback=redirect_url)

    models.OAuthToken(id=a.request_token_key,
                      secret=a.request_token_secret,
                      namespace='').put()
    auth_url = a.get_authorization_url()
    return redirect(auth_url)


# --- Error handler ---

def handle_http_exception(exception):
    logging.exception(exception)
    code = getattr(exception, 'code', 500)
    title = getattr(exception, 'name', 'Unknown error')
    explanation = getattr(exception, 'description',
                         'An unknown error occurred, the error has been logged.')

    stacktrace = None
    if config.DEBUG:
        stacktrace = ''.join(traceback.format_exception(*sys.exc_info()))

    return render_template('httperror.html', code=code, title=title,
                           explanation=explanation,
                           stacktrace=stacktrace), code
