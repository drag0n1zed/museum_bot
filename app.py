"""
Main Application Module for Museum Bot.

This module contains the main entry point function that initializes
and starts the museum bot application.
"""

import json
import threading
import time
import queue
from enum import Enum

# Import the separated components
try:
    from . import web, navigation, ai, driver, tts
except ImportError:
    # Fallback for running directly with python app.py
    import web
    import navigation
    import ai
    import driver
    import tts


# --- STATE MACHINE SETUP ---
class RobotState(Enum):
    IDLE = 1
    NAVIGATING = 2
    SPEAKING = 3


# Initialize TTS models
tts.initialize_tts()


class Robot:
    def __init__(self, data_filepath, socketio=None, initial_language="EN"):
        # Load data from the file system
        import os

        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Navigate to the data directory
        data_dir = os.path.join(current_dir, "data")
        data_file_path = os.path.join(data_dir, data_filepath)

        # Check if the file exists and load it
        if os.path.exists(data_file_path):
            with open(data_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            raise FileNotFoundError(f"Data file not found at: {data_file_path}")

        map_data = data["map"]
        self.x = map_data["metadata"]["start_x"]
        self.y = map_data["metadata"]["start_y"]
        self.angle = map_data["metadata"]["start_angle"]
        self.grid_unit_cm = map_data["metadata"]["grid_unit_cm"]
        self.map_grid = map_data["grid"]
        self.socketio = socketio  # Store socketio instance
        self.dynamic_obstacles = set()  # Track dynamic obstacles
        # Load POI data from the same file
        self.poi_data = {poi["id"]: poi for poi in data["pois"]}
        # Initialize current POI to the starting position
        self.current_poi_id = "poi_2"  # Entrance POI
        self.state = RobotState.IDLE
        self.language = (
            initial_language.upper()
            if initial_language.upper() in ["EN", "ZH"]
            else "EN"
        )
        # Track if we're at a destination and showing arrival questions
        self.at_destination = False
        self.arrival_questions = []
        self.arrival_questions_shown = (
            False  # Track if arrival questions have been shown
        )
        self.follow_up_questions = []
        self.tts_ready = False  # Track if TTS is ready

    # --- NEW: Granular WebSocket Emitter Methods ---
    def emit_position(self):
        """Emits only the robot's current position and angle. Called frequently."""
        if self.socketio:
            self.socketio.emit(
                "update_position",
                {"position": {"x": self.x, "y": self.y}, "angle": self.angle},
            )

    def emit_new_path(self, path):
        """Emits the full new path. Called only when a path is calculated."""
        if self.socketio:
            # Convert path to list of dictionaries
            path_as_dicts = [{"x": node[0], "y": node[1]} for node in path]
            self.socketio.emit("new_path", {"path": path_as_dicts})

    def emit_obstacles(self):
        """Emits the set of dynamic obstacles. Called only when a new one is found."""
        if self.socketio:
            self.socketio.emit(
                "update_obstacles", {"obstacles": list(self.dynamic_obstacles)}
            )

    def emit_error(self, message):
        """Emits an error message to the client for UI display."""
        if self.socketio:
            self.socketio.emit("navigation_error", {"message": message})

    def set_language(self, lang_code: str):
        if lang_code.upper() in ["EN", "ZH"]:
            self.language = lang_code.upper()
            print(f"[ROBOT] Language set to {self.language}")
            ai.generate_tts_and_play(
                "Language set." if self.language == "EN" else "语言已设定",
                self.language,
            )

    def ask_question(self, question: str):
        """Handles the logic for answering a question."""
        global last_ai_response
        self.state = RobotState.SPEAKING
        self.tts_ready = False  # Reset TTS ready flag
        # Use TTS instead of static sound file for "thinking" sound
        thinking_text = (
            "让我想一想..." if self.language == "ZH" else "Let me think for a bit..."
        )
        ai.generate_tts_and_play(thinking_text, self.language)

        ai_answer = ai.get_ai_response(
            question, self.language, self.poi_data, self.current_poi_id
        )

        # Parse the AI response to extract answer and follow-up questions
        parsed_response = ai.parse_ai_response(ai_answer)
        answer = parsed_response["answer"]
        self.follow_up_questions = parsed_response["follow_up_questions"]
        # Synchronize with web module's global variable
        web.follow_up_questions = parsed_response["follow_up_questions"]

        last_ai_response = answer  # Store AI response for web UI
        # Add AI response to conversation history
        web.conversation_history.append(("ai", answer))

        # Limit conversation history to prevent it from growing too large
        if len(web.conversation_history) > 20:  # Keep only the last 20 messages
            web.conversation_history = web.conversation_history[-20:]

        ai.generate_tts_and_play(answer, self.language)
        self.tts_ready = True  # Set TTS ready flag
        print("[ROBOT] TTS ready flag set to True")

        self.state = RobotState.IDLE

    def go_to_poi(self, target_poi_id: str):
        """Handles the logic for navigating to a POI."""
        self.state = RobotState.NAVIGATING
        # Use TTS instead of static sound file for "lets go" sound
        navigate_prompt_key = f"navigate_{target_poi_id}_{self.language.lower()}"
        navigate_text = tts.get_tts_prompt(navigate_prompt_key)
        if navigate_text:
            ai.generate_tts_and_play(
                navigate_text, self.language, key=navigate_prompt_key
            )
        else:
            # Fallback to generic text if no specific prompt
            generic_text = (
                "好的，我们出发吧！" if self.language == "ZH" else "Okay, let's go!"
            )
            ai.generate_tts_and_play(generic_text, self.language)

        # Use the robot's actual current position as the starting point
        start_coords = (self.x, self.y)
        end_coords = self.poi_data[target_poi_id]["coordinates"]
        path = navigation.find_a_star_path(
            self.map_grid,
            start_coords,
            (end_coords["x"], end_coords["y"]),
        )

        # Emit the new path if using SocketIO
        if path:
            self.emit_new_path(path)
        else:
            self.emit_new_path([])  # Clear path on client
            self.emit_error("Cannot find a path to the destination.")  # Emit error

        success = True
        if path:
            success = self.follow_path(path)  # This is a blocking call

        # Only update current POI if navigation was successful
        if success:
            self.current_poi_id = target_poi_id
        if self.current_poi_id in self.poi_data and success:
            # Set at_destination flag
            self.at_destination = True

            # Reset flags when arriving at a new destination
            self.arrival_questions_shown = False  # Reset arrival questions shown flag
            self.follow_up_questions = []
            web.follow_up_questions = []

            # Use dynamic TTS prompts with fallback
            poi = self.poi_data[self.current_poi_id]
            poi_id = poi["id"]

            # Get arrival prompt with fallback
            arrival_prompt_key = f"arrival_{poi_id}_{self.language.lower()}"
            arrival_text = tts.get_tts_prompt(arrival_prompt_key)

            if not arrival_text:
                # Fallback to generic arrival message
                # Handle both old format (dict) and new format (merged string)
                if isinstance(poi["name"], dict):
                    poi_name = poi["name"]["en"]
                else:
                    # New merged format - extract from bilingual string
                    name_parts = (
                        poi["name"].split(". ")
                        if "." in poi["name"]
                        else [poi["name"], ""]
                    )
                    poi_name = name_parts[0]

                if isinstance(poi["description"], dict):
                    poi_description = poi["description"]["en"]
                else:
                    # New merged format - extract from bilingual string
                    desc_parts = (
                        poi["description"].split(". ")
                        if ". " in poi["description"]
                        else [poi["description"], ""]
                    )
                    poi_description = desc_parts[0] + (
                        "." if not desc_parts[0].endswith(".") else ""
                    )

                if self.language == "ZH":
                    if isinstance(poi["name"], dict):
                        poi_name = poi["name"]["zh"]
                    else:
                        # New merged format - extract from bilingual string
                        name_parts = (
                            poi["name"].split(". ")
                            if "." in poi["name"]
                            else [poi["name"], ""]
                        )
                        poi_name = (
                            name_parts[1] if len(name_parts) > 1 else name_parts[0]
                        )

                    if isinstance(poi["description"], dict):
                        poi_description = poi["description"]["zh"]
                    else:
                        # New merged format - extract from bilingual string
                        desc_parts = (
                            poi["description"].split(". ")
                            if ". " in poi["description"]
                            else [poi["description"], ""]
                        )
                        poi_description = (
                            ". ".join(desc_parts[1:])
                            if len(desc_parts) > 1
                            else desc_parts[0]
                        )
                arrival_text = (
                    f"We have arrived at {poi_name}. {poi_description}"
                    if self.language == "EN"
                    else f"我们已到达{poi_name}。{poi_description}"
                )

            ai.generate_tts_and_play(
                arrival_text, self.language, key=arrival_prompt_key
            )

            # Generate arrival questions
            self._generate_arrival_questions()

        self.state = RobotState.IDLE

    def _generate_arrival_questions(self):
        """Generate arrival questions for the current POI."""
        if self.current_poi_id in self.poi_data:
            poi = self.poi_data[self.current_poi_id]

            # Generate some default questions based on the POI
            if self.language == "EN":
                self.arrival_questions = [
                    f"What can you tell me about {poi['name'].split('.')[0] if isinstance(poi['name'], str) else poi['name']['en']}?",
                    "What is the history of this exhibit?",
                    "Are there any interesting facts about this display?",
                    "What is the significance of this artifact?",
                ]
            else:
                self.arrival_questions = [
                    f"能告诉我一些关于{poi['name'].split('.')[1] if isinstance(poi['name'], str) else poi['name']['zh']}的信息吗？",
                    "这个展品的历史是什么？",
                    "关于这个展览有什么有趣的事实吗？",
                    "这个文物有什么重要意义？",
                ]

    def _update_current_poi(self):
        """Update current_poi_id based on the robot's actual position."""
        for poi_id, poi in self.poi_data.items():
            if (self.x, self.y) == (
                poi["coordinates"]["x"],
                poi["coordinates"]["y"],
            ):
                self.current_poi_id = poi_id
                break

    def follow_path(self, path: list[tuple]):
        """CORRECTED stateful path following logic with dynamic obstacle avoidance."""

        print(f"[ROBOT] Following stateful path with {len(path)} steps")

        # Remove the starting node if it's the robot's current location
        if path and (path[0] == (self.x, self.y)):
            path.pop(0)

        current_path = path

        while current_path:
            # Get the next step from the path
            target_x, target_y = current_path.pop(0)

            # SIMULATE SUPERSONIC SENSOR CHECK (5% chance of detecting an obstacle)
            if driver.supersonic_sensor_check():
                print(
                    f"[ROBOT] SENSOR: Supersonic sensor detected obstacle at ({target_x}, {target_y})!"
                )
                # Update the map to mark this position as an obstacle
                self.map_grid[target_y][target_x] = 1  # 1 = obstacle
                # Add to dynamic obstacles set
                self.dynamic_obstacles.add((target_x, target_y))
                # Emit updated obstacles
                self.emit_obstacles()

                # Get current position
                current_pos = (self.x, self.y)

                # Get destination position (last node in original path)
                if path:  # Original path
                    end_pos = path[-1] if path else (target_x, target_y)
                else:
                    # If original path is empty, use the target position
                    end_pos = (target_x, target_y)

                # RE-PLAN path from current position to destination
                print("[ROBOT] ACTION: Re-planning path from current position...")
                new_path = navigation.find_a_star_path(
                    self.map_grid, current_pos, end_pos
                )

                if not new_path:
                    print("[ROBOT] ERROR: Cannot find a new path around the obstacle.")
                    self.emit_error("Cannot find a new path around the obstacle.")
                    return False  # Abort navigation

                # Emit the new path
                self.emit_new_path(new_path)

                # Adopt the new path
                current_path = new_path
                print(f"[ROBOT] INFO: New path planned with {len(current_path)} steps.")

                # If the new path starts with our current position, remove it
                if current_path and current_path[0] == current_pos:
                    current_path.pop(0)

                # Get the new first step
                if current_path:
                    target_x, target_y = current_path.pop(0)
                else:
                    # If no more steps, we're done
                    break

            print(f"--- Moving from ({self.x},{self.y}) to ({target_x},{target_y}) ---")
            dx = target_x - self.x
            dy = target_y - self.y

            if dx == 1:
                target_angle = 0  # East
            elif dx == -1:
                target_angle = 180  # West
            elif dy == 1:
                target_angle = 90  # South (canvas y-axis points down)
            elif dy == -1:
                target_angle = 270  # North (canvas y-axis points down)
            else:
                print("ERROR: Invalid path segment. Skipping.")
                continue

            turn_angle = target_angle - self.angle
            if turn_angle > 180:
                turn_angle -= 360
            if turn_angle <= -180:
                turn_angle += 360

            if abs(turn_angle) > 1:  # Avoid trivial turns
                print(
                    f"[DEBUG] Turning {turn_angle} degrees (from {self.angle} to {target_angle})"
                )
                # Determine turn direction based on angle
                if turn_angle > 0:
                    driver.turn("right")
                else:
                    driver.turn("left")
                self.angle = target_angle

            print(f"[DEBUG] Moving forward {self.grid_unit_cm} cm")
            driver.move_forward()
            self.x = target_x
            self.y = target_y

            # Emit position update
            self.emit_position()

            # Update current POI based on new position
            self._update_current_poi()

        print("[ROBOT] Finished following path.")
        return True


# --- ROBOT'S MAIN BRAIN LOOP ---
def robot_logic_thread_func():
    """The main, continuous loop that processes commands for the robot."""
    global robot_instance, last_ai_response
    last_ai_response = ""
    driver.setup_hardware()

    # Initialize robot with default language, will be updated when user selects language
    robot_instance = Robot("raw_poi_data.json", web.socketio, "EN")

    # Set the robot instance in the web module
    web.set_robot_instance(robot_instance)

    print("[ROBOT_THREAD] Robot logic initialized and ready for commands.")

    while True:
        try:
            # Wait for a command from the web server
            command, args = web.command_queue.get(
                timeout=1
            )  # Check for command every second

            if robot_instance.state == RobotState.IDLE:
                if command == "GOTO":
                    robot_instance.go_to_poi(args)
                elif command == "ASK":
                    robot_instance.ask_question(args)
                elif command == "SET_LANG":
                    robot_instance.set_language(args)
                elif command == "SET_INITIAL_LANG":
                    robot_instance.language = (
                        args.upper() if args.upper() in ["EN", "ZH"] else "EN"
                    )
                    print(f"[ROBOT] Initial language set to {robot_instance.language}")
            else:
                print(
                    f"[ROBOT_THREAD] Command '{command}' ignored, robot is busy ({robot_instance.state.name})"
                )

        except queue.Empty:
            # No command received, just continue the loop
            pass
        time.sleep(0.1)


def start_museum_bot(
    data_file_path="data/raw_poi_data.json", port=5001, host="0.0.0.0"
):
    """
    Main entry point to start the museum bot application.

    Args:
        data_file_path (str): Path to the POI data file
        port (int): Port number for the webserver
        host (str): Host address for the webserver

    This function will:
    1. Initialize all required components (TTS, AI, etc.)
    2. Start the robot logic thread
    3. Start the webserver
    """
    print("Starting Museum Bot application...")

    # Start the robot logic thread
    robot_thread = threading.Thread(target=robot_logic_thread_func, daemon=True)
    robot_thread.start()

    # Start the webserver
    web.run_server(port=port, host=host)


if __name__ == "__main__":
    start_museum_bot()
