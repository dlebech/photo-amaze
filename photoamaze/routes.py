"""
    routes
    ======

    All the routes for Photo Amaze.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import webapp2
from webapp2_extras.routes import (PathPrefixRoute, RedirectRoute,
                                   HandlerPrefixRoute)


# Routes
routes = [
    HandlerPrefixRoute('photoamaze.handlers.', [
        webapp2.Route('/', handler='LandingHandler', name='landing'),
        webapp2.Route('/credits', handler='CreditsHandler', name='credits'),
        webapp2.Route('/privacy', handler='PrivacyHandler', name='privacy'),
        webapp2.Route('/terms', handler='TermsHandler', name='terms'),

        # Public maze endpoints.
        PathPrefixRoute('/public', [
            webapp2.Route('/maze', name='public-maze',
                          handler='PublicMazeHandler'),
            webapp2.Route('/image/list', name='public-image-list',
                          handler='PublicImageListHandler'),
            webapp2.Route(r'/image/<image_id:.+>', name='public-image',
                          handler='PublicImageHandler')
        ]),

        # Instagram auth
        PathPrefixRoute('/auth', [
            webapp2.Route('/instagram', name='auth-instagram',
                          handler='AuthInstagramHandler'),
            webapp2.Route('/flickr', name='auth-flickr',
                          handler='AuthFlickrHandler'),
            webapp2.Route('/facebook', name='auth-facebook',
                          handler='AuthFacebookHandler'),
        ]),


        # Private maze endpoints.
        RedirectRoute(r'/maze/<maze_id:\w+>', name='maze',
                      handler='MazeHandler', strict_slash=True),
        PathPrefixRoute(r'/maze/<maze_id:\w+>', [
            webapp2.Route('/login', name='maze-login',
                          handler='MazeLoginHandler'),
            webapp2.Route('/texture/<image_key>', name='maze-texture',
                          handler='MazeTextureHandler'),
            PathPrefixRoute('/image', [
                webapp2.Route('/list', name='maze-image-list',
                              handler='MazeImageListHandler'),
            ]),
            webapp2.Route('/admin/<admin_key>', name='maze-admin',
                          handler='MazeAdminHandler'),
            PathPrefixRoute('/admin/<admin_key>', [
                webapp2.Route('/settings', name='maze-admin-settings',
                              handler='MazeAdminSettingsHandler'),
                webapp2.Route('/password', name='maze-admin-password',
                              handler='MazeAdminPasswordHandler'),
                webapp2.Route('/instagram', name='maze-admin-instagram',
                              handler='MazeAdminInstagramHandler'),
                webapp2.Route('/flickr', name='maze-admin-flickr',
                              handler='MazeAdminFlickrHandler'),
                webapp2.Route('/facebook', name='maze-admin-facebook',
                              handler='MazeAdminFacebookHandler'),
                PathPrefixRoute('/connect', [
                    webapp2.Route('/instagram',
                                  name='maze-admin-connect-instagram',
                                  handler='MazeAdminConnectInstagramHandler'),
                    webapp2.Route('/flickr',
                                  name='maze-admin-connect-flickr',
                                  handler='MazeAdminConnectFlickrHandler'),
                    webapp2.Route('/facebook',
                                  name='maze-admin-connect-facebook',
                                  handler='MazeAdminConnectFacebookHandler'),
                ])
            ])  # end admin path prefix
        ]),  # end maze path prefix
    ]),  # end hander prefix

    # Incoming mail handler
    webapp2.Route('/_ah/mail/<address>', name='mail',
                  handler='photoamaze.mail.MailHandler')
]
