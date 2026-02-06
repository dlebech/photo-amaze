"""
    models
    ========

    Contains all datastore and local models.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import secrets

from google.appengine.ext import ndb
from google.appengine.api import memcache
from werkzeug.security import generate_password_hash, check_password_hash

from photoamaze.config import PEPPER
from photoamaze.util import html_escape, ReadOnly


class LocalImage(object):
    def __init__(self, url, message, attribution='', external_url='',
                 license=''):
        self.url = url if isinstance(url, str) else str(url)
        self.message = message if isinstance(message, str) else str(message)
        self.attribution = attribution
        self.external_url = external_url
        self.license = license

    def __hash__(self):
        return hash(self.url + self.message)

    def __eq__(self, other):
        return self.url == other.url and self.message == other.message

    def to_dict(self):
        return {
            'url': self.url,
            'msg': self.message,
            'attrib': self.attribution,
            'eurl': self.external_url,
            'lic': self.license
        }


class MazeCacheKey(ReadOnly):
    flickr_user = '{}:flickr_user'
    image_list = '{}:imagelist'


class BaseModel(ndb.Model):
    created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
    modified = ndb.DateTimeProperty(auto_now=True, indexed=False)


class OAuthToken(BaseModel):
    """Represents an oauth token with a token key and secret."""
    secret = ndb.TextProperty()


class FlickrUserAccess(ndb.Model):
    """Represents a single user's access to Flickr. This is stored in a central
    location so it can be used in several different maze configurations.

    """
    access_token = ndb.TextProperty()
    access_token_secret = ndb.TextProperty()

    @classmethod
    def create_or_update(cls, user_id, access_token, access_token_secret):
        """Creates or updates Flickr access for the given user."""
        user_id = str(user_id)
        access = cls.get_or_insert(user_id)
        access.access_token = access_token
        access.access_token_secret = access_token_secret
        return access.put()

    @classmethod
    def get_by_user_id(cls, user_id):
        user_id = str(user_id)
        return cls.get_by_id(user_id)


class FlickrSettings(ndb.Model):
    """Represents Flickr settings for a specific maze."""
    user_access = ndb.KeyProperty(FlickrUserAccess)

    tags = ndb.TextProperty()
    user = ndb.TextProperty()

    # Whether or not to include user's own (recent) photos.
    include_recent = ndb.BooleanProperty(default=False)

    # Whether or not to include user's own favorites.
    include_favs = ndb.BooleanProperty(default=False)


class Maze(BaseModel):
    # Maze base settings.
    name = ndb.TextProperty()
    password = ndb.TextProperty()
    hash_method = ndb.TextProperty()
    salt = ndb.TextProperty()

    # Admin info
    admin_key = ndb.TextProperty(required=True)
    admin_email = ndb.StringProperty(required=True)

    # Flickr settings
    flickr = ndb.StructuredProperty(FlickrSettings, indexed=False)


    @property
    def name_encoded(self):
        if self.name:
            return html_escape(self.name)
        return ''

    @classmethod
    @ndb.transactional
    def create(cls, email, name='', password=''):
        """Creates a new maze with a unique string ID."""
        admin_key = secrets.token_urlsafe(32)

        # Make sure to avoid ID collisions.
        maze = True
        while maze:
            maze_id = secrets.token_urlsafe(32)
            maze = cls.get_by_id(maze_id)

        # Create the maze with the non-colliding Maze ID.
        maze = cls(id=maze_id,
                   name=name,
                   admin_email=email,
                   admin_key=admin_key)
        maze.set_password(password, save=False)
        maze.flickr = FlickrSettings()
        return maze.put()

    def set_password(self, password, save=True):
        if password:
            peppered = PEPPER + password if PEPPER else password
            h = generate_password_hash(peppered, method='pbkdf2:sha256')
            self.password = h
            self.hash_method = 'pbkdf2:sha256'
            self.salt = ''
            if save:
                self.put()

    def validate_password(self, password):
        if not self.password:
            return True
        peppered = PEPPER + password if PEPPER else password
        # Support legacy format from webapp2_extras.security
        if self.salt:
            legacy_hash = '$'.join([self.password, self.hash_method, self.salt])
            # Try werkzeug format first, fall back to legacy
            try:
                return check_password_hash(self.password, peppered)
            except Exception:
                return False
        return check_password_hash(self.password, peppered)

    def delete_cache(self):
        for cache_key in MazeCacheKey.values:
            memcache.delete(cache_key.format(self.key.id()))


class MazeImage(BaseModel):
    image_key = ndb.BlobKeyProperty(indexed=False)
    image = ndb.BlobProperty(indexed=False)
    message = ndb.TextProperty()
