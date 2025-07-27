from flask import Flask, request, render_template, redirect, url_for, jsonify
import queue
from enum import Enum
from flask_socketio import SocketIO
import json
import importlib.resources


# --- STATE MACHINE SETUP ---
class RobotState(Enum):
    IDLE = 1
    NAVIGATING = 2
    SPEAKING = 3


# Global variables
command_queue = queue.Queue()  # Thread-safe queue for commands


# Get the absolute paths for templates and static folders
def get_resource_path(package, resource):
    """Get the absolute path to a resource within the package."""
    import os

    # Try to find the resource in the file system
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if "templates" in resource:
        return os.path.join(base_dir, "templates")
    elif "static" in resource:
        return os.path.join(base_dir, "static")
    else:
        # For other resources, try to find them relative to the current directory
        return os.path.join(base_dir, resource)


# Create Flask app with proper template and static folder paths
template_path = get_resource_path("museum_bot", "templates")
static_path = get_resource_path("museum_bot", "static")

app = Flask(__name__, template_folder=template_path, static_folder=static_path)

# Use 'threading' async_mode for compatibility with the robot's background thread
socketio = SocketIO(app, async_mode="threading")  # Initialize SocketIO
last_response = ""
last_ai_response = ""
# Conversation history - list of tuples (sender, message)
conversation_history = []
# Follow-up questions from AI
follow_up_questions = []
robot_instance = None  # Will be set from app.py
selected_language = None  # Will be set when user selects language


# Load POI data
def load_poi_data():
    """Load POI data from the file system."""
    import os

    # Try to find the data file in the file system
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(base_dir, "data", "raw_poi_data.json")
    # If not found, try in the current directory
    if not os.path.exists(data_file_path):
        data_file_path = os.path.join(os.getcwd(), "data", "raw_poi_data.json")
    with open(data_file_path, "r", encoding="utf-8") as f:
        return json.load(f)


poi_data = load_poi_data()


def set_robot_instance(robot):
    """Set the robot instance for use in routes."""
    global robot_instance
    robot_instance = robot


@app.route("/")
def index():
    # Check if language is selected
    global selected_language
    if selected_language is None:
        return redirect(url_for("language_select"))

    # Pass the robot's current state to the template for UI feedback
    # Handle case where robot_instance is not yet set
    if robot_instance is None:
        return render_template(
            "index.html",
            destinations=[],
            response=last_response,
            robot_state="INITIALIZING",
            selected_language=selected_language,
        )

    # Define the custom order for destinations
    destination_order = ["poi_2", "poi_6", "poi_5", "poi_3", "poi_4", "poi_1"]
    ordered_destinations = []
    for poi_id in destination_order:
        if poi_id in robot_instance.poi_data:
            ordered_destinations.append(robot_instance.poi_data[poi_id])

    return render_template(
        "index.html",
        destinations=ordered_destinations,
        response=last_response,
        robot_state=robot_instance.state.name,
        selected_language=selected_language,
    )


@app.route("/language_select")
def language_select():
    # Show language selection page
    return render_template("language_select.html")


@app.route("/set_initial_language", methods=["POST"])
def set_initial_language():
    global selected_language
    lang = request.form["language"]
    if lang.upper() in ["EN", "ZH"]:
        selected_language = lang.upper()
        # Send command to robot to set initial language
        command_queue.put(("SET_INITIAL_LANG", lang.upper()))
    return redirect(url_for("index"))


@app.route("/set_language", methods=["POST"])
def set_language():
    global selected_language
    lang = request.form["language"]
    if lang.upper() in ["EN", "ZH"]:
        selected_language = lang.upper()
    command_queue.put(("SET_LANG", lang))
    return redirect(url_for("index"))


@app.route("/goto", methods=["POST"])
def goto():
    target_id = request.form["poi_id"]
    command_queue.put(("GOTO", target_id))
    return redirect(url_for("index"))


@app.route("/ask", methods=["POST"])
def ask():
    global last_response, last_ai_response, conversation_history, follow_up_questions
    question = request.form["question"]
    last_response = question  # Show the question immediately for feedback
    last_ai_response = ""  # Clear previous AI response

    # Reset follow-up questions when asking a new question
    follow_up_questions = []

    # Reset TTS ready flag
    if robot_instance:
        robot_instance.tts_ready = False

    # Add user question to conversation history
    conversation_history.append(("user", question))

    # Limit conversation history to prevent it from growing too large
    if len(conversation_history) > 20:  # Keep only the last 20 messages
        conversation_history = conversation_history[-20:]

    command_queue.put(("ASK", question))
    return redirect(url_for("index"))


@app.route("/ask_arrival_question", methods=["POST"])
def ask_arrival_question():
    """Handle arrival question selection."""
    global last_response, last_ai_response, conversation_history, follow_up_questions
    question = request.form["question"]
    last_response = question  # Show the question immediately for feedback
    last_ai_response = ""  # Clear previous AI response

    # Reset follow-up questions when asking a new question
    follow_up_questions = []

    # Reset TTS ready flag
    if robot_instance:
        robot_instance.tts_ready = False

    # Set arrival_questions_shown flag to hide arrival questions
    if robot_instance:
        robot_instance.arrival_questions_shown = True

    # Add user question to conversation history
    conversation_history.append(("user", question))

    # Limit conversation history to prevent it from growing too large
    if len(conversation_history) > 20:  # Keep only the last 20 messages
        conversation_history = conversation_history[-20:]

    command_queue.put(("ASK", question))
    return redirect(url_for("index"))


@app.route("/status")
def status():
    global selected_language
    # A new endpoint for the browser to poll for updates
    # Handle case where robot_instance is not yet set
    if robot_instance is None:
        return {
            "state": "INITIALIZING",
            "response": last_response,
            "language": selected_language if selected_language else "EN",
            "conversation_history": conversation_history,
        }

    return {
        "state": robot_instance.state.name,
        "response": last_ai_response if last_ai_response else last_response,
        "language": selected_language
        if selected_language
        else (robot_instance.language if robot_instance else "EN"),
        "conversation_history": conversation_history,
        "at_destination": robot_instance.at_destination if robot_instance else False,
        "arrival_questions": robot_instance.arrival_questions if robot_instance else [],
        "arrival_questions_shown": robot_instance.arrival_questions_shown
        if robot_instance
        else False,
        "tts_ready": robot_instance.tts_ready if robot_instance else False,
        "follow_up_questions": follow_up_questions,
    }


# --- NEW: API Endpoint for Static Map Data ---
@app.route("/api/map_data")
def get_map_data():
    """
    Provides the static data needed to draw the map just once on page load.
    """
    return jsonify(
        {
            "grid": poi_data["map"]["grid"],
            "pois": poi_data["pois"],
            "width": len(poi_data["map"]["grid"][0]),
            "height": len(poi_data["map"]["grid"]),
        }
    )


# --- NEW: API Endpoint for Robot's Current Position ---
@app.route("/api/robot_position")
def get_robot_position():
    """
    Provides the robot's current position and angle.
    """
    if robot_instance is None:
        # Return initial position if robot not initialized
        return jsonify({"position": {"x": 10, "y": 0}, "angle": 90})
    return jsonify(
        {
            "position": {"x": robot_instance.x, "y": robot_instance.y},
            "angle": robot_instance.angle,
        }
    )


def run_server(port=5001, host="0.0.0.0"):
    """Run the Flask web server."""
    # Clear all sessions on server restart
    with app.app_context():
        pass  # Sessions are stored client-side in Flask, so we can't clear them server-side
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
