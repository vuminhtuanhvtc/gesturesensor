# GestureSensor

GestureSensor works with [Frigate](https://frigate.video/) to detect hand gestures in your camera feeds. It can also integrate with [Double-Take](https://github.com/jakowenko/double-take) for face recognition, allowing you to associate detected gestures with specific people.

## Features

- Detect hand gestures from Frigate camera feeds
- Optionally integrate with Double-Take for face recognition
- Publish detailed detection results to MQTT including:
  - Process ID
  - Person identification
  - Gesture detected
  - Processing duration
  - Double-Take results
  - Hand detection coordinates
- Store annotated images for debugging and review
- Configure which cameras to monitor
- Selective processing based on recognized individuals
- Customizable gesture detection parameters

## How It Works

1. GestureSensor connects to your Frigate instance via MQTT to receive person detection events.
2. When a person is detected, it analyzes the camera feed for hand gestures using [MediaPipe](https://google.github.io/mediapipe/).
3. If Double-Take integration is enabled, it first checks for face matches before processing gestures.
4. By default, gestures are only analyzed if Double-Take finds a match.
5. If `detect_all_results` is enabled in the Double-Take configuration, GestureSensor will process all images regardless of Double-Take's recognition result.
6. Results are published to MQTT for use with home automation systems like Home Assistant.
7. Optionally, annotated images with bounding boxes showing the detected gestures are saved to a storage directory.

Supported gestures include:
- Forward
- Stop
- Up
- Land
- Down
- Back
- Left
- Right

See [supportedgestures.jpg](./supportedgestures.jpg) for visual examples.

## Requirements

- MQTT broker (with or without authentication)
- Frigate installed and configured to publish events to MQTT
- Optional: Double-Take for face recognition
- Docker (recommended) or Python 3.8+

## Configuration

GestureSensor uses a YAML configuration file. The basic configuration is simple, while advanced options are available for more specific needs.

### Basic Configuration

The minimal configuration only requires MQTT broker and Frigate details:

```yaml
mqtt:
  host: localhost
  port: 1883
  user: mqtt_username  # Optional
  password: mqtt_password  # Optional

frigate:
  host: localhost
  port: 5000
```

With this configuration, GestureSensor will:
- Connect to the specified MQTT broker
- Monitor all cameras configured in Frigate
- Process gestures for any detected person
- Use default gesture detection settings
- Store annotated images in the "storage" directory with 1-day retention

### Advanced Configuration

For more control, you can use these additional options:

```yaml
mqtt:
  host: localhost
  port: 1883
  user: mqtt_username
  password: mqtt_password

frigate:
  host: localhost
  port: 5000
  cameras:  # Optional: specify which cameras to monitor
    - camera1
    - camera2

double-take:  # Optional: enable face recognition
  host: localhost
  port: 3000
  cameras:  # Optional: specify which cameras should use face recognition
    - camera1
  detect_all_results: false  # If true, process all images regardless of Double-Take's recognition result

gesture:  # Optional: customize gesture detection
  handsize: 9000  # Minimum hand size in pixels
  confidence: 0.75  # Confidence threshold for gesture detection
  topic: gestures  # MQTT topic prefix
  allowed_persons:  # Empty list means process all people
    - person1
    - person2
    
storage:  # Optional: customize image storage
  enabled: true  # Set to false to disable image storage
  path: storage  # Directory where images will be stored
  retention_days: 1  # Number of days to keep images, set to 0 for permanent storage
  save_annotated: true  # Save images with gesture annotations
```

### Configuration Options Explained

#### MQTT
- `host`: MQTT broker address
- `port`: MQTT broker port
- `user`: Username for MQTT authentication (optional)
- `password`: Password for MQTT authentication (optional)

#### Frigate
- `host`: Frigate server address
- `port`: Frigate API port
- `cameras`: List of cameras to monitor (optional, defaults to all cameras)

#### Double-Take
- `host`: Double-Take server address
- `port`: Double-Take API port
- `cameras`: List of cameras that should use face recognition (optional, defaults to all cameras)
- `detect_all_results`: When true, process all images regardless of face recognition result

#### Gesture
- `handsize`: Minimum hand size in pixels for detection (default: 9000)
- `confidence`: Confidence threshold for gesture classification (default: 0.75)
- `topic`: MQTT topic prefix for publishing results (default: gestures)
- `allowed_persons`: List of person names to process (empty list means process all people)

#### Storage
- `enabled`: Enable or disable image storage (default: true)
- `path`: Directory where images will be stored (default: storage)
- `retention_days`: Number of days to keep images, set to 0 for permanent storage (default: 1)
- `save_annotated`: Save images with gesture annotations (default: true)

## Running with Docker

Build the Docker image:

```bash
docker build -t gesturesensor .
```

Run with Docker Compose:

```bash
docker-compose up -d
```

## MQTT Payload Format

GestureSensor publishes detection results in JSON format with the following structure:

```json
{
  "id": "1616423898123",
  "person": "john",
  "gesture": "Stop",
  "timestamp": 1616423898,
  "camera": "camera1",
  "duration": 0.532,
  "double_take": {
    "used": true,
    "results": {
      "results": [
        {
          "match_found": true,
          "match_name": "john",
          "match_confidence": 0.92
        }
      ]
    }
  },
  "hand_detection": {
    "x": 320,
    "y": 240,
    "width": 120,
    "height": 140,
    "area": 16800,
    "confidence": 0.87
  }
}
```

## Home Assistant Integration

You can integrate GestureSensor with Home Assistant using MQTT sensors. Here's an example configuration:

```yaml
mqtt:
  sensor:
    - name: "Camera Gesture"
      unique_id: camera_gesture
      state_topic: "gestures/camera1"
      availability:
        - topic: "gestures/availability"
      value_template: "{{ value_json.gesture }}"
      json_attributes_topic: "gestures/camera1"
      json_attributes_template: "{{ value_json | tojson }}"
```

This creates a sensor with the current gesture as its state and additional attributes for all the detection data.

You can then create automations that trigger based on specific gestures or people.
