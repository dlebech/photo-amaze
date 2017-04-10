"""
    imageutil
    =========

    Utility library for image handling both internally and from external APIs.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import base64
import logging
import threading

import flickr_api
from google.appengine.api import memcache
from google.appengine.ext import ndb

from photoamaze import config, models, auth

EXTERNAL_INSTAGRAM = 'i'
EXTERNAL_FLICKR = 'f'
FLICKR_BUDDYICON_URL_TEMPLATE = ("https://farm{farm}.staticflickr.com/{server}/"
                                 "buddyicons/{nsid}.jpg")
FLICKR_BUDDYICON_URL = "https://www.flickr.com/images/buddyicon.gif"
FLICKR_EXTRAS = 'url_s,url_z,url_l,owner_name,license'
FLICKR_PHOTO_URL = 'https://www.flickr.com/photos/{user_id}/{photo_id}'
FLICKR_LICENSES_ALL = '0,1,2,3,4,5,6,7,8'  # All license types.
FLICKR_LICENSES_PUBLIC = '1,2,3,4,5,6,7,8'  # Not "All rights reserved".
FLICKR_LICENSES = None
FLICKR_LOCK = threading.Lock()


def __prepare_search(s, remove_whitespace=False, error_message=None):
    s = s.strip() if s else ''
    if remove_whitespace:
        s = s.replace(' ', '')
    if error_message and not s:
        raise ValueError(error_message)
    return s[0:100]


def __format_external_url(external_id, url):
    return '{};{};0'.format(external_id, base64.b64encode(url))


def __prepare_flickr_photos(photos, size):
    imagelist = []
    for photo in photos:
        url = None
        # Try three different sizes.
        if size >= 1024:
            url = photo.get('url_l')
        if not url or 512 <= size < 1024:
            url = photo.get('url_z')
        if not url or size < 512:
            url = photo.get('url_s')

        title = photo.title
        owner = photo.owner.id
        name = photo.get('ownername') or owner or ''
        photo_url = FLICKR_PHOTO_URL.format(user_id=owner,
                                            photo_id=photo.get('id'))
        attribution = u"'{}' by {}".format(title, name)
        license = flickr_license(photo.get('license', ''))

        # If there was an appropriate size, add the image to the list.
        if url:
            url = __format_external_url(EXTERNAL_FLICKR, url)
            img = models.LocalImage(url, title, attribution=attribution,
                                    external_url=photo_url, license=license)
            imagelist.append(img)
    return imagelist


def __prepare_instagram_media(media_list, size=1024):
    imagelist = []
    for media in media_list:
        if media.type == 'image':
            media_url = media.get_standard_resolution_url()
            if size < 512:
                media_url = media.get_low_resolution_url()
            url = __format_external_url(EXTERNAL_INSTAGRAM, media_url)
            msg = media.caption.text if media.caption else ''
            img = models.LocalImage(url, msg)
            imagelist.append(img)
    return imagelist


@ndb.tasklet
def __prepare_internal_images_for_maze(maze, size, page, page_size):
    # Use the breakpoint values from bootstrap's responsive classes.
    # Extra small
    size = size or 0
    if size < 768:
        size = 256
    # Small
    elif 768 <= size < 992:
        size = 512
    # Eveything else (desktop)
    else:
        size = 1024

    q = models.MazeImage.query(ancestor=maze.key)
    # TODO: Add support for page number.
    entities, next_cursor, more = yield q.fetch_page_async(page_size)

    image_list = []
    for entity in entities:
        image_key = 'b;{};{}'.format(entity.key.urlsafe(), size)
        img = models.LocalImage(image_key, entity.message)
        image_list.append(img)

    raise ndb.Return(image_list)


@ndb.tasklet
def __prepare_flickr_images_for_maze(maze, size, page, page_size):
    # Find a Flickr user, if it exists.
    flickr_user = yield auth.check_flickr_user_for_maze(maze)
    token = flickr_user.getToken() if flickr_user else None

    image_set = set()

    try:
        if maze.flickr.tags or maze.flickr.user:
            image_set.update(flickr_search(maze.flickr.tags, maze.flickr.user,
                                           auth=token, size=size, page=page,
                                           page_size=page_size))

        if flickr_user and maze.flickr.include_recent:
            photos = flickr_user.getPhotos(token=token,
                                           extras=FLICKR_EXTRAS,
                                           page=page,
                                           per_page=page_size)
            image_set.update(__prepare_flickr_photos(photos, size))

        if flickr_user and maze.flickr.include_favs:
            photos = flickr_user.getFavorites(token=token,
                                              extras=FLICKR_EXTRAS,
                                              page=page,
                                              per_page=page_size)
            image_set.update(__prepare_flickr_photos(photos, size))
    except Exception as e:
        # For now, just log everything.
        logging.exception(e)

    raise ndb.Return(list(image_set))


@ndb.tasklet
def __prepare_instagram_images_for_maze(maze, size, page, page_size):
    api = None

    # Check if user specific API calls are possible.
    if maze.instagram.user_access:
        user_access = yield maze.instagram.user_access.get_async()
        if user_access:
            api = auth.init_instagram(access_token=user_access.access_token)

    if not api:
        raise ndb.Return([])

    image_set = set()

    try:
        if maze.instagram.tag:
            images = instagram_search_tag(maze.instagram.tag, api)
            image_set.update(images)

        if maze.instagram.include_recent:
            recent_media, next_ = api.user_recent_media()
            image_set.update(__prepare_instagram_media(recent_media))

        if maze.instagram.include_feed:
            recent_media, next_ = api.user_media_feed()
            image_set.update(__prepare_instagram_media(recent_media))
    except Exception as e:
        # For now, just log everything.
        logging.exception(e)

    raise ndb.Return(list(image_set))


def instagram_search_tag(tag, api, size=1024):
    tag = __prepare_search(tag, True, 'Tag is invalid')
    medias, _next = api.tag_recent_media(20, None, tag)
    images = set()
    images.update(__prepare_instagram_media(medias, size=size))
    return list(images)


def flickr_search(tags, user, auth=None, size=1024, page=1, page_size=30):
    tags = __prepare_search(tags)
    user = __prepare_search(user)

    # Remove whitespace around tag commas.
    tags = ','.join(tag.strip() for tag in tags.split(','))

    license = FLICKR_LICENSES_ALL

    # If the search is not authenticated, it is public so we do not want photos
    # with All Rights Reserved as license.
    if not auth:
        license = FLICKR_LICENSES_PUBLIC

    photos = []
    try:
        photos = flickr_api.Photo.search(user_id=user,
                                         tags=tags,
                                         page=page,
                                         per_page=page_size,
                                         media='photos',
                                         extras=FLICKR_EXTRAS,
                                         license=license,
                                         token=auth)
    except Exception as e:
        logging.exception(e)
    return __prepare_flickr_photos(photos, size)


def flickr_buddy_icon(person):
    """Adds a buddy icon url to the given person."""
    buddyicon = FLICKR_BUDDYICON_URL
    try:
        if int(person['iconserver']) > 0:
            buddyicon = FLICKR_BUDDYICON_URL_TEMPLATE.format(
                farm=person['iconfarm'],
                server=person['iconserver'],
                nsid=person['nsid'])
    except:
        pass
    person['buddyiconurl'] = buddyicon


def flickr_license(license_id):
    """Finds a Flickr license with the given ID."""
    # OMG what a ceremony to get some simple caching of an object!
    global FLICKR_LICENSES
    if not FLICKR_LICENSES:
        with FLICKR_LOCK:
            # Double checked locking
            if not FLICKR_LICENSES:
                cache_key = 'flickr_licenses'
                FLICKR_LICENSES = memcache.get(cache_key)
                if not FLICKR_LICENSES:
                    FLICKR_LICENSES = {}
                    license_list = flickr_api.License.getList()
                    for license in license_list:
                        FLICKR_LICENSES[license.id] = {
                            'name': license.name,
                            'url': license.url
                        }
                    memcache.set(cache_key, FLICKR_LICENSES)
    return FLICKR_LICENSES.get(license_id)


@ndb.tasklet
def prepare_images_for_maze(maze, page=1, page_size=20, size=0):
    cache_key = '{}:imagelist'.format(maze.key.id())
    image_list = memcache.get(cache_key)

    if not image_list:
        image_list = []
        internal = __prepare_internal_images_for_maze(maze, size,
                                                      page, page_size)
        flickr = __prepare_flickr_images_for_maze(maze, size, page, page_size)
        instagram = __prepare_instagram_images_for_maze(maze, size,
                                                        page, page_size)

        internal, flickr, instagram = yield internal, flickr, instagram
        image_list = internal + flickr + instagram
        memcache.set(cache_key, image_list, time=config.MEMCACHE_TIME)

    raise ndb.Return(image_list)
