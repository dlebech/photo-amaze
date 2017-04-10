# photo-amaze

A 3D maze with walls made up of photos from Flickr or Instagram. Runs on Google
App Engine with THREE.js as graphics library.

View it [here](https://photo-amaze.appspot.com).

## License

MIT License

## Credits

*Stone wall* by [McKay Savage](https://www.flickr.com/photos/mckaysavage/7084755961). CC-BY license.
Used for the floors.

*Wall of Rust and Crust, Tucson* by [cobalt123](https://www.flickr.com/photos/cobalt/3292143183/). CC-BY-NC-SA license.
Used for the initial walls.

## Running it locally

First install `gcloud` tools. Then ideally it should be this simple:

    $ cp app_sample.yml app.yml
    $ npm install
    $ pip2 install -t lib -r requirements.txt
    $ ./debug.sh

## History

The project was initially made in 2014 for a wedding as a "selfie-maze", but
the code was never released on Github, because I started getting busy, and
didn't have time to clean it up.

Now, in 2017, I've updated it to use slightly fancier JS syntax and updated
some other deprecated code that didn't work anymore as well as move hardcoded
API secrets into environment variables. This explains why the commit history is
very short, because I didn't want to have secrets in the commit history, so the
project got a "fresh start" :-)
