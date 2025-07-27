import heapq


class Node:
    """Represents a node in the A* pathfinding algorithm."""

    def __init__(self, x, y, g=float("inf"), h=0, f=float("inf"), parent=None):
        self.x = x
        self.y = y
        self.g = g
        self.h = h
        self.f = f
        self.parent = parent

    def __lt__(self, other):
        """Comparison method for priority queue."""
        return self.f < other.f

    def __eq__(self, other):
        """Equality method to compare nodes by coordinates."""
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        """Hash method for using nodes in sets."""
        return hash((self.x, self.y))


class AStarFinder:
    """Custom implementation of the A* pathfinding algorithm."""

    # Turn penalty constant - higher values will result in fewer turns
    TURN_PENALTY = 2.0

    def __init__(self):
        pass

    def heuristic(self, node, end_node):
        """Calculate the Manhattan distance heuristic for grid-based movement."""
        return abs(node.x - end_node.x) + abs(node.y - end_node.y)

    def get_neighbors(self, node, map_data):
        """Get valid neighboring nodes, excluding diagonal neighbors."""
        neighbors = []
        # Define the 4 possible movements (cardinal directions only)
        directions = [
            (0, 1),  # North
            (0, -1),  # South
            (1, 0),  # East
            (-1, 0),  # West
        ]

        # Check if map_data is valid and not empty
        if not map_data:
            return neighbors
        # Check if the first row exists and is not empty
        if not map_data[0]:
            return neighbors

        for dx, dy in directions:
            new_x, new_y = node.x + dx, node.y + dy

            # Check if the new position is within the map boundaries
            if 0 <= new_y < len(map_data) and 0 <= new_x < len(map_data[0]):
                # Check if the new position is not an obstacle (static or dynamic)
                # For this demo, we only check for static obstacles
                if map_data[new_y][new_x] == 0:  # 0 = open space
                    neighbors.append(Node(new_x, new_y))

        return neighbors

    def _calculate_turn_penalty(self, current_node, neighbor):
        """
        Calculate the turn penalty when moving from current_node to neighbor.

        A turn occurs if the direction of movement from grandparent -> current_node
        is different from the direction of movement from current_node -> neighbor.
        """
        # No penalty if current_node has no parent (it's the start node)
        if current_node.parent is None:
            return 0

        # Calculate vectors
        # Vector from grandparent to parent (current_node.parent to current_node)
        vec1 = (
            current_node.x - current_node.parent.x,
            current_node.y - current_node.parent.y,
        )
        # Vector from parent to neighbor (current_node to neighbor)
        vec2 = (neighbor.x - current_node.x, neighbor.y - current_node.y)

        # Apply penalty if the direction changed
        if vec1 != vec2:
            return self.TURN_PENALTY

        return 0

    def _calculate_movement_cost(self, current_node, neighbor):
        """Calculate the movement cost between two adjacent nodes."""
        # Only straight movements are allowed
        return 1.0

    def find_path(self, map_data, start_coords, end_coords):
        """
        Find the shortest path using the A* algorithm with turn penalties.

        Args:
            map_data (list): 2D list representing the environment (0 = open, 1 = obstacle)
            start_coords (tuple): (x, y) representing the starting position
            end_coords (tuple): (x, y) representing the destination

        Returns:
            list: List of (x, y) tuples representing the path, or empty list if no path exists
        """
        # Validate map_data
        if not map_data:
            print("[NAVIGATION] Error: Invalid or empty map data")
            return []
        # Check if the first row exists and is not empty
        if not map_data[0]:
            print("[NAVIGATION] Error: Invalid or empty map data")
            return []

        # Validate start and end coordinates
        if not (
            0 <= start_coords[1] < len(map_data)
            and 0 <= start_coords[0] < len(map_data[0])
        ):
            print(
                f"[NAVIGATION] Error: Start coordinates {start_coords} are out of bounds"
            )
            return []

        if not (
            0 <= end_coords[1] < len(map_data) and 0 <= end_coords[0] < len(map_data[0])
        ):
            print(f"[NAVIGATION] Error: End coordinates {end_coords} are out of bounds")
            return []

        # Check if start or end positions are obstacles
        if map_data[start_coords[1]][start_coords[0]] != 0:
            print(f"[NAVIGATION] Error: Start position {start_coords} is an obstacle")
            return []

        if map_data[end_coords[1]][end_coords[0]] != 0:
            print(f"[NAVIGATION] Error: End position {end_coords} is an obstacle")
            return []

        # Create start and end nodes
        start_node = Node(start_coords[0], start_coords[1], g=0)
        end_node = Node(end_coords[0], end_coords[1])

        # Initialize open and closed lists
        open_list = []
        closed_list = set()

        # Add the start node to the open list
        heapq.heappush(open_list, start_node)

        # Main loop
        while open_list:
            # Get the node with the lowest f cost
            current_node = heapq.heappop(open_list)

            # Add current node to closed list
            closed_list.add((current_node.x, current_node.y))

            # Check if we've reached the end
            if current_node == end_node:
                # Reconstruct path
                path = []
                while current_node is not None:
                    path.append((current_node.x, current_node.y))
                    current_node = current_node.parent
                return path[::-1]  # Return reversed path

            # Generate neighbors
            neighbors = self.get_neighbors(current_node, map_data)

            for neighbor in neighbors:
                # Skip if neighbor is in closed list
                if (neighbor.x, neighbor.y) in closed_list:
                    continue

                # Calculate movement cost
                movement_cost = self._calculate_movement_cost(current_node, neighbor)

                # Calculate turn penalty
                turn_penalty = self._calculate_turn_penalty(current_node, neighbor)

                # Calculate tentative g score with turn penalty
                tentative_g = current_node.g + movement_cost + turn_penalty

                # Check if this path to neighbor is better
                if tentative_g < neighbor.g:
                    # Update neighbor's properties
                    neighbor.parent = current_node
                    neighbor.g = tentative_g
                    neighbor.h = self.heuristic(neighbor, end_node)
                    neighbor.f = neighbor.g + neighbor.h

                    # Add neighbor to open list if not already there
                    # Check if neighbor is already in open list
                    in_open_list = False
                    for node in open_list:
                        if neighbor == node and neighbor.g > node.g:
                            in_open_list = True
                            break

                    if not in_open_list:
                        heapq.heappush(open_list, neighbor)

        # No path found
        return []


def find_a_star_path(grid, start, end):
    """
    Calculate the shortest path between two points using the A* algorithm.

    Args:
        grid (list): 2D list representing the environment (0 = open, 1 = obstacle)
        start (tuple): (x, y) representing the starting position
        end (tuple): (x, y) representing the destination

    Returns:
        list: List of (x, y) tuples representing the path, or empty list if no path exists
    """
    try:
        # Create our custom A* finder
        finder = AStarFinder()

        # Find path
        path = finder.find_path(grid, start, end)

        # Check if a path was found
        if not path:
            print("[NAVIGATION] No path found between start and end points")
            return []

        return path

    except Exception as e:
        print(f"[NAVIGATION] Error finding path: {e}")
        return []
