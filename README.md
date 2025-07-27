# Museum Bot

An intelligent museum guide robot application that provides interactive navigation and information services for museum visitors. The application features both a web-based interface and hardware integration for a complete museum experience.

## Features

- Interactive museum navigation with pathfinding algorithms
- Multilingual support (English and Chinese)
- AI-powered question answering system
- Text-to-speech capabilities for audio guidance
- Real-time robot position tracking
- Dynamic obstacle avoidance
- Web-based user interface with visual map display

## Project Structure

```
museum_bot/
├── app.py                 # Main application entry point
├── web.py                 # Web server and UI components
├── navigation.py          # Pathfinding and navigation algorithms
├── ai.py                  # AI question answering system
├── tts.py                 # Text-to-speech functionality
├── driver.py              # Hardware driver interface
├── cli.py                 # Command-line interface utilities
├── requirements.txt       # Python dependencies
├── data/
│   └── raw_poi_data.json  # Point of Interest data
├── templates/             # HTML templates
├── static/                # Static assets (CSS, JavaScript)
├── sounds/                # Audio files
└── utils/                 # Utility functions
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd museum_bot
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv museum_bot_env
   source museum_bot_env/bin/activate  # On Windows: museum_bot_env\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up data files:

   To use the application, you need to create a `data/raw_poi_data.json` file from the provided sample:

   ```bash
   cp data/raw_poi_data.sample.json data/raw_poi_data.json
   ```

   Then, you need to generate the TTS prompts by running:

   ```bash
   python generate_tts_prompts.py
   ```

   This will create a `data/generated_tts_prompts.json` file with all the necessary TTS prompts for the application.

## Usage

### Running the Application

To start the museum bot application:

```bash
python app.py
```

The application will start a web server on `http://localhost:5001` by default.

### Web Interface

1. Open your web browser and navigate to `http://localhost:5001`
2. Select your preferred language (English or Chinese)
3. Use the interface to:
   - Navigate to different points of interest in the museum
   - Ask questions about exhibits
   - View the robot's current position on the map

### Hardware Integration

The application is designed to work with hardware components:
- Motor controllers for robot movement
- Ultrasonic sensors for obstacle detection
- Audio output for speech synthesis

For development purposes, the hardware drivers can run in simulation mode.

## Configuration

### Environment Variables

The application uses the following environment variable for configuration:

- `ALIBABA_API_KEY`: API key for Alibaba Cloud services (required for AI question answering and TTS)

### Data Files

The `data/raw_poi_data.json` file contains all the museum's point of interest information, including:
- Location coordinates
- Names and descriptions in multiple languages
- Custom TTS prompts

## Development

### Project Components

1. **app.py**: Main application orchestrator that initializes all components and starts the web server
2. **web.py**: Flask web server implementation with SocketIO for real-time communication
3. **navigation.py**: Implements A* pathfinding algorithm for robot navigation
4. **ai.py**: Integrates with Alibaba Dashscope API for question answering
5. **tts.py**: Manages text-to-speech functionality using Alibaba Dashscope
6. **driver.py**: Hardware abstraction layer for robot control

## License

This project is licensed under the WTFPL - see the [LICENSE](LICENSE) file for details.