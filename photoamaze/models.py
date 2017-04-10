"""
    models
    ========

    Contains all datastore and local models.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
from google.appengine.ext import ndb
from google.appengine.api import memcache
from webapp2_extras import security

from photoamaze.config import PEPPER
from photoamaze.util import html_escape, ReadOnly


class LocalImage(object):
    def __init__(self, url, message, attribution='', external_url='',
                 license=''):
        self.url = url if isinstance(url, basestring) else str(url)
        self.message = message if isinstance(message,
                                             basestring) else str(message)
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
    instagram_user = '{}:instagram_user'
    flickr_user = '{}:flickr_user'
    facebook_user = '{}:facebook_user'
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


class OAuthUserAccess(ndb.Model):
    """Represents a single user's oauth access to some service."""
    access_token = ndb.TextProperty()

    @classmethod
    def create_or_update(cls, user_id, access_token):
        """Creates or updates Instagram access for the given user."""
        user_id = str(user_id)
        access = cls.get_or_insert(user_id)
        access.access_token = access_token
        return access.put()

    @classmethod
    def get_by_user_id(cls, user_id):
        user_id = str(user_id)
        return cls.get_by_id(user_id)


class InstagramUserAccess(OAuthUserAccess):
    """Represents a single user's access to Instagram. This is stored in a
    central location so it can be used in several different maze configurations.

    """
    pass


class FacebookUserAccess(OAuthUserAccess):
    """Represents a single user's access to Facebook. This is stored in a
    central location so it can be used in several different maze configurations.

    """
    pass


class FlickrSettings(ndb.Model):
    """Represents Flickr settings for a specific maze."""
    user_access = ndb.KeyProperty(FlickrUserAccess)

    tags = ndb.TextProperty()
    user = ndb.TextProperty()

    # Whether or not to include user's own (recent) photos.
    include_recent = ndb.BooleanProperty(default=False)

    # Whether or not to include user's own favorites.
    include_favs = ndb.BooleanProperty(default=False)


class InstagramSettings(ndb.Model):
    """Represents Instagram settings for a specific maze."""
    user_access = ndb.KeyProperty(InstagramUserAccess)

    tag = ndb.TextProperty()

    # Whether or not to include the user's activity feed
    include_feed = ndb.BooleanProperty(default=False)

    # Whether or not to include the user's recent media
    include_recent = ndb.BooleanProperty(default=False)


class FacebookSettings(ndb.Model):
    user_access = ndb.KeyProperty(FacebookUserAccess)

    include_photos_of_you = ndb.BooleanProperty(default=False)


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

    # Instragram settings
    instagram = ndb.StructuredProperty(InstagramSettings, indexed=False)

    # Facebook settings
    facebook = ndb.StructuredProperty(FacebookSettings, indexed=False)

    # Whether or not to show share buttons on the photo maze.
    enable_sharing = ndb.BooleanProperty(default=False, indexed=False)

    @property
    def name_encoded(self):
        if self.name:
            return html_escape(self.name)
        return ''

    @classmethod
    @ndb.transactional
    def create(cls, email, name='', password=''):
        """Creates a new maze with a unique string ID."""
        admin_key = security.generate_random_string(entropy=128)

        # Make sure to avoid ID collisions.
        maze = True
        while maze:
            maze_id = security.generate_random_string(entropy=128)
            maze = cls.get_by_id(maze_id)

        # Create the maze with the non-colliding Maze ID.
        maze = cls(id=maze_id,
                   name=name,
                   admin_email=email,
                   admin_key=admin_key)
        maze.set_password(password, save=False)
        maze.flickr = FlickrSettings()
        maze.instagram = InstagramSettings()
        maze.facebook = FacebookSettings()
        return maze.put()

    def set_password(self, password, save=True):
        if password:
            h = security.generate_password_hash(password,
                                                method='sha512',
                                                length=64,
                                                pepper=PEPPER)
            hashval, method, salt = h.split('$')
            self.password = hashval
            self.hash_method = method
            self.salt = salt
            if save:
                self.put()

    def validate_password(self, password):
        if not self.password:
            return True
        pwhash = '$'.join([self.password, self.hash_method, self.salt])
        return security.check_password_hash(password, pwhash, pepper=PEPPER)

    def delete_cache(self):
        for cache_key in MazeCacheKey.values:
            memcache.delete(cache_key.format(self.key.id()))


class MazeImage(BaseModel):
    image_key = ndb.BlobKeyProperty(indexed=False)
    image = ndb.BlobProperty(indexed=False)
    message = ndb.TextProperty()
