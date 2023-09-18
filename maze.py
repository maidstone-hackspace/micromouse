import os
import secrets
from math import ceil
from PIL import Image, ImageDraw

"""
Cardinal direction values
"""
NORTH = 0
EAST = 1
SOUTH = 2
WEST = 3

"""
Printer variables
"""
printer_dpi = 300
a4_height_cm = 29.7
a4_width_cm = 21.0
cm_to_inch_ratio = 2.54

pixel_width_mm = cm_to_inch_ratio * 10 / printer_dpi
pixel_width_cm = cm_to_inch_ratio / printer_dpi

a4_height_px = a4_height_cm / pixel_width_cm
a4_width_px = a4_width_cm / pixel_width_cm

maze_slice_dir_name = "maze_slices"

"""
Calculate how wide the walls & paths need to be based off of pixel -> mm mapping
"""
wall_width_mm = 80
path_width_mm = 5

wall_width = wall_width_mm / pixel_width_mm # E.g. How many pixels fit into 160mm
path_width = path_width_mm / pixel_width_mm

"""
Dimensions are now specified by the number of cells. This allows the program to calculate
exactly how much space is required for the maze.
"""
num_cols = 10
num_rows = 10

"""
Metadata for encoding direction, how to calculate the address of that cell, and whether checking
the cell would result in an out-of-bounds array access.

Format:

[
    list[int, int]: A list containing the entry's id and "opposite id". These are correlated with
        the values in the current & the adjacent cell's `connected` lists.
    tuple[int, int]: dx, dy required to get to adjacent cell.
    lambda[int, int]: Callable that performs bounds-check to ensure adjacent cell exists
]
"""
directional_metadata = [
    [[NORTH, SOUTH], (0, -1), lambda x,y: y > 0],            # North
    [[EAST, WEST],   (1, 0),  lambda x,y: x < num_cols - 1], # East
    [[SOUTH, NORTH], (0, 1),  lambda x,y: y < num_rows - 1], # South
    [[WEST, EAST],   (-1, 0), lambda x,y: x > 0]             # West
]

# Create a grid for the maze
maze = [
    [
        {
            'coords': (x, y),
            'visited': False,
            'connections': [False, False, False, False]
        } for x in range(num_cols)
    ] for y in range(num_rows)
] 

start_cell = None
end_cell = None

def get_adjacent_cell(base: tuple[int, int], modifier: tuple[int, int]) -> dict:
    new_x, new_y = tuple(map(lambda a,b: a + b, base, modifier))
    return maze[new_y][new_x]


# Generate a random maze using the Depth First Search algorithm
def generate_directional_maze():

    global start_cell, end_cell

    # Generate a random starting position in the maze
    random_start_num = secrets.randbelow(num_rows * num_cols)
    start_cell = maze[random_start_num // num_rows][random_start_num % num_cols]
    current_cell = start_cell
    #current_cell = maze[0][0]
    neighbours = []
    visited = []

    current_path_length = 1
    longest_path_length = 1

    # Set initial state for the first cell
    current_cell['visited'] = True
    visited.append(current_cell)

    # Must use this instead of len(visited), as "visited.pop()" will change the array length
    # meaning the algorithm will never complete
    nVisited = 1

    while nVisited != num_cols * num_rows:

        x, y = current_cell['coords']
        neighbours.clear()

        # Check for unvisited neighbours
        for direction_data in directional_metadata:

            # Perform check to see if cell exists & whether it's been visited
            if direction_data[2].__call__(x, y) and not get_adjacent_cell(current_cell['coords'], direction_data[1])['visited']: 
                neighbours.append(direction_data)

        if neighbours:

            # Choose a random neighbour as our next cell
            choice = secrets.choice(neighbours)

            # Set the current cell's relevant `connections` bool
            current_cell['connections'][choice[0][0]] = True

            # Set `current_cell` to refer to the randomly-selected neighbour
            current_cell = get_adjacent_cell(current_cell['coords'], choice[1])

            # Set the new cell's `connections` bool to also point back to the previous cell
            current_cell['connections'][choice[0][1]] = True

            # Mark the new cell as visited
            current_cell['visited'] = True
            visited.append(current_cell)
            nVisited += 1

            # Increase current path length variable
            current_path_length += 1

            # Check if this is the longest path
            if current_path_length > longest_path_length:
                longest_path_length = current_path_length
                end_cell = current_cell

        else:
            # We have no path forward, so work backwards until we find a cell with an unvisited
            # neighbour.
            current_cell = visited.pop()
            current_path_length -= 1

    print(f'Current path length: {current_path_length}')
    print(f'Longest path: {longest_path_length}')


generate_directional_maze()

"""
Calculate required canvas width & height. The maze is seen as a constant size determined by the
number of cells and the specific spacing requirements. A total width & height can be calculated
using this information.

It is worth noting that drawing the "white cells" is no longer required - this is taken care of
simply by setting a white background, setting the dimensions of the maze, and drawing the paths
with wall-space in mind.
"""
canvas_buffer = wall_width
canvas_height = (canvas_buffer * 2) + (path_width * (num_rows - 1)) + (wall_width * (num_rows - 1))
canvas_width = (canvas_buffer * 2) + (path_width * (num_cols - 1)) + (wall_width * (num_cols - 1))

"""
Calculate how many A4 pages are required to print this image
"""
a4_pages_required_horizontal = ceil(canvas_width / a4_width_px)
a4_pages_required_vertical = ceil(canvas_height / a4_height_px)

print(f'A4 sheets required: {a4_pages_required_horizontal}x{a4_pages_required_vertical}')

# Create an image to represent the maze
image = Image.new("RGB", (round(canvas_width), round(canvas_height)), "white")
draw = ImageDraw.Draw(image)

for row in range(num_rows):
    for col in range(num_cols):

        """
        Calculate the current offset of the cell based on row / col number & known spacing requirements
        """
        x0, y0 = canvas_buffer + (path_width * col) + (wall_width * col), canvas_buffer + (path_width * row) + (wall_width * row)
        x1, y1 = x0 + path_width, y0 + path_width

        """
        Cells are all rendered equidistant from eachother, with a mandatory `wall_width` buffer between them. As such,
        we need to manually check whether or not cells are supposed to be connected by checking the east and south
        cells. Seeing as we will visit all cells in the grid, this ensures that all cells are connected to their
        neighbours where applicable. If an adjacent cell is connected, the relevant coordinate will be modified to
        connect it to the neighbour. This requires multiple draws, as drawing both a modified x1 and y1 simultaneously
        creates a `wall_width`^2 sized square as opposed to individual `wall_width` length path lines.
        """ 
        if row < num_rows - 1:
            if maze[row][col]['connections'][SOUTH]:
                # draw.rectangle([x0, y0, x1, y1 + wall_width + path_width], outline="black", fill=None) #fill="black")
                draw.rectangle([x0, y0, x1, y1 + wall_width + path_width], fill="black")

        if col < num_cols - 1:
            if maze[row][col]['connections'][EAST]:
                # draw.rectangle([x0, y0, x1 + wall_width + path_width, y1], outline="black", fill=None) # fill="black")
                draw.rectangle([x0, y0, x1 + wall_width + path_width, y1], fill="black")


# Get co-ordinates of the start & end cells
start_x, start_y = start_cell['coords']
end_x, end_y = end_cell['coords']

# Define size of start & end markers
marker_size = path_width * 4
marker_offset = (marker_size / 4) + path_width / 2

# Calculate render co-ordinates of the starting point marker
start_x0, start_y0 = canvas_buffer + (path_width * start_x) + (wall_width * start_x) - marker_offset, canvas_buffer + (path_width * start_y) + (wall_width * start_y) - marker_offset
start_x1, start_y1 = start_x0 + marker_size, start_y0 + marker_size

# Calculate render co-ordinates of the ending point marker
end_x0, end_y0 = canvas_buffer + (path_width * end_x) + (wall_width * end_x) - marker_offset, canvas_buffer + (path_width * end_y) + (wall_width * end_y) - marker_offset
end_x1, end_y1 = end_x0 + marker_size, end_y0 + marker_size

# Draw the markers
draw.rectangle([start_x0, start_y0, start_x1, start_y1], fill="black")
draw.ellipse([end_x0, end_y0, end_x1, end_y1], fill="black")

# Create a directory to store the individual maze segments
if not os.path.exists(maze_slice_dir_name):
    os.makedirs(maze_slice_dir_name)

maze_edge_x = (path_width * num_cols - 1) + (wall_width * num_cols - 1) + path_width
maze_edge_y = (path_width * num_rows - 1) + (wall_width * num_rows - 1) + path_width

# Create individual A4-sized maze segments
for y in range(a4_pages_required_vertical):
    for x in range(a4_pages_required_horizontal):

        is_last_page_x = x == a4_pages_required_horizontal - 1
        is_last_page_y = y == a4_pages_required_vertical - 1

        slice_start_x = x * round(a4_width_px)
        slice_start_y = y * round(a4_height_px)

        slice_end_x = ((x + 1) * a4_width_px - 1) if not is_last_page_x else maze_edge_x
        slice_end_y = ((y + 1) * a4_height_px - 1) if not is_last_page_y else maze_edge_y

        # Crop specific area of the main image
        image_slice = image.crop([
            slice_start_x,
            slice_start_y,
            slice_end_x,
            slice_end_y
        ])

        # If this is the last page in the x or y axis, create a new A4-sized image and paste the maze onto it to avoid black bars
        if is_last_page_x or is_last_page_y:
            tmp = image_slice
            image_slice = Image.new("RGB", (round(a4_width_px), round(a4_height_px)), "white")
            image_slice.paste(tmp)

            """
            Check if image is all white - if it is, do not save it. This can occur when all paths are included in other image
            slices, and only white "buffer space" is cropped into this image segment. These can be disregarded.
            """
            if image_slice.convert("L").getextrema() == (255, 255):
                continue

        # Formulate the segment filepath in an os-independant way
        img_path = os.path.join(maze_slice_dir_name, f'maze-slice-{y}-{x}.jpg')

        # Save segment
        image_slice.save(img_path, "JPEG", dpi=(printer_dpi, printer_dpi))

# Save the maze as a printable JPEG
maze_filename = "maze.jpg"
image.save(maze_filename, "JPEG", dpi=(printer_dpi, printer_dpi))
print(f"Full maze saved as {maze_filename}. Individual A4 slices saved to '.\\{maze_slice_dir_name}\\'")
