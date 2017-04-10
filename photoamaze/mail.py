"""
    config
    ======

    Mail module. For various mails. No i18n. Maybe later.

    :copyright: 2017 David Volquartz Lebech
    :license: MIT, see LICENSE for details

"""
import logging

import webapp2
from google.appengine.api import mail

from photoamaze import config


class MailHandler(webapp2.RequestHandler):
    def post(self, *args, **kwargs):
        msg = mail.InboundEmailMessage(self.request.body)
        logging.info('Mail from: {}'.format(msg.sender))
        logging.info('Subject: {}'.format(msg.subject))
        for content_type, body in msg.bodies():
            logging.info(content_type)
            logging.info(body.decode())


def send_welcome(admin_email, maze_url, admin_url):
    body = """Hello,

Nice, you created a new maze. To change your maze settings, visit your admin
page:
{admin_url}
You should probably keep this link to yourself.

If you want to share your maze with friends, use this link:
{maze_url}

Enjoy!
Photo Amaze"""
    body = body.format(maze_url=maze_url,
                       admin_url=admin_url)
    mail.send_mail(config.EMAIL,
                   admin_email,
                   'Photo Amaze created',
                   body)
