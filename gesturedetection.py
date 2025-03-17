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

def lookforhands():
    """Main function to detect hands and gestures"""
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Publishing availability")
    topic = config.config['gesture']['topic'] + "/" + 'availability'
    payload = "online"
    config.client.publish(topic, payload, retain=True)
    
    for camera in config.config['frigate']['cameras']:
        pubinitial(camera)
    
    while True:
        for cameraname in config.numpersons:
            numcamerapeople = config.numpersons[cameraname]
            if numcamerapeople > 0:
                process_start_time = time.time()
                try:
                    use_double_take = config.should_use_double_take(cameraname)
                    detect_all_results = config.config['gesture'].get('detect_all_results', False)
                    
                    if use_double_take:
                        dt_start_time = time.time()
                        matches = getmatches(cameraname)
                        dt_time = time.time() - dt_start_time
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Double-Take processed in {dt_time:.3f}s")
                        
                        if should_process_result(matches) or detect_all_results:
                            person_name, _ = get_person_to_process(matches)
                            if not detect_all_results and not person_name:
                                print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: No match found, skipping gesture detection")
                                pubresults(cameraname, '', '')
                                continue
                        else:
                            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: No match and detect_all_results is False, skipping")
                            pubresults(cameraname, '', '')
                            continue
                    
                    img = getlatestimg(cameraname)
                    if img is not None:
                        gesture = gesturemodelfunctions.gesturemodelmatch(img)
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Gesture analysis result: '{gesture}'")
                        pubresults(cameraname, person_name or 'unknown', gesture)
                    else:
                        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Failed to get image")
                        pubresults(cameraname, '', '')
                    
                    total_process_time = time.time() - process_start_time
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Camera {cameraname}: Total processing time: {total_process_time:.3f}s")
                except Exception as e:
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error processing camera {cameraname}: {str(e)}")
            else:
                pubresults(cameraname, '', '')
        
        gc.collect()
        time.sleep(0.5)
