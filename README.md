# photo-amaze

A 3D maze with walls made up of photos from Flickr. Runs on Google
App Engine (Python 3) with THREE.js as graphics library.

View it [here](https://photo-amaze.appspot.com).

## License

MIT License

## Credits

*Stone wall* by [McKay Savage](https://www.flickr.com/photos/mckaysavage/7084755961). CC-BY license.
Used for the floors.

*Wall of Rust and Crust, Tucson* by [cobalt123](https://www.flickr.com/photos/cobalt/3292143183/). CC-BY-NC-SA license.
Used for the initial walls.

## Running it locally

First install `gcloud` tools and Node.js. Then:

    $ cp app_sample.yaml app.yaml
    $ python -m venv venv && source venv/bin/activate
    $ pip install -r requirements.txt
    $ npm install
    $ npm run build
    $ python main.py

## History

The project was initially made in 2014 for a wedding as a "selfie-maze", but
the code was never released on Github, because I started getting busy, and
didn't have time to clean it up.

In 2017, it was updated to use slightly fancier JS syntax and updated
some other deprecated code, as well as move hardcoded API secrets into
environment variables.

In 2026, it was migrated from Python 2.7/webapp2 to Python 3/Flask,
the build pipeline was updated from gulp/webpack to Vite, and dead
Instagram/Facebook integrations were removed.
