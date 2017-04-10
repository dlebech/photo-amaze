/* global THREE */

class Utils {
  // http://stackoverflow.com/questions/14813902/three-js-get-the-direction-in-which-the-camera-is-looking
  static getCameraDirection(camera) {
    const vector = new THREE.Vector3(0, 0, -1);
    vector.applyQuaternion(camera.quaternion);
    return vector;
  }
}

/**
 * Represents a player. The player controls the given camera.
 */
class Player {
  constructor(scene, camera) {
    // Forward works both for keyboard and touch.
    // Back, left and right only works for keyboard.
    this.forward = { keyboard: false, touch: false };
    this.backward = false;
    this.right = false;
    this.left = false;
    this.fps = false;  // First-person-shooter mode :-)
    this.camera = camera;
    this.mouseX = 0;
    this.mouseY = 0;
    this.touchX = 0;
    this.touchY = 0;
    this.maxPitch = Math.PI / 6;

    // Set up the player controls.
    this.pitch = new THREE.Object3D();
    this.pitch.add(camera);

    this.yaw = new THREE.Object3D();
    this.yaw.add(this.pitch);
    scene.add(this.yaw);

    // Set up the player's light source.
    this.light = new THREE.PointLight(0xffffff, 2, 400);
    scene.add(this.light);

    // Set up the player's collision detector.
    this.caster = new THREE.Raycaster();

    // Set up a 90 degree rotation matrix for rotating the caster position.
    this.rotationMatrix = new THREE.Matrix4()
      .makeRotationAxis(new THREE.Vector3(0, 1, 0), -Math.PI / 2);

    // Register the player for events.
    const onResize = () => {
      this.viewHalfX = window.innerWidth / 2;
      this.viewQuarterX = this.viewHalfX / 2;
      this.viewHalfY = window.innerHeight / 2;
      this.viewQuarterY = this.viewHalfY / 2;
    };
    onResize(); // Trigger a resize.

    const onKeyDown = keyEvent => this.toggleMovement(keyEvent.keyCode, true);
    const onKeyUp = keyEvent => this.toggleMovement(keyEvent.keyCode, false);

    const onMouseMove = (e) => {
      this.mouseX = e.pageX - this.viewHalfX;
      this.mouseY = e.pageY - this.viewHalfY;
    };

    const registerTouchPosition = (touch) => {
      this.touchX = touch.pageX - this.viewHalfX;
      this.touchY = touch.pageY - this.viewHalfY;
    };

    const onTouchMove = (e) => {
      if (e.touches.length > 0) {
        registerTouchPosition(e.touches[0]);
      }
    };

    const onTouchStart = (e) => {
      if (e.touches.length > 0) {
        registerTouchPosition(e.touches[0]);
        this.forward.touch = true;
      }
    };

    const onTouchEnd = (e) => {
      if (e.touches.length === 0) {
        // Stop moving completely when not touching.
        this.forward.touch = false;
        this.touchX = 0;
        this.touchY = 0;
      }
    };

    window.addEventListener('resize', onResize);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('touchmove', onTouchMove);
    window.addEventListener('touchstart', onTouchStart);
    window.addEventListener('touchend', onTouchEnd);
  }

  toggleMovement(keyCode, directionBool) {
    switch (keyCode) {
      case 37:  // Left arrow
      case 65:  // a key
        this.left = directionBool;
        break;
      case 38:  // Up arrow
      case 87:  // w key
        this.forward.keyboard = directionBool;
        break;
      case 39:  // Right arrow
      case 68:  // d key
        this.right = directionBool;
        break;
      case 40:  // Down arrow
      case 83:  // s key
        this.backward = directionBool;
        break;
      default:
        break;
    }
  }

  toggleFPS() {
    this.fps = !this.fps;
    if (!this.fps) {  // Reset the pitch when FPS is turned off.
      this.pitch.rotation.x = 0;
    }
  }

  update(elapsed, obstacles) {
    const position = this.getPosition();
    const direction = this.getDirection();

    // Calculate movement.
    let deltaX = 0;
    let deltaZ = 0;

    // 1. Always rotate according to touch coordinates if they are present.
    // 2. If FPS is on, rotate according to mouse.
    // 3. If not touching and fps is not on, move according to the left and
    // right keys.
    if (this.touchX !== 0 || this.touchY !== 0) {
      this.yaw.rotation.y -= (this.touchX / this.viewHalfX) * 0.03;
      this.pitch.rotation.x -= (this.touchY / this.viewHalfY) * 0.03;
    } else if (this.fps) {
      this.yaw.rotation.y -= (this.mouseX / this.viewHalfX) * 0.03;
      this.pitch.rotation.x -= (this.mouseY / this.viewHalfY) * 0.03;
    } else if (this.left) {
      this.yaw.rotation.y += 0.03;
    } else if (this.right) {
      this.yaw.rotation.y -= 0.03;
    }

    this.pitch.rotation.x = Math.max(
      -this.maxPitch,
      Math.min(this.maxPitch, this.pitch.rotation.x));

    // Only move if touch position is less than halfway to the edge of
    // the screen and there are no collisions.
    // When using the keyboard, forward movement is always allowed.
    // Not a pretty if statement here :-)
    if (this.forward.keyboard ||
      (this.forward.touch &&
        Math.abs(this.touchX) < this.viewQuarterX &&
        Math.abs(this.touchY) < this.viewQuarterY)) {
      // Check forward collision.
      this.caster.set(position, direction);
      const collisions = this.caster.intersectObjects(obstacles);
      if (collisions.length === 0 || collisions[0].distance > 40) {
        deltaZ = -100 * elapsed;
        this.yaw.translateZ(deltaZ);
        this.light.position.set(this.yaw.position.x, this.yaw.position.y, this.yaw.position.z);
      }
    }

    // Rotate direction 90 degrees
    direction.applyMatrix4(this.rotationMatrix);

    if (this.right && this.fps) {
      this.caster.set(position, direction);
      const collisions = this.caster.intersectObjects(obstacles);
      if (collisions.length === 0 || collisions[0].distance > 40) {
        deltaX = 100 * elapsed;
      }
    }

    direction.applyMatrix4(this.rotationMatrix);

    if (this.backward) {
      this.caster.set(position, direction);
      const collisions = this.caster.intersectObjects(obstacles);
      if (collisions.length === 0 || collisions[0].distance > 40) {
        deltaZ = 100 * elapsed;
      }
    }

    direction.applyMatrix4(this.rotationMatrix);

    if (this.left && this.fps) {
      this.caster.set(position, direction);
      const collisions = this.caster.intersectObjects(obstacles);
      if (collisions.length === 0 || collisions[0].distance > 40) {
        deltaX = -100 * elapsed;
      }
    }

    if (deltaZ !== 0 || deltaX !== 0) {
      this.yaw.translateZ(deltaZ);
      this.yaw.translateX(deltaX);
      this.light.position.set(this.yaw.position.x, this.yaw.position.y, this.yaw.position.z);
    }
  }


  getPosition() {
    return this.yaw.position;
  }

  getDirection() {
    return Utils.getCameraDirection(this.yaw);
  }
}

module.exports = Player;
