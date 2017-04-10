/* global THREE, Stats */

const Maze = require('./maze');
const Player = require('./player');
const MiniMap = require('./minimap');

/**
 * @author alteredq / http://alteredqualia.com/
 * @author mr.doob / http://mrdoob.com/
 */
class Detector {
  static get canvas() {
    return !!window.CanvasRenderingContext2D;
  }

  static get webgl() {
    try {
      const canvas = document.createElement('canvas');
      return window.WebGLRenderingContext &&
        (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
    } catch (e) {
      return false;
    }
  }

  static get workers() {
    return !!window.Worker;
  }

  static get fileapi() {
    return window.File && window.FileReader && window.FileList && window.Blob;
  }
}

// Representation of the maze and minimap.
let maze = null;
let minimap = null;

// A list of 3D walls.
let walls = null;

// Re-usable wall geometry.
let wallGeometry = null;

// Animation ID for stopping animation
let animationId = null;

// Wall setup, private so they cannot be changed.
const wallWidth = 100;
const wallHalfWidth = wallWidth / 2;
const wallHeight = 100;
const wallHalfHeight = wallHeight / 2;

// Renderer, scene, camera, clock and stats are available within the scope
// of this closure.
let renderer = null;
let scene = null;
let camera = null;
let clock = null;
let stats = null;

// The player.
let player = null;

// Player row/col position for convenience.
let curRow = 0;
let curCol = 0;

// Whether or not the current maze is enabled.
let enabled = false;

let usingWebGL = true;

// Image loader and loading texture placeholder.
const imgLoader = new THREE.ImageLoader();
const textureLoader = new THREE.TextureLoader();
const wallTexture = textureLoader.load('/img/wall.jpg');
wallTexture.minFilter = THREE.LinearFilter;
const loadingTexture = textureLoader.load('/img/loading.jpg');
loadingTexture.minFilter = THREE.LinearFilter;

/**
 * Creates a single wall at the given coordinates.
 */
const createWall = (x, z, direction) => {
  // Reuse the same plane geometry for the walls.
  // The walls actually consist of two planes that are merged together.
  // This is done so textures can be added to each side without the
  // texture being inverted.
  if (wallGeometry === null) {
    // Create two planes.
    let geometry;
    let geometry2;

    if (usingWebGL) {
      geometry = new THREE.PlaneGeometry(wallWidth, wallHeight);
      geometry2 = new THREE.PlaneGeometry(wallWidth, wallHeight);
    } else {
      // If webgl is not present, use more wall segments.
      geometry = new THREE.PlaneGeometry(wallWidth, wallHeight, 4, 4);
      geometry2 = new THREE.PlaneGeometry(wallWidth, wallHeight, 4, 4);
    }

    // Rotate the second plane and merge the planes together.
    geometry2.applyMatrix(new THREE.Matrix4().makeRotationY(Math.PI));
    geometry.merge(geometry2);

    // Set the material index to be different on each side.
    // A plane geometry has two faces.
    // XXX: Can we be sure about that forever?
    geometry.faces[0].materialIndex = 0;
    geometry.faces[1].materialIndex = 0;
    geometry.faces[2].materialIndex = 1;
    geometry.faces[3].materialIndex = 1;

    wallGeometry = geometry;
  }

  // Create a material for each side of the wall.
  const material1 = new THREE.MeshLambertMaterial({ map: wallTexture });
  const material2 = new THREE.MeshLambertMaterial({ map: wallTexture });
  if (!usingWebGL) {
    material1.overdraw = true;
    material2.overdraw = true;
  }
  const materials = [material1, material2];

  const wall = new THREE.Mesh(wallGeometry, new THREE.MultiMaterial(materials));

  switch (direction) {
    case maze.DIRECTIONS.N:
      // Plane geometry is already aligned with the xy plane so for
      // north/south walls it just needs to be moved. A little bit is
      // added to the z-position to move it to the edge of the maze
      // cell.
      wall.position.x = x;
      wall.position.z = z - wallHalfWidth;
      break;
    case maze.DIRECTIONS.S:
      wall.position.x = x;
      wall.position.z = z + wallHalfWidth;
      break;
    case maze.DIRECTIONS.E:
      // Rotate east and west surfaces 90 degrees.
      // The walls are doublesided so it doesn't matter which way
      // they are rotated.
      wall.rotation.y = Math.PI / 2;
      wall.position.z = z;
      wall.position.x = x + wallHalfWidth;
      break;
    case maze.DIRECTIONS.W:
      wall.rotation.y = Math.PI / 2;
      wall.position.z = z;
      wall.position.x = x - wallHalfWidth;
      break;
    default:
      break;
  }

  return wall;
};

/**
 * Creates all the walls for the maze.
 */
const createWalls = () => {
  // Reset the walls.
  walls = [];

  for (let row = 0; row < maze.mazeGrid.length; row += 1) {
    const z = row * wallWidth;
    walls[row] = [];

    for (let col = 0; col < maze.mazeGrid[row].length; col += 1) {
      const x = col * wallWidth;
      walls[row][col] = [];

      // If first row, place north wall.
      if (row === 0) {
        walls[row][col].push(
          createWall(x, z, maze.DIRECTIONS.N));
      }

      // If first column, place west wall
      if (col === 0) {
        walls[row][col].push(
          createWall(x, z, maze.DIRECTIONS.W));
      }

      // Determine east and south walls.
      const mazeWalls = maze.mazeGrid[row][col];

      // There is a wall to the south.
      if ((mazeWalls & maze.DIRECTIONS.S) === 0) {
        walls[row][col].push(
          createWall(x, z, maze.DIRECTIONS.S));
      }

      // There is a wall to the east.
      if ((mazeWalls & maze.DIRECTIONS.E) === 0) {
        walls[row][col].push(
          createWall(x, z, maze.DIRECTIONS.E));
      }
    }
  }
};

/**
 * Create a first-person player for the maze. The player controls the
 * camera of the scene.
 */
const createPlayer = () => {
  // Camera starts in "top-left" corner of maze (x, y, z) = (0, 0, 0)
  camera.position.set(0, 0, 0);

  // Initialize the player to control the camera.
  player = new Player(scene, camera);

  // The camera should be rotated to point in the direction of the first
  // open wall at the starting position. This will be either East (along
  // the positive x-axis) or South (along the positive z-axis).
  if ((maze.mazeGrid[0][0] & maze.DIRECTIONS.S) !== 0) {
    // South is open, rotate 180 degrees.
    player.yaw.rotation.y = Math.PI;
  } else {
    // East is open, rotate 90 degrees.
    player.yaw.rotation.y = -Math.PI / 2;
  }
};

const getObstacles = () => {
  const row = curRow;
  const col = curCol;

  const obstacles = [];
  if (row >= 0 && row < maze.mazeGrid.length && col >= 0 && col < maze.mazeGrid[0].length) {
    // Obstacles from this room.
    obstacles.push(...walls[row][col]);

    // Obstacles to the north
    if (row - 1 >= 0) {
      obstacles.push(...walls[row - 1][col]);

      // Northwest
      if (col - 1 >= 0) obstacles.push(...walls[row - 1][col - 1]);

      // Northeast
      if (col + 1 < maze.mazeGrid[0].length) obstacles.push(...walls[row - 1][col + 1]);
    }

    // Obstacles to the south
    if (row + 1 < walls.length) {
      obstacles.push(...walls[row + 1][col]);

      // Southwest
      if (col - 1 >= 0) obstacles.push(...walls[row + 1][col - 1]);

      // Southeast
      if (col + 1 < maze.mazeGrid[0].length) obstacles.push(...walls[row + 1][col + 1]);
    }

    // Obstacles to the west.
    if (col - 1 >= 0) obstacles.push(...walls[row][col - 1]);

    // Obstacles to the east.
    if (col + 1 < maze.mazeGrid[0].length) obstacles.push(...walls[row][col + 1]);
  }

  return obstacles;
};

const updateMaze = (elapsed) => {
  if (enabled) {
    // Update the player view.
    player.update(elapsed, getObstacles());

    // Save the current row/col position.
    const curPos = player.getPosition();
    curRow = Math.round(curPos.z / wallWidth);
    curCol = Math.round(curPos.x / wallWidth);

    // Update minimap.
    if (minimap !== null) {
      minimap.update(curRow, curCol);
    }
  }
};

/**
 * Initializes a 3D version of the maze, including a player-controllable
 * character.
 */
const init3DMaze = () => {
  // Create walls and player
  createWalls();
  createPlayer(scene, camera);

  // Add all the walls.
  for (let i = 0; i < walls.length; i += 1) {
    for (let j = 0; j < walls[i].length; j += 1) {
      for (let k = 0; k < walls[i][j].length; k += 1) {
        scene.add(walls[i][j][k]);
      }
    }
  }

  // Create and add floor
  if (usingWebGL) {
    const width = maze.mazeGrid.length * wallWidth;
    const geometry = new THREE.PlaneGeometry(width, width);
    geometry.applyMatrix(new THREE.Matrix4().makeRotationX(-Math.PI / 2));

    const txt = textureLoader.load('/img/floor.jpg');
    txt.wrapS = THREE.RepeatWrapping;
    txt.wrapT = THREE.RepeatWrapping;
    txt.repeat.set(maze.mazeGrid.length, maze.mazeGrid.length);
    const material = new THREE.MeshPhongMaterial({ map: txt });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set((width / 2) - wallHalfWidth, -wallHalfHeight, (width / 2) - wallHalfWidth);
    scene.add(mesh);
  }
};

const initScene = (renderAreaId) => {
  // Autostart clock.
  clock = new THREE.Clock(true);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 500);

  if (usingWebGL) renderer = new THREE.WebGLRenderer();
  else renderer = new THREE.CanvasRenderer();
  renderer.setSize(window.innerWidth, window.innerHeight);

  const renderarea = document.getElementById(renderAreaId);
  if (renderarea.hasChildNodes()) renderarea.removeChild(renderarea.childNodes[0]);
  renderarea.appendChild(renderer.domElement);

  // Setup resizing of viewport.
  const handleResize = () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.far = 10000;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  };
  window.addEventListener('resize', handleResize);
};

const initMaze = (length, width) => {
  maze = new Maze(length, width);
  init3DMaze();
  minimap = new MiniMap(maze);
  document.body.appendChild(minimap.domElement);
};

// Render puts everything on the screen.
const render = () => {
  renderer.render(scene, camera);
};

// Animate makes sure that dynamic elements are updated.
const animate = () => {
  const elapsed = clock.getDelta();

  updateMaze(elapsed);

  animationId = requestAnimationFrame(animate);
  render();

  if (stats) stats.update();
};

/**
 * Asynchronously load an image and add it to the given wall.
 * It is assumed that image is a JS object with a 'url' attribute.
 */
const addImageToWall = (image, mesh) => {
  // Add loading wall
  mesh.material.materials[0].map = loadingTexture;
  mesh.material.materials[1].map = loadingTexture;

  // Start loading the image.
  imgLoader.load(image.url, (img) => {
    // Check to see if the image already has a texture set. This could
    // have hapened in a different context and there is no need to draw
    // it again.
    if (!(image.texture instanceof THREE.Texture)) {
      // The size of the texture is the longest side of the image.
      const size = Math.max(img.width, img.height);

      // Create canvas
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;

      // Get context
      const context = canvas.getContext('2d');

      // Draw wall background
      context.fillStyle = 'black';
      context.fillRect(0, 0, size, size);

      const offsetX = (size - img.width) / 2;
      const offsetY = (size - img.height) / 2;

      // Draw image. Offset based on the shortest side.
      context.drawImage(img, offsetX, offsetY);

      if (image.msg.length > 0) {
        // Maximum width with 5% padding if needed.
        const maxWidth = size - (size * 0.05);

        // Setup font and fill style.
        context.save();
        context.fillStyle = 'white';
        context.strokeStyle = 'black';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.lineWidth = 2;

        if (img.width < img.height) {
          context.font = `${offsetX / 2}px sans-serif`;
          context.translate(0, size);
          context.rotate(-Math.PI / 2);
          context.fillText(image.msg, size / 2, offsetX / 2, maxWidth);
        } else {
          context.font = `${offsetY / 2}px sans-serif`;
          context.fillText(image.msg, size / 2, size - (offsetY / 2), maxWidth);
        }
        context.restore();
      }

      // Create the texture.
      image.texture = new THREE.Texture(canvas);
      image.texture.minFilter = THREE.LinearFilter;
      image.texture.needsUpdate = true;
    }

    // Update the wall on both sides.
    mesh.material.materials[0].map = image.texture;
    mesh.material.materials[1].map = image.texture;
  });
};

class PhotoMaze {
  /**
   * Loads the given images onto the walls of the maze.
   * The images should be given as an array of JS objects that have url and msg attributes.
   */
  static loadImages(images) {
    if (images.length === 0 || walls === null) return;

    for (let i = 0; i < walls.length; i += 1) {
      for (let j = 0; j < walls[i].length; j += 1) {
        for (let k = 0; k < walls[i][j].length; k += 1) {
          const wall = walls[i][j][k];

          // Select a random image and add it to the wall.
          const image = images[Math.floor(Math.random() * images.length)];
          addImageToWall(image, wall);
        }
      }
    }
  }

  /**
   * Return a boolean indicating whether the WebGL renderer is used or not.
   */
  static isWebGL() {
    return usingWebGL;
  }

  /**
   * Enable the maze.
   */
  static enable() {
    enabled = true;
  }

  /**
   * Disable the maze.
   */
  static disable() {
    enabled = false;
  }

  /**
   * Toggle whether or not the maze is enabled.
   */
  static toggle() {
    enabled = !enabled;
  }

  static toggleMouse() {
    player.toggleFPS();
  }

  static toggleStats() {
    // Stats for WebGL.
    if (stats) {
      document.body.removeChild(stats.domElement);
      stats.end();
      stats = null;
      return;
    }

    stats = new Stats();
    stats.setMode(0);

    // Align top-right
    stats.domElement.style.position = 'fixed';
    stats.domElement.style.right = '0px';
    stats.domElement.style.top = '0px';
    document.body.appendChild(stats.domElement);
  }

  /**
   * Start sets up the maze and begins rendering.
   */
  static start(renderAreaId, length, width) {
    // Determine whether or not to use webgl.
    usingWebGL = Detector.webgl;

    if (animationId !== null) cancelAnimationFrame(animationId);

    // Initialize the basic scene elements.
    initScene(renderAreaId);

    // Create the maze.
    // Webgl, ok for any length/width (almost)
    if (usingWebGL) initMaze(length, width);
    // Not WebGL, limit to 4 by 4.
    else initMaze(4, 4);

    // Animate!
    animate();
  }
}

module.exports = PhotoMaze;
