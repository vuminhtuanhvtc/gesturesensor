import config

def on_publish(client, userdata, result):
    """Callback when a message is published"""
    pass

def on_message(client, userdata, msg):
    """Callback when a message is received"""
    try:
        # Extract camera name from topic
        topic_parts = msg.topic.split("/")
        if len(topic_parts) >= 2:
            camera_name = topic_parts[1]
            
            # Update number of persons for this camera
            try:
                num_persons = int(msg.payload)
                config.numpersons[camera_name] = num_persons
            except (ValueError, TypeError):
                config.numpersons[camera_name] = 0
                print(f"Invalid payload for {msg.topic}: {msg.payload}")
        else:
            print(f"Unexpected topic format: {msg.topic}")
    except Exception as e:
        print(f"Error processing MQTT message: {str(e)}")

def on_connect(client, userdata, flags, rc):
    """Callback when connection to MQTT broker is established"""
    print(f"Connected to MQTT broker with result code {rc}")
    
    # Subscribe to person detection topics for all configured cameras
    for camera in config.config['frigate']['cameras']:
        topic = f"frigate/{camera}/person"
        client.subscribe(topic)
        print(f"Subscribed to {topic}")

def setup_mqtt_auth(client):
    """Set up MQTT authentication if configured"""
    mqtt_config = config.config.get('mqtt', {})
    if 'user' in mqtt_config and 'password' in mqtt_config:
        client.username_pw_set(mqtt_config['user'], mqtt_config['password'])
        print(f"MQTT authentication configured with user: {mqtt_config['user']}")
