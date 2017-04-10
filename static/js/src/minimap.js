class MiniMap {
  constructor(maze) {
    this.maze = maze;
    this.domElement = document.createElement('canvas');
    this.domElement.id = 'minimap';
    this.domElement.style.display = 'none';
    window.addEventListener('resize', () => {
      this.create();
    });
    this.create();
  }

  create() {
    // Minimap should be a 1/10 of the window size.
    this.size = Math.floor(window.innerWidth / 10);
    this.wallLength = this.size / this.maze.mazeGrid.length;

    // Set previous row variables used in the update function.
    this.curRow = 0;
    this.curCol = 0;

    // Set width of the canvas.
    this.domElement.width = this.size;
    this.domElement.height = this.size;

    // Get context
    const context = this.domElement.getContext('2d');

    // Draw map background
    context.fillStyle = 'white';
    context.fillRect(0, 0, this.size, this.size);
    context.strokeStyle = 'black';
    context.lineWidth = 1;

    for (let row = 0; row < this.maze.mazeGrid.length; row += 1) {
      const y = row * this.wallLength;

      for (let col = 0; col < this.maze.mazeGrid[row].length; col += 1) {
        const x = col * this.wallLength;

        // Determine east and south walls.
        const mazeWalls = this.maze.mazeGrid[row][col];

        // There is a wall to the south.
        if ((mazeWalls & this.maze.DIRECTIONS.S) === 0) {
          context.beginPath();
          context.moveTo(x, y + this.wallLength);
          context.lineTo(x + this.wallLength, y + this.wallLength);
          context.stroke();
        }

        // There is a wall to the east.
        if ((mazeWalls & this.maze.DIRECTIONS.E) === 0) {
          context.beginPath();
          context.moveTo(x + this.wallLength, y);
          context.lineTo(x + this.wallLength, y + this.wallLength);
          context.stroke();
        }
      }
    }

    // Draw the current position.
    this.drawPosition(this.curRow, this.curCol, 'blue', this.wallLength / 4);

    this.domElement.style.position = 'absolute';
    this.domElement.style.left = '0px';
    this.domElement.style.top = '0px';
  }

  update(curRow, curCol) {
    if (curRow === this.curRow && curCol === this.curCol) return;

    // Draw over previous position.
    this.drawPosition(this.curRow, this.curCol, 'white', this.wallLength / 3);

    this.curRow = curRow;
    this.curCol = curCol;

    // Draw new position.
    this.drawPosition(this.curRow, this.curCol, 'blue', this.wallLength / 4);
  }

  drawPosition(row, col, color, rad) {
    const context = this.domElement.getContext('2d');
    context.fillStyle = color;
    context.beginPath();
    const x = (col * this.wallLength) + (this.wallLength / 2);
    const y = (row * this.wallLength) + (this.wallLength / 2);
    context.arc(x, y, rad, 0, 2 * Math.PI);
    context.fill();
  }
}

module.exports = MiniMap;
