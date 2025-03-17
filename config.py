import yaml
import paho.mqtt.client as mqtt
import os
import time

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
    
    # Create storage directory if enabled
    if config['storage']['enabled']:
        os.makedirs(config['storage']['path'], exist_ok=True)

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
        'allowed_persons': []
    }
    
    for key, value in gesture_defaults.items():
        if key not in config['gesture']:
            config['gesture'][key] = value
    
    # Ensure storage config exists with defaults
    if 'storage' not in config:
        config['storage'] = {}
    
    storage_defaults = {
        'enabled': True,
        'path': 'storage',
        'retention_days': 1,
        'save_annotated': True
    }
    
    for key, value in storage_defaults.items():
        if key not in config['storage']:
            config['storage'][key] = value
    
    # Ensure double-take config exists and move detect_all_results to double-take
    if 'double-take' in config and 'detect_all_results' not in config['double-take']:
        config['double-take']['detect_all_results'] = False

def _init_camera_states():
    """Initialize the state for each camera"""
    import requests
    if 'cameras' not in config['frigate'] or not config['frigate']['cameras']:
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
    
    for camera in config['frigate']['cameras']:
        numpersons[camera] = 0
        sentpayload[camera] = ""

def should_use_double_take(camera_name):
    """Check if a camera should use Double-Take for face recognition"""
    if 'double-take' not in config:
        return False
    if 'cameras' not in config['double-take']:
        return True
    return camera_name in config['double-take']['cameras']

def detect_all_results():
    """Check if all images should be analyzed regardless of Double-Take results"""
    return config.get('double-take', {}).get('detect_all_results', False)

def is_person_allowed(person_name):
    """Check if a person is allowed based on the configuration"""
    allowed_persons = config['gesture'].get('allowed_persons', [])
    if not allowed_persons:
        return True
    return person_name in allowed_persons

def cleanup_old_images():
    """Clean up old images based on retention policy"""
    if not config['storage']['enabled'] or config['storage']['retention_days'] <= 0:
        return  # No cleanup needed if storage disabled or retention is infinite
        
    storage_path = config['storage']['path']
    retention_seconds = config['storage']['retention_days'] * 24 * 60 * 60
    current_time = time.time()
    
    try:
        for filename in os.listdir(storage_path):
            file_path = os.path.join(storage_path, filename)
            # Skip directories and non-image files
            if os.path.isdir(file_path) or not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
                
            # Check file age
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > retention_seconds:
                os.remove(file_path)
                print(f"Removed old image: {filename}")
    except Exception as e:
        print(f"Error during image cleanup: {str(e)}")
