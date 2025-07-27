"""
Command Line Interface module for Museum Bot.

This module contains functions that can be called as console scripts
for various utility functions of the museum bot.
"""

import sys
import json
from PIL import Image


def run_png_to_grid():
    """Run the PNG to grid conversion tool."""
    # Import the png_to_grid functionality
    print("Running the PNG to Grid conversion tool...")

    # Get arguments from command line
    if len(sys.argv) < 3:
        print("Usage: museum-png-to-grid input.png output.json")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    # Default values for grid parameters
    start_x = 10
    start_y = 0
    start_angle = 90
    grid_unit_cm = 30

    try:
        # Open the image
        img = Image.open(input_path)
        width, height = img.size

        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Load pixel data
        pixels = img.load()

        # Define the POI color
        poi_color = (0, 249, 255)  # #00f9ff

        # Create the grid
        grid = []
        pois = []
        poi_counter = 1

        for y in range(height):
            row = []
            for x in range(width):
                pixel = pixels[x, y] if pixels else img.getpixel((x, y))

                # Check if it's a wall (pure black)
                if pixel == (0, 0, 0):
                    row.append(1)  # Wall
                # Check if it's a POI
                elif pixel == poi_color:
                    row.append(0)  # Space (POIs are placed on spaces)
                    # Add POI to the list
                    poi_id = f"poi_{poi_counter}"
                    pois.append(
                        {
                            "id": poi_id,
                            "name": {
                                "en": f"POI {poi_counter}",
                                "zh": f"POI {poi_counter}",
                            },
                            "description": f"Description for POI {poi_counter}",
                            "coordinates": {"x": x, "y": y},
                        }
                    )
                    poi_counter += 1
                # Otherwise, it's a space (pure white or any other color)
                else:
                    row.append(0)  # Space
            grid.append(row)

        # Create the JSON structure
        data = {
            "map": {
                "metadata": {
                    "start_x": start_x,
                    "start_y": start_y,
                    "start_angle": start_angle,
                    "grid_unit_cm": grid_unit_cm,
                },
                "grid": grid,
            },
            "pois": pois,
        }

        # Write to output file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Successfully converted {input_path} to {output_path}")
        print(f"Grid size: {width}x{height}")
        print(f"Number of POIs: {len(pois)}")

        # --- NEW: Added Grid Preview ---
        print("\nGrid Preview (█=Wall, .=Space, P=POI):")
        # Create a temporary grid for display purposes
        display_grid = [list(row) for row in grid]
        for poi in pois:
            px, py = poi["coordinates"]["x"], poi["coordinates"]["y"]
            if 0 <= py < height and 0 <= px < width:
                # Use a character to represent POIs, e.g., 'P' or a number
                display_grid[py][px] = "P"

        for row in display_grid:
            row_str = ""
            for cell in row:
                if cell == 1:
                    row_str += "█"
                elif cell == 0:
                    row_str += "."
                else:
                    row_str += str(cell)  # This will print 'P'
            print(row_str)
        # --- End of new section ---

    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)


def run_generate_tts():
    """Run the TTS pre-generation tool."""
    print("Running the TTS pre-generation tool...")

    # Import the TTS generation functionality
    try:
        # Try package import first
        from museum_bot.generate_tts_prompts import main as generate_tts_main
    except ImportError:
        try:
            # Try direct execution import
            from generate_tts_prompts import main as generate_tts_main
        except ImportError as e:
            print(f"Error importing TTS generation module: {e}")
            sys.exit(1)

    try:
        generate_tts_main()
    except Exception as e:
        print(f"Error running TTS generation: {e}")
        sys.exit(1)


def main():
    """Main function to handle CLI commands."""
    if len(sys.argv) < 2:
        print("Usage: museum-bot-cli [command]")
        print("Commands:")
        print("  png-to-grid     Convert PNG map to grid JSON")
        print("  generate-tts    Pre-generate TTS prompts")
        sys.exit(1)

    command = sys.argv[1]

    if command == "png-to-grid":
        run_png_to_grid()
    elif command == "generate-tts":
        run_generate_tts()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
