import threading
import mqtthandlers
import config
import gesturedetection
import time
import sys

def main():
    print("GestureSensor starting...")
    
    # Initialize configuration
    try:
        config.init()
        print("Configuration loaded successfully")
    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
        sys.exit(1)
    
    # Set up MQTT client
    config.client.on_connect = mqtthandlers.on_connect
    config.client.on_message = mqtthandlers.on_message
    config.client.on_publish = mqtthandlers.on_publish
    
    # Set up MQTT authentication if configured
    mqtthandlers.setup_mqtt_auth(config.client)
    
    # Connect to MQTT broker
    try:
        print(f"Connecting to MQTT broker at {config.config['mqtt']['host']}:{config.config['mqtt']['port']}...")
        config.client.connect(config.config['mqtt']['host'], config.config['mqtt']['port'], 60)
        print("Connected to MQTT broker")
    except Exception as e:
        print(f"Error connecting to MQTT broker: {str(e)}")
        sys.exit(1)
    
    # Start the gesture detection thread
    print("Starting gesture detection thread...")
    t1 = threading.Thread(target=gesturedetection.lookforhands)
    t1.daemon = True  # Make thread a daemon so it exits when main program exits
    t1.start()
    print("Gesture detection thread started")
    
    # Print configuration summary
    print("\nConfiguration Summary:")
    print(f"MQTT Broker: {config.config['mqtt']['host']}:{config.config['mqtt']['port']}")
    print(f"Frigate Server: {config.config['frigate']['host']}:{config.config['frigate']['port']}")
    print(f"Monitoring cameras: {', '.join(config.config['frigate']['cameras'])}")
    if 'double-take' in config.config:
        print(f"Double-Take Server: {config.config['double-take']['host']}:{config.config['double-take']['port']}")
        if 'cameras' in config.config['double-take']:
            print(f"Using face recognition for cameras: {', '.join(config.config['double-take']['cameras'])}")
        else:
            print("Using face recognition for all cameras")
    else:
        print("Face recognition disabled")
    
    print(f"Gesture detection settings: handsize={config.config['gesture']['handsize']}, " +
          f"confidence={config.config['gesture']['confidence']}")
    print(f"MQTT topic prefix: {config.config['gesture']['topic']}")
    
    if config.config['gesture']['allowed_persons']:
        print(f"Processing gestures only for: {', '.join(config.config['gesture']['allowed_persons'])}")
    else:
        print("Processing gestures for all detected people")
    
    print("\nGestureSensor running. Press Ctrl+C to exit.")
    
    # Start MQTT loop
    try:
        config.client.loop_forever()
    except KeyboardInterrupt:
        print("\nShutting down GestureSensor...")
        # Publish offline status before exiting
        topic = config.config['gesture']['topic'] + "/" + 'availability'
        config.client.publish(topic, "offline", retain=True)
        time.sleep(1)  # Give time for the message to be sent
        sys.exit(0)

if __name__ == "__main__":
    main()
