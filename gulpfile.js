'use strict';

const del = require('del'),
  gulp = require('gulp'),
  cleanCSS = require('gulp-clean-css'),
  less = require('gulp-less'),
  named = require('vinyl-named'),
  webpack = require('webpack'),
  webpackStream = require('webpack-stream');

const JS_SRC = 'static/js/src/';
const JS_DIST = 'static/js/dist/';
const CSS_SRC = 'static/css/src/';
const CSS_DIST = 'static/css/dist/';

// Cleans up the dist folders.
gulp.task('clean', () => del([CSS_DIST, JS_DIST]));

// Copies library files.
gulp.task('libs', () => {
  return gulp.src(JS_SRC + 'libs/*.js')
    .pipe(gulp.dest(JS_DIST + 'libs/'));
});

gulp.task('css-dev', () => {
  return gulp.src(CSS_SRC + '*.less', { sourcemaps: true })
    .pipe(less())
    .pipe(gulp.dest(CSS_DIST));
});

gulp.task('css-dist', () => {
  return gulp.src(CSS_SRC + '*.less', { sourcemaps: true })
    .pipe(less())
    .pipe(cleanCSS())
    .pipe(gulp.dest(CSS_DIST));
});

const webpackConfig = {
  devtool: 'source-map',
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            cacheDirectory: true,
            presets: [
              [
                'env',
                {
                  targets: {
                    browsers: ["ie >= 11"]
                  },
                  modules: false
                }
              ]
            ]
          }
        }
      }
    ]
  },
  plugins: [
    new webpack.optimize.UglifyJsPlugin({
      sourceMap: true
    })
  ]
};

gulp.task('js', () => {
  return gulp.src(JS_SRC + '*.js')
    .pipe(named())
    .pipe(webpackStream(webpackConfig, webpack))
    .on('error', function(err) {
      console.error(err);
      this.emit('end');
    })
    .pipe(gulp.dest(JS_DIST));
});

gulp.task('dev', gulp.series('clean', gulp.parallel('libs', 'css-dev', 'js')));
gulp.task('dist', gulp.series('clean', gulp.parallel('libs', 'css-dist', 'js')));

gulp.task('default', gulp.series('dist'))

gulp.task('watch', () => {
  // Watch css and libs
  gulp.watch(CSS_SRC + '*.less', gulp.series('css-dev'));
  gulp.watch(CSS_SRC + 'libs/*.css', gulp.series('libs'));

  // Watch js and libs
  gulp.watch(JS_SRC + '*.js', gulp.series('js'));
  gulp.watch(JS_SRC + 'libs/*.js', gulp.series('libs'));
});
