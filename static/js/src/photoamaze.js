const PhotoMaze = require('./photomaze');

// Initially empty image list.
let images = [];

// Loads images from the given url.
const loadImages = (url, obj) => {
  const req = new XMLHttpRequest();
  let qs = '';
  Object.keys(obj).forEach((k) => {
    if (qs === '') qs = '?';
    else qs += '&';
    qs += `${k}=${obj[k]}`;
  });
  url += qs;
  req.open('GET', url, true);
  req.onload = function () {
    if (this.status >= 200 && this.status < 400) {
      const data = JSON.parse(this.response);
      images = data;
      PhotoMaze.loadImages(data);
    }
  };
  req.send();
};

// Fills the attribution list.
const fillAttribList = () => {
  const copy = document.getElementById('copyright-list');
  if (copy.hasChildNodes()) copy.removeChild(copy.childNodes[0]);

  for (let i = 0; i < images.length; i += 1) {
    const img = images[i];
    const elem = document.createElement('p');
    if (img.attrib) {
      const attrib = document.createElement('span');
      attrib.textContent = img.attrib;
      if (img.eurl) {
        const link = document.createElement('a');
        link.href = img.eurl;
        link.rel = 'nofollow';
        link.target = '_blank';
        link.appendChild(attrib);
        elem.appendChild(link);
      } else {
        elem.appendChild(attrib);
      }
    }
    copy.appendChild(elem);
  }
};

// Shows the overlay
const overlay = (controls, sharing, copyright) => {
  PhotoMaze.disable();

  if (controls) document.getElementById('controls').style.display = '';
  else document.getElementById('controls').style.display = 'none';

  if (window.enableSharing) {
    if (sharing) document.getElementById('sharing').style.display = '';
    else document.getElementById('sharing').style.display = 'none';
  }

  if (copyright) document.getElementById('copyright').style.display = '';
  else document.getElementById('copyright').style.display = 'none';

  document.getElementById('overlay').style.display = '';
};

document.addEventListener('DOMContentLoaded', () => {
  // Start the maze with a 10 by 10 grid.
  PhotoMaze.start('render-area', 10, 10);

  // Load image textures
  loadImages(window.imagesUrl, window.imagesParams);

  // Add WebGL warning, if necessary.
  if (!PhotoMaze.isWebGL()) {
    document.getElementById('webgl-warning').style.display = '';
  }

  // Add click/touch event for the start button so the overlay can be hidden.
  let elem = document.getElementById('start');
  let ev = (e) => {
    if (e) e.stopPropagation();
    document.getElementById('overlay').style.display = 'none';
    PhotoMaze.enable();
  };
  elem.addEventListener('click', ev);
  elem.addEventListener('touchstart', ev);

  document.getElementById('toggle-mouse').addEventListener('click', function () {
    if (this.textContent === 'Enable mouse') this.textContent = 'Disable mouse';
    else this.textContent = 'Enable mouse';
    PhotoMaze.toggleMouse();
  });

  // Show overlay on escape key.
  window.addEventListener('keydown', (e) => {
    if (e.keyCode === 27) {
      overlay(true, true, false);
    }
  });

  const preventEvent = (e) => {
    if (!e) return;
    e.preventDefault();
    e.stopPropagation();
  };

  // Set up the menu items.
  const elems = document.querySelectorAll('[data-url]');
  ev = function (e) {
    preventEvent(e);
    window.location.href = this.dataset.url;
  };
  for (let i = 0; i < elems.length; i += 1) {
    elems[i].addEventListener('click', ev);
    elems[i].addEventListener('touchstart', ev);
  }

  ev = (e) => {
    preventEvent(e);
    PhotoMaze.toggleStats();
  };
  document.getElementById('settings-stats').addEventListener('click', ev);
  document.getElementById('settings-stats').addEventListener('touchstart', ev);

  ev = (e) => {
    preventEvent(e);
    elem = document.getElementById('minimap');
    if (elem.style.display === '') elem.style.display = 'none';
    else elem.style.display = '';
  };
  document.getElementById('settings-minimap').addEventListener('click', ev);
  document.getElementById('settings-minimap').addEventListener('touchstart', ev);

  if (window.enableSharing) {
    ev = () => overlay(false, true, false);
    document.getElementById('settings-share').addEventListener('click', ev);
    document.getElementById('settings-share').addEventListener('touchstart', ev);
  }

  ev = () => overlay(true, false, false);
  document.getElementById('settings-controls').addEventListener('click', ev);
  document.getElementById('settings-controls').addEventListener('touchstart', ev);

  ev = () => {
    fillAttribList();
    overlay(false, false, true);
  };
  document.getElementById('settings-copyright').addEventListener('click', ev);
  document.getElementById('settings-copyright').addEventListener('touchstart', ev);

  ev = (e) => {
    preventEvent(e);
    elem = document.getElementById('menu-items');
    if (elem.style.display === '') elem.style.display = 'none';
    else elem.style.display = '';
  };
  document.getElementById('settings-link').addEventListener('click', ev);
  document.getElementById('settings-link').addEventListener('touchstart', ev);
});
