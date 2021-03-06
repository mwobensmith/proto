# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


# This class is used to wrap methods around the Sikuli API

import platform
import pyautogui
import numpy as np
from helpers.image_remove_noise import process_image_for_ocr
import pytesseract
import cv2
import time
import random
import logging
import os

try:
    import Image
except ImportError:
    from PIL import Image

pyautogui.FAILSAFE = False
DEFAULT_IMG_ACCURACY = 0.8
FIND_METHOD = cv2.TM_CCOEFF_NORMED
IMAGES = {}
DEBUG = True

logger = logging.getLogger(__name__)


def get_os():
    global logger
    current_system = platform.system()
    current_os = ''
    if current_system == "Windows":
        current_os = "win"
        pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files (x86)\\Tesseract-OCR\\tesseract'
    elif current_system == "Linux":
        current_os = "linux"
        pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'
    elif current_system == "Darwin":
        current_os = "osx"
        pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'
    else:
        logger.error("Iris does not yet support your current environment: " + current_system)

    return current_os


def get_platform():
    return platform.machine()


def get_module_dir():
    return os.path.realpath(os.path.split(__file__)[0] + "/../..")


CURRENT_PLATFORM = get_os()
PROJECT_BASE_PATH = get_module_dir()
for root, dirs, files in os.walk(PROJECT_BASE_PATH):
    for file_name in files:
        if file_name.endswith(".png"):
            if CURRENT_PLATFORM in root:
                IMAGES[file_name] = os.path.join(root, file_name)

'''
pyautogui.size() works correctly everywhere except Mac Retina
This technique works everywhere, so we'll use it instead
'''
screenWidth, screenHeight = pyautogui.screenshot().size


IMAGE_DEBUG_PATH = get_module_dir() + "/image_debug"
try:
    os.stat(IMAGE_DEBUG_PATH)
except:
    os.mkdir(IMAGE_DEBUG_PATH)
for debug_image_file in os.listdir(IMAGE_DEBUG_PATH):
    file_path = os.path.join(IMAGE_DEBUG_PATH, debug_image_file)
    try:
        if os.path.isfile(file_path):
            os.unlink(file_path)
    except Exception as e:
        continue

'''
Private function: Saves PIL input image for debug
'''


def _save_debug_image(search_for, search_in, res_coordinates):
    if DEBUG:
        w, h = search_for.shape[::-1]

        if isinstance(res_coordinates, list):
            for match_coordinates in res_coordinates:
                cv2.rectangle(search_in, (match_coordinates[0], match_coordinates[1]),
                              (match_coordinates[0] + w, match_coordinates[1] + h), [0, 0, 255], 2)
        else:
            cv2.rectangle(search_in, (res_coordinates[0], res_coordinates[1]),
                          (res_coordinates[0] + w, res_coordinates[1] + h), [0, 0, 255], 2)

        current_time = int(time.time())
        random_nr = random.randint(1, 51)
        cv2.imwrite(IMAGE_DEBUG_PATH + '/name_' + str(current_time) + '_' + str(random_nr) + '.png', search_in)


'''
Private function: Returns a screenshot from tuple (topx, topy, bottomx, bottomy)

Input : Region tuple (topx, topy, bottomx, bottomy)
Output : PIL screenshot image

Ex: _region_grabber(region=(0, 0, 500, 500)) 
'''


def _region_grabber(coordinates):
    x1 = coordinates[0]
    y1 = coordinates[1]
    width = coordinates[2] - x1
    height = coordinates[3] - y1
    grabbed_area = pyautogui.screenshot(region=(x1, y1, width, height))

    # Resize grabbed area to what pyautogui thinks is the correct screen size
    w, h = pyautogui.size()
    logger.debug("Screen size according to pyautogui.size(): %s,%s" % (w, h))
    logger.debug("Screen size according to pyautogui.screenshot().size: %s,%s" % (screenWidth, screenHeight))
    resized_area = grabbed_area.resize([w,h])
    return resized_area


'''
Private function: Search for needle in stack
'''


def _match_template(search_for, search_in, precision=DEFAULT_IMG_ACCURACY, search_multiple=False):
    img_rgb = np.array(search_in)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
    needle = cv2.imread(search_for, 0)

    res = cv2.matchTemplate(img_gray, needle, FIND_METHOD)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val < precision:
        return [-1, -1]
    else:
        _save_debug_image(needle, img_rgb, max_loc)
        return max_loc


def _match_template_multiple(search_for, search_in, precision=DEFAULT_IMG_ACCURACY, search_multiple=False,
                             threshold=0.7):
    img_rgb = np.array(search_in)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
    needle = cv2.imread(search_for, 0)

    res = cv2.matchTemplate(img_gray, needle, FIND_METHOD)
    w, h = needle.shape[::-1]
    points = []
    while True:
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if FIND_METHOD in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            top_left = min_loc
        else:
            top_left = max_loc

        if max_val > threshold:
            sx, sy = top_left
            for x in range(sx - w / 2, sx + w / 2):
                for y in range(sy - h / 2, sy + h / 2):
                    try:
                        res[y][x] = np.float32(-10000)
                    except IndexError:
                        pass
            new_match_point = (top_left[0], top_left[1])
            points.append(new_match_point)
        else:
            break

    _save_debug_image(needle, img_rgb, points)
    return points


'''
Private function: Search for an image on the entire screen.
    For searching in a certain area use _image_search_area

Input :
    image_path : Path to the searched for image.
    precision : OpenCv image search precision.

Output :
   Top left coordinates of the element if found as [x,y] or [-1,-1] if not.

'''


def _image_search(image_path, precision=DEFAULT_IMG_ACCURACY):
    in_region = _region_grabber(coordinates=(0, 0, screenWidth, screenHeight))
    return _match_template(image_path, in_region, precision)


'''
Private function: Search for multiple matches of image on the entire screen.

Input :
    image_path : Path to the searched for image.
    precision : OpenCv image search precision.

Output :
   Array of coordinates if found as [[x,y],[x,y]] or [] if not.

'''


def _image_search_multiple(image_path, precision=DEFAULT_IMG_ACCURACY):
    in_region = _region_grabber(coordinates=(0, 0, screenWidth, screenHeight))
    return _match_template_multiple(image_path, in_region, precision)


'''
Private function: Search for an image within an area

Input :
    image_path :  Path to the searched for image.
    x1 : Top left x area value.
    y1 : Top left y area value.
    x2 : Bottom right x area value.
    y2 : Bottom right y area value.
    precision : OpenCv image search precision.
    in_region : an already cached region, in this case x1,y1,x2,y2 will be ignored

Output :
    Top left coordinates of the element if found as [x,y] or [-1,-1] if not.
'''


def _image_search_area(image_path, x1, y1, x2, y2, precision=DEFAULT_IMG_ACCURACY, in_region=None):
    if in_region is None:
        in_region = _region_grabber(coordinates=(x1, y1, x2, y2))
    return _match_template(image_path, in_region, precision)


'''
Private function: Search for an image on entire screen continuously until it's found.

Input :
    image_path : Path to the searched for image.
    time_sample : Waiting time after failing to find the image .
    precision :  OpenCv image search precision.

Output :
     Top left coordinates of the element if found as [x,y] or [-1,-1] if not.

'''


def _image_search_loop(image_path, time_sample, attempts=5, precision=0.8):
    pos = _image_search(image_path, precision)
    tries = 0
    while (pos[0] == -1) and (tries < attempts):
        time.sleep(time_sample)
        pos = _image_search(image_path, precision)
        tries += 1
    return pos


'''
Private function: Search for an image on a region of the screen continuously until it's found.

Input :
    time : Waiting time after failing to find the image. 
    image_path :  Path to the searched for image.
    x1 : Top left x area value.
    y1 : Top left y area value.
    x2 : Bottom right x area value.
    y2 : Bottom right y area value.
    precision : OpenCv image search precision.
    in_region : An already cached region, in this case x1,y1,x2,y2 will be ignored

Output :
    Top left coordinates of the element if found as [x,y] or [-1,-1] if not.

'''


def _image_search_region_loop(image_path, time_sample, x1, y1, x2, y2, precision=DEFAULT_IMG_ACCURACY, in_region=None):
    pos = _image_search_area(image_path, x1, y1, x2, y2, precision, in_region)
    while pos[0] == -1:
        time.sleep(time_sample)
        pos = _image_search_area(image_path, x1, y1, x2, y2, precision, in_region)
    return pos


'''

Private function: Clicks on a image

input :
    image_path : Path to the clicked image ( only for width,height calculation)
    pos : Position of the top left corner of the image [x,y].
    action : button of the mouse to activate : "left" "right" "middle".
    time : Time taken for the mouse to move from where it was to the new position.
'''


def _click_image(image_path, pos, action, time_stamp):
    img = cv2.imread(image_path)
    height, width, channels = img.shape
    pyautogui.moveTo(pos[0] + width / 2, pos[1] + height / 2, time_stamp)
    pyautogui.click(button=action)


def _text_search_all(in_region=None):
    if in_region is None:
        in_region = _region_grabber(coordinates=(0, 0, screenWidth, screenHeight))

    tesseract_match_min_len = 12
    input_image = np.array(in_region)
    optimized_ocr_image = process_image_for_ocr(image_array=Image.fromarray(input_image))

    if DEBUG:
        cv2.imwrite(IMAGE_DEBUG_PATH + "/debug_ocr_ready.png", optimized_ocr_image)

    optimized_ocr_array = np.array(optimized_ocr_image)
    processed_data = pytesseract.image_to_data(Image.fromarray(optimized_ocr_array))

    final_data = []
    for line in processed_data.split("\n"):
        try:
            data = line.encode("ascii").split()
            if len(data) is tesseract_match_min_len:
                precision = int(data[10]) / float(100)
                new_match = {'x': data[6],
                             'y': data[7],
                             'width': data[8],
                             'height': data[9],
                             'precision': precision,
                             'value': data[11]
                             }
                final_data.append(new_match)
        except:
            continue

    return final_data


'''

Sikuli wrappers
- wait
- waitVanish
- click
- exists 
- find
- findAll
- type
- Key
- KeyModifier

'''


def wait(image_name, max_attempts=10, interval=0.5, precision=DEFAULT_IMG_ACCURACY):
    image_path = IMAGES[image_name]
    image_found = _image_search_loop(image_path, interval, max_attempts, precision)
    if (image_found[0] != -1) & (image_found[1] != -1):
        return True
    else:
        raise Exception


def waitVanish(image_name, max_attempts=10, interval=0.5, precision=DEFAULT_IMG_ACCURACY):
    global logger
    logger.debug("Wait vanish for: " + image_name)
    try:
        pattern_found = wait(image_name, 1)
    except:
        return True
    tries = 0
    while (pattern_found is True) and (tries < max_attempts):
        time.sleep(interval)
        try:
            pattern_found = wait(image_name, 1)
        except:
            pattern_found = False
        tries += 1

    if pattern_found is True:
        raise Exception
    else:
        return True


# @todo Search in regions for faster results
def click(image_name):
    global logger
    logger.debug("Try click on: " + image_name)
    image_path = IMAGES[image_name]
    pos = _image_search(image_path)
    if pos[0] != -1:
        _click_image(image_path, pos, "left", 0)
        time.sleep(1)
        return pos
    else:
        logger.debug("Image not found:", image_name)


def exists(image_name, interval):
    try:
        wait(image_name, 3, interval)
        return True
    except:
        return False


# @todo to take in consideration the number of screens
def get_screen():
    if DEBUG is True:
        pyautogui.displayMousePosition()
    return _region_grabber(coordinates=(0, 0, screenWidth, screenHeight))


def hover(x=0, y=0, duration=0.0, tween='linear', pause=None, image=None):
    if image is not None:
        pos = _image_search(image)
        if pos[0] != -1:
            pyautogui.moveTo(pos[0], pos[1])
    else:
        x = int(x)
        y = int(y)
        pyautogui.moveTo(x, y, duration, tween, pause)


def find(image_name):
    image_path = IMAGES[image_name]
    return _image_search(image_path)


def findAll(image_name):
    image_path = IMAGES[image_name]
    return _image_search_multiple(image_path)


# Obsolete, will be removed
"""
def typewrite(text, interval=0.02):
    logger.debug("Type: " + str(text))
    pyautogui.typewrite(text, interval)


def press(key):
    logger.debug("Press: " + key)
    pyautogui.keyDown(str(key))
    pyautogui.keyUp(str(key))


def hotkey_press(*args):
    pyautogui.hotkey(*args)
"""


def keyDown(key):
    pyautogui.keyDown(key)


def keyUp(key):
    pyautogui.keyUp(key)


def scroll(clicks):
    pyautogui.scroll(clicks)


def type(text=None, modifier=None, interval=0.02):
    global logger
    logger.debug("type method: ")
    if modifier == None:
        if isinstance(text, _key):
            logger.debug("Scenario 1: reserved key")
            logger.debug("Reserved key: %s" % text)
            if str(text) is str(Key.ENTER):
                pyautogui.typewrite(["enter"])
            else:
                pyautogui.keyDown(str(text))
                pyautogui.keyUp(str(text))
        else:
            logger.debug("Scenario 2: normal key or text block")
            logger.debug("Text: %s" % text)
            pyautogui.typewrite(text, interval)
    else:
        logger.debug("Scenario 3: combination of modifiers and other keys")
        modifier_keys = KeyModifier.get_active_modifiers(modifier)
        num_keys = len(modifier_keys)
        logger.debug("Modifiers (%s): %s " % (num_keys, ' '.join(modifier_keys)))
        logger.debug("text: %s" % text)
        if num_keys == 1:
            pyautogui.hotkey(modifier_keys[0], str(text))
        elif num_keys == 2:
            pyautogui.hotkey(modifier_keys[0], modifier_keys[1], str(text))
        else:
            logger.error("Returned key modifiers out of range")


class KeyModifier(object):
    SHIFT = 1 << 0  # 1
    CTRL = 1 << 1  # 2
    CMD = 1 << 2  # 4
    WIN = 1 << 2  # 4
    ALT = 1 << 3  # 8

    @staticmethod
    def get_active_modifiers(value):
        all_modifiers = [
            (KeyModifier.SHIFT, "shift"),
            (KeyModifier.CTRL, "ctrl")]

        if get_os() == "osx":
            all_modifiers.append((KeyModifier.CMD, "command"))
        else:
            # TODO: verify that Linux is same as Windows
            all_modifiers.append((KeyModifier.WIN, "win"))

        all_modifiers.append((KeyModifier.ALT, "alt"))

        active_modifiers = []
        for item in all_modifiers:
            if item[0] & value:
                active_modifiers.append(item[1])
        return active_modifiers


class _key(object):

    def __init__(self, label, reserved=True):
        self.value = label
        self.is_reserved = reserved

    def __str__(self):
        return self.value


class Key(object):
    SPACE = _key(" ")
    TAB = _key("tab")
    ENTER = _key("enter")
    LEFT = _key("left")
    RIGHT = _key("right")
    UP = _key("up")
    DOWN = _key("down")
    ESC = _key("esc")
    HOME = _key("home")
    END = _key("end")
    DELETE = _key("del")
    FN = _key("fn")
    F5 = _key("f5")
    F6 = _key("f6")
    F11 = _key("f11")


"""
Stub implementation, just to prevent tests from throwing an error
"""


class Pattern(object):

    def __init__(self, image_name):
        self.image = image_name

    def targetOffset(self, x, y):
        self.x_offset = x
        self.y_offset = y
        return self.image
