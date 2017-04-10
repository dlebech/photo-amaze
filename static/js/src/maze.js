/**
 * A 2D maze representation.
 */
class Maze {
  constructor(rows, cols) {
    // Initialize an empty maze field.
    this.mazeGrid = [];
    for (let row = 0; row < rows; row += 1) {
      this.mazeGrid[row] = [];
      for (let col = 0; col < cols; col += 1) {
        this.mazeGrid[row][col] = 0;
      }
    }

    // Maze generation algorithm adapted from Ruby implementation by Jamis
    // Buck:
    // http://weblog.jamisbuck.org/2010/12/27/maze-generation-recursive-backtracking
    // Creative Common license (by-nc-sa 2.5).

    // Setup some variables to make it easier to traverse the maze.
    this.DIRECTIONS = {
      N: 1,
      S: 2,
      E: 4,
      W: 8,
    };

    const DX = {
      N: 0,
      S: 0,
      E: 1,
      W: -1,
    };

    const DY = {
      N: -1,
      S: 1,
      E: 0,
      W: 0,
    };

    const OPPOSITE = {
      N: this.DIRECTIONS.S,
      S: this.DIRECTIONS.N,
      E: this.DIRECTIONS.W,
      W: this.DIRECTIONS.E,
    };

    // Setup the function that recursively carves the passages.
    const carvePassage = (cx, cy, grid) => {
      const rndDirs = ['N', 'S', 'E', 'W'].sort(() => Math.random() - 0.5);
      for (let i = 0; i < rndDirs.length; i += 1) {
        const direction = rndDirs[i];
        const nx = cx + DX[direction];
        const ny = cy + DY[direction];

        if (ny >= 0 && ny <= grid.length - 1 && nx >= 0 &&
            nx <= grid[ny].length - 1 && grid[ny][nx] === 0) {
          grid[cy][cx] |= this.DIRECTIONS[direction];
          grid[ny][nx] |= OPPOSITE[direction];
          carvePassage(nx, ny, grid);
        }
      }
    };

    // Carve out the passages
    // Start at position 0, 0.
    carvePassage(0, 0, this.mazeGrid);

    console.log(this.printMaze());
  }

  printMaze() {
    let s = ' ';
    for (let i = 0; i < (this.mazeGrid[0].length * 2) - 1; i += 1) {
      s += '_';
    }
    s += '\n';

    for (let y = 0; y < this.mazeGrid.length; y += 1) {
      s += '|';
      for (let x = 0; x < this.mazeGrid[y].length; x += 1) {
        if ((this.mazeGrid[y][x] & this.DIRECTIONS.S) !== 0) s += ' ';
        else s += '_';

        if ((this.mazeGrid[y][x] & this.DIRECTIONS.E) !== 0) {
          if (((this.mazeGrid[y][x] | this.mazeGrid[y][x + 1]) & this.DIRECTIONS.S) !== 0) s += ' ';
          else s += '_';
        } else {
          s += '|';
        }
      }
      s += '\n';
    }
    return s;
  }
}

module.exports = Maze;
