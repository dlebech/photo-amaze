"""
    util
    ====

    Utility library.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import json
from xml.sax import saxutils


class Bunch(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def to_json(self):
        return json.dumps(self.__dict__)


class _ReadOnlyMetaClass(type):
    """A metaclass for creating read-only subclasses."""
    def __setattr__(self, name, value):
        raise ValueError('This class is read-only')

    @property
    def values(self):
        """Return all defined values for this class."""
        return self.__dict__.values()

    def __str__(self):
        """Return the name of the class."""
        return self.__name__.lower()


class ReadOnly(object):
    """A class where all class attributes are read-only."""
    __metaclass__ = _ReadOnlyMetaClass


_html_escape_table = {
    '"': '&quot;',
    "'": '&#39;'
}


def html_escape(text):
    """Escapes certain html reserved characters in the given text."""
    return saxutils.escape(text, _html_escape_table)


def html_status():
    return Bunch(error={}, success={}, info={})
