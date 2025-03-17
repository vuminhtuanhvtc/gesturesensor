import config
import requests
import cv2
import numpy as np
import urllib
import time
import json
import gesturemodelfunctions
import gc
import contextlib

def pubinitial(cameraname):
    """Publish an initial state for a camera with empty person and gesture"""
    topic = config.config['gesture']['topic'] + "/" + cameraname
    payload = {'person': '', 'gesture': ''}
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Publishing initial state for: {cameraname}")
    ret = config.client.publish(topic, json.dumps(payload), retain=True)
    config.sentpayload[cameraname] = payload

def pubresults(cameraname, name, gesture):
    """Publish detection results for a camera"""
    topic = config.config['gesture']['topic'] + "/" + cameraname
    payload = {'person': name, 'gesture': gesture}
    if config.sentpayload[cameraname] != payload:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Publishing to {topic}: {str(payload)}")
        ret = config.client.publish(topic, json.dumps(payload), retain=True)
        config.sentpayload[cameraname] = payload

def getmatches(cameraname):
    """Get face recognition matches from Double-Take"""
    if 'double-take' not in config.config:
        return None
        
    url = f"http://{config.config['double-take']['host']}:{config.config['double-take']['port']}/api/recognize"
    url += f"?url=http://{config.config['frigate']['host']}:{config.config['frigate']['port']}/api/{cameraname}/latest.jpg"
    url += f"&attempts=1&camera={cameraname}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting matches from Double-Take: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception while getting matches from Double-Take: {str(e)}")
        return None
    finally:
        if 'response' in locals():
            response.close()

def getlatestimg(cameraname):
    """Get the latest image from Frigate"""
    url = f"http://{config.config['frigate']['host']}:{config.config['frigate']['port']}/api/{cameraname}/latest.jpg"
    try:
        with contextlib.closing(urllib.request.urlopen(url)) as req:
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
        img = cv2.imdecode(arr, -1)
        return img
    except Exception as e:
        print(f"Exception while getting latest image from Frigate: {str(e)}")
        return None

def should_process_result(matches):
    """Check if results should be processed based on configuration"""
    # If no matches data, don't process
    if not matches:
        return False
        
    # If there's a match, always process
    if int(matches['counts']['match']) > 0:
        return True
    
    # Check if we should process all results
    detect_all_results = config.config['gesture'].get('detect_all_results', False)
    if detect_all_results:
        # Check if there's any detection
        if (int(matches['counts']['person']) > 0 or 
            int(matches['counts']['miss']) > 0 or 
            int(matches['counts']['unknown']) > 0):
            return True
    
    return False

def get_person_to_process(matches):
    """Find the most suitable person to process from recognition results"""
    if not matches:
        return None, None
        
    # First, check for matches
    if int(matches['counts']['match']) > 0:
        # Find the largest match that is allowed
        biggestmatchsize = 0
        biggestmatch = None
        
        for match in matches['matches']:
            if not config.is_person_allowed(match['name']):
                continue
                
            matchsize = match['box']['width'] * match['box']['height']
            if matchsize > biggestmatchsize:
                biggestmatchsize = matchsize
                biggestmatch = match
        
        if biggestmatch:
            return biggestmatch['name'], biggestmatch['box']
    
    # If no match or no allowed match, check for misses and unknowns
    detect_all_results = config.config['gesture'].get('detect_all_results', False)
    if detect_all_results:
        # Check for misses (recognized but not matched)
        if int(matches['counts']['miss']) > 0:
            for miss in matches['misses']:
                if not config.is_person_allowed(miss['name']):
                    continue
                return miss['name'], miss['box']
        
        # Check for unknowns
        if int(matches['counts']['unknown']) > 0:
            # Find the largest unknown
            biggestunknownsize = 0
            biggestunknown = None
            
            for unknown in matches['unknowns']:
                unknownsize = unknown['box']['width'] * unknown['box']['height']
                if unknownsize > biggestunknownsize:
                    biggestunknownsize = unknownsize
                    biggestunknown = unknown
            
            if biggestunknown:
                return "unknown", biggestunknown['box']
    
    return None, None

def lookforhands():
    """Main function to detect hands and gestures"""
    # Publish availability
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Publishing availability")
    topic = config.config['gesture']['topic'] + "/" + 'availability'
    payload = "online"
    ret = config.client.publish(topic, payload, retain=True)
    
    # Reset all cameras to initial state
    for camera in config.config['frigate']['cameras']:
        pubinitial(camera)
    
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Starting main loop - monitoring {len(config.config['frigate']['cameras'])} cameras")
    
    # Track previous states to avoid redundant logs
    previous_camera_states = {}
    for cameraname in config.numpersons:
        previous_camera_states[cameraname] = -1
    
    while True:
        for cameraname in config.numpersons:
            numcamerapeople = config.numpersons[cameraname]
            
            # Log only when the number of people changes
            if previous_camera_states[cameraname] != numcamerapeople:
                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: {numcamerapeople} people")
                previous_camera_states[cameraname] = numcamerapeople
            
            # Process only if people are detected
            if numcamerapeople > 0:
                process_start_time = time.time()
                try:
                    # Check if this camera should use Double-Take
                    use_double_take = config.should_use_double_take(cameraname)
                    
                    if use_double_take:
                        # Process through Double-Take for face recognition
                        dt_start_time = time.time()
                        matches = getmatches(cameraname)
                        dt_time = time.time() - dt_start_time
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Double-Take processed in {dt_time:.3f}s")
                        
                        # Check if we should process these results
                        if should_process_result(matches):
                            # Find a suitable person to process
                            person_name, person_box = get_person_to_process(matches)
                            
                            if person_name:
                                # Get the latest image and analyze gestures
                                img = getlatestimg(cameraname)
                                if img is not None:
                                    gesture = gesturemodelfunctions.gesturemodelmatch(img)
                                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Gesture analysis for {person_name}: '{gesture}'")
                                    pubresults(cameraname, person_name, gesture)
                                else:
                                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Failed to get image")
                            else:
                                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: No suitable person found")
                                pubresults(cameraname, '', '')
                        else:
                            pubresults(cameraname, '', '')
                    else:
                        # Direct image processing without face recognition
                        img = getlatestimg(cameraname)
                        if img is not None:
                            gesture = gesturemodelfunctions.gesturemodelmatch(img)
                            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Direct gesture analysis: '{gesture}'")
                            # Since we're not using face recognition, the person field is empty
                            pubresults(cameraname, '', gesture)
                        else:
                            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Failed to get image")
                            pubresults(cameraname, '', '')
                    
                    total_process_time = time.time() - process_start_time
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Total processing time: {total_process_time:.3f}s")
                except Exception as e:
                    total_process_time = time.time() - process_start_time
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error processing camera {cameraname} after {total_process_time:.3f}s: {str(e)}")
                    import traceback
                    traceback.print_exc()
            elif numcamerapeople == 0:
                # Reset the results when no people are detected
                pubresults(cameraname, '', '')
        
        gc.collect()
        time.sleep(0.5)
