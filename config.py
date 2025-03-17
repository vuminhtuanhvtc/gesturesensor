import yaml
import paho.mqtt.client as mqtt

config = ""
numpersons = {}
sentpayload = {}
client = mqtt.Client()

def init():
    global config
    try:
        with open('/config/config.yml', 'r') as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        with open('config.yml', 'r') as file:
            config = yaml.safe_load(file)
    
    # Apply default values for missing configurations
    _apply_defaults()
    
    # Initialize camera states
    _init_camera_states()

def _apply_defaults():
    """Apply default values for missing configurations"""
    # Ensure MQTT config exists
    if 'mqtt' not in config:
        config['mqtt'] = {'host': 'localhost', 'port': 1883}
    
    # Ensure Frigate config exists
    if 'frigate' not in config:
        config['frigate'] = {'host': 'localhost', 'port': 5000}
    
    # Ensure gesture config exists with defaults
    if 'gesture' not in config:
        config['gesture'] = {}
    
    gesture_defaults = {
        'handsize': 9000,
        'confidence': 0.75,
        'topic': 'gestures',
        'detect_all_results': False,
        'allowed_persons': []
    }
    
    # Apply defaults to gesture config
    for key, value in gesture_defaults.items():
        if key not in config['gesture']:
            config['gesture'][key] = value

def _init_camera_states():
    """Initialize the state for each camera"""
    # If no cameras specified, fetch from Frigate API
    if 'cameras' not in config['frigate'] or not config['frigate']['cameras']:
        import requests
        try:
            frigate_url = f"http://{config['frigate']['host']}:{config['frigate']['port']}/api/config"
            response = requests.get(frigate_url, timeout=10)
            if response.status_code == 200:
                frigate_config = response.json()
                config['frigate']['cameras'] = list(frigate_config.get('cameras', {}).keys())
                print(f"Retrieved cameras from Frigate: {config['frigate']['cameras']}")
            else:
                print(f"Failed to retrieve cameras from Frigate API: {response.status_code}")
                config['frigate']['cameras'] = []
        except Exception as e:
            print(f"Error connecting to Frigate API: {str(e)}")
            config['frigate']['cameras'] = []
    
    # Initialize camera states
    for camera in config['frigate']['cameras']:
        numpersons[camera] = 0
        sentpayload[camera] = ""

def should_use_double_take(camera_name):
    """Check if a camera should use Double-Take for face recognition"""
    # If Double-Take is not configured, don't use it
    if 'double-take' not in config:
        return False
    
    # If no cameras specified for Double-Take, use it for all cameras
    if 'cameras' not in config['double-take']:
        return True
    
    # If cameras are specified, check if this camera is in the list
    return camera_name in config['double-take']['cameras']

def is_person_allowed(person_name):
    """Check if a person is allowed based on the configuration"""
    allowed_persons = config['gesture'].get('allowed_persons', [])
    # If the list is empty, allow all people
    if not allowed_persons:
        return True
    # If the list is not empty, check if the person is in the list
    return person_name in allowed_persons
