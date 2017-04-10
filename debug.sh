#!/usr/bin/env bash

# Runs Photo Amaze in debug mode.
node_modules/.bin/gulp dev
node_modules/.bin/gulp watch &

python2 $(which dev_appserver.py) --clear_datastore yes --log_level=debug --show_mail_body=yes app.yaml
