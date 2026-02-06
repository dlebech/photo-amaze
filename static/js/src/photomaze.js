import * as THREE from 'three';
import Stats from 'stats.js';
import Maze from './maze';
import Player from './player';
import MiniMap from './minimap';

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
  if (wallGeometry === null) {
    wallGeometry = new THREE.PlaneGeometry(wallWidth, wallHeight);
  }

  const material = new THREE.MeshLambertMaterial({
    map: wallTexture,
    side: THREE.DoubleSide,
  });

  const wall = new THREE.Mesh(wallGeometry, material);

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
 * Creates a large sky dome with a zenith-to-horizon gradient.
 */
const createSkyDome = () => {
  const skyGeo = new THREE.SphereGeometry(5000, 32, 15);
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    uniforms: {},
    vertexShader: `
      varying vec3 vWorldPosition;
      void main() {
        vec4 worldPos = modelMatrix * vec4(position, 1.0);
        vWorldPosition = worldPos.xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vWorldPosition;
      void main() {
        float h = normalize(vWorldPosition).y;
        vec3 zenith = vec3(0.0, 0.467, 1.0);   // 0x0077ff
        vec3 horizon = vec3(0.667, 0.8, 1.0);   // 0xaaccff
        vec3 color = mix(horizon, zenith, max(h, 0.0));
        gl_FragColor = vec4(color, 1.0);
      }
    `,
  });

  const skyDome = new THREE.Mesh(skyGeo, skyMat);
  // Center dome over the maze floor
  const width = maze.mazeGrid.length * wallWidth;
  skyDome.position.set(
    (width / 2) - wallHalfWidth,
    0,
    (width / 2) - wallHalfWidth,
  );
  scene.add(skyDome);
};

/**
 * Creates visual markers at the maze exit: green floor tile, point light,
 * and two flanking posts.
 */
const createExitMarker = () => {
  const exitX = maze.exitCol * wallWidth;
  const exitZ = maze.exitRow * wallWidth;

  // Green floor tile slightly above the floor to avoid z-fighting
  const tileGeo = new THREE.PlaneGeometry(wallWidth * 0.9, wallWidth * 0.9);
  tileGeo.applyMatrix4(new THREE.Matrix4().makeRotationX(-Math.PI / 2));
  const tileMat = new THREE.MeshPhongMaterial({
    color: 0x00ff88,
    emissive: 0x00ff88,
    emissiveIntensity: 0.4,
  });
  const tile = new THREE.Mesh(tileGeo, tileMat);
  tile.position.set(exitX, -wallHalfHeight + 0.5, exitZ);
  scene.add(tile);

  // Green point light as a visible beacon
  const exitLight = new THREE.PointLight(0x00ff88, 1500, 200);
  exitLight.position.set(exitX, wallHalfHeight, exitZ);
  scene.add(exitLight);

  // Two small posts flanking the exit opening on the south edge
  const postGeo = new THREE.BoxGeometry(5, wallHeight, 5);
  const postMat = new THREE.MeshPhongMaterial({
    color: 0x00ff88,
    emissive: 0x00ff88,
    emissiveIntensity: 0.6,
  });

  const southZ = exitZ + wallHalfWidth;

  const postLeft = new THREE.Mesh(postGeo, postMat);
  postLeft.position.set(exitX - wallHalfWidth, 0, southZ);
  scene.add(postLeft);

  const postRight = new THREE.Mesh(postGeo, postMat);
  postRight.position.set(exitX + wallHalfWidth, 0, southZ);
  scene.add(postRight);
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
  const width = maze.mazeGrid.length * wallWidth;
  const geometry = new THREE.PlaneGeometry(width, width);
  geometry.applyMatrix4(new THREE.Matrix4().makeRotationX(-Math.PI / 2));

  const txt = textureLoader.load('/img/floor.jpg');
  txt.wrapS = THREE.RepeatWrapping;
  txt.wrapT = THREE.RepeatWrapping;
  txt.repeat.set(maze.mazeGrid.length, maze.mazeGrid.length);
  const material = new THREE.MeshPhongMaterial({ map: txt });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set((width / 2) - wallHalfWidth, -wallHalfHeight, (width / 2) - wallHalfWidth);
  scene.add(mesh);

  // Ambient light for uniform wall illumination
  scene.add(new THREE.AmbientLight(0xffffff, 2));

  // Fog fades distant walls into the sky color
  scene.fog = new THREE.FogExp2(0xaaccff, 0.0008);

  createSkyDome();
  createExitMarker();
};

const initScene = (renderAreaId) => {
  // Autostart clock.
  clock = new THREE.Clock(true);
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xaaccff);
  camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 10000);

  renderer = new THREE.WebGLRenderer();
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
  mesh.material.map = loadingTexture;

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

    // Update the wall.
    mesh.material.map = image.texture;
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
    return true;
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
    if (stats) {
      document.body.removeChild(stats.dom);
      stats = null;
      return;
    }

    stats = new Stats();
    stats.showPanel(0);

    // Align top-right
    stats.dom.style.position = 'fixed';
    stats.dom.style.right = '0px';
    stats.dom.style.top = '0px';
    document.body.appendChild(stats.dom);
  }

  /**
   * Start sets up the maze and begins rendering.
   */
  static start(renderAreaId, length, width) {
    if (animationId !== null) cancelAnimationFrame(animationId);

    // Initialize the basic scene elements.
    initScene(renderAreaId);

    // Create the maze.
    initMaze(length, width);

    // Animate!
    animate();
  }
}

export default PhotoMaze;
