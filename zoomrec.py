import logging
import os
import random
import schedule
import time
import atexit
import requests
import re
import pyautogui
from signal import SIGQUIT, SIGKILL
from subprocess import Popen, PIPE, DEVNULL
from threading import Thread
from csv import DictReader
from psutil import process_iter, NoSuchProcess, AccessDenied, ZombieProcess
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

global ONGOING_MEETING
global VIDEO_PANEL_HIDED
global MEETING_DESCRIPTION

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                    level=logging.INFO)

# Turn DEBUG on:
#   - screenshot on error
#   - record joining
#   - do not exit container on error
DEBUG = os.getenv('DEBUG') == 'True'
STDOUT = PIPE if DEBUG else DEVNULL

# Disable failsafe
pyautogui.FAILSAFE = False

# Display size
global WIDTH, HEIGHT
WIDTH, HEIGHT = pyautogui.size()

# Get vars
BASE_PATH = os.getenv('HOME')
CSV_PATH = os.path.join(BASE_PATH, "meetings.csv")
IMG_PATH = os.path.join(BASE_PATH, "img")
REC_PATH = os.path.join(BASE_PATH, "recordings")
AUDIO_PATH = os.path.join(BASE_PATH, "audio")

TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"
CSV_DELIMITER = ';'

ONGOING_MEETING = False
VIDEO_PANEL_HIDED = False


# Check continuously if meeting has ended
class BackgroundThread:

    def __init__(self, interval=10):
        # Set running state
        self._running = True
        # Sleep interval between
        self.interval = interval

        thread = Thread(target=self.run, args=())
        # Daemonize thread
        thread.daemon = True
        # Start the execution
        thread.start()

    def terminate(self):
        logging.info("BackgroundThread: terminated")
        self._running = False

    def run(self):
        global ONGOING_MEETING
        ONGOING_MEETING = True

        logging.info("BackgroundThread: started")
        while self._running and ONGOING_MEETING:
            # Check if recording
            if (pyautogui.locateCenterOnScreen(os.path.join(
                    IMG_PATH, 'meeting_is_being_recorded.png'),
                                               confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("This meeting is being recorded..")
                try:
                    x, y = pyautogui.locateCenterOnScreen(os.path.join(
                        IMG_PATH, 'got_it.png'),
                                                          confidence=0.9)
                    pyautogui.click(x, y)
                    logging.info("Accepted recording..")
                except TypeError:
                    logging.error("Could not accept recording!")

            # Check if ended
            if (pyautogui.locateOnScreen(os.path.join(
                    IMG_PATH, 'meeting_ended_by_host_1.png'),
                                         confidence=0.9) is not None or
                    pyautogui.locateOnScreen(os.path.join(
                        IMG_PATH, 'meeting_ended_by_host_2.png'),
                                             confidence=0.9) is not None):
                ONGOING_MEETING = False
                logging.info("Meeting ended by host..")
            time.sleep(self.interval)


# Check continuously if screen sharing is active
class HideViewOptionsThread:

    def __init__(self, interval=10):
        # Set running state
        self._running = True
        # Sleep interval between
        self.interval = interval

        thread = Thread(target=self.run, args=())
        # Daemonize thread
        thread.daemon = True
        # Start the execution
        thread.start()

    def terminate(self):
        logging.info("HideViewOptionsThread: terminated")
        self._running = False

    def run(self):
        global VIDEO_PANEL_HIDED
        logging.info("HideViewOptionsThread: started")
        while self._running and ONGOING_MEETING:
            # Check if host is sharing poll results
            if (pyautogui.locateCenterOnScreen(os.path.join(
                    IMG_PATH, 'host_is_sharing_poll_results.png'),
                                               confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("Host is sharing poll results..")
                try:
                    x, y = pyautogui.locateCenterOnScreen(os.path.join(
                        IMG_PATH, 'host_is_sharing_poll_results.png'),
                                                          confidence=0.9)
                    pyautogui.click(x, y)
                    try:
                        x, y = pyautogui.locateCenterOnScreen(os.path.join(
                            IMG_PATH, 'exit.png'),
                                                              confidence=0.9)
                        pyautogui.click(x, y)
                        logging.info("Closed poll results window..")
                    except TypeError:
                        logging.error("Could not exit poll results window!")
                except TypeError:
                    logging.error("Could not find poll results window anymore!")

            # Check if view options available
            if pyautogui.locateCenterOnScreen(
                    os.path.join(IMG_PATH, 'you_are_viewing.png'),
                    confidence=0.9) is None or pyautogui.locateOnScreen(
                        os.path.join(IMG_PATH, 'view_options.png'),
                        confidence=0.9) is None:
                VIDEO_PANEL_HIDED = False

            elif not VIDEO_PANEL_HIDED:
                logging.info("Screen sharing active..")
                try:
                    x, y = pyautogui.locateCenterOnScreen(os.path.join(
                        IMG_PATH, 'view_options.png'),
                                                          confidence=0.9)
                    pyautogui.click(x, y)
                    time.sleep(1)
                    # Hide video panel
                    if pyautogui.locateOnScreen(os.path.join(
                            IMG_PATH, 'show_video_panel.png'),
                                                confidence=0.9) is not None:
                        # Leave 'Show video panel' and move mouse from screen
                        pyautogui.click(int(WIDTH / 2), int(HEIGHT / 2))
                        pyautogui.moveTo(10, int(HEIGHT * 0.05))
                        VIDEO_PANEL_HIDED = True
                    else:
                        try:
                            x, y = pyautogui.locateCenterOnScreen(
                                os.path.join(IMG_PATH, 'hide_video_panel.png'),
                                confidence=0.9)
                            pyautogui.click(x, y)
                            # Move mouse from screen
                            pyautogui.moveTo(10, int(HEIGHT * 0.05))
                            VIDEO_PANEL_HIDED = True
                        except TypeError:
                            logging.error("Could not hide video panel!")
                except TypeError:
                    logging.error("Could not find view options!")
            time.sleep(self.interval)


def get_name():
    display_name = os.getenv('DISPLAY_NAME')
    if display_name is None or len(display_name) < 3:
        NAME_LIST = [
            'iPhone', 'iPad', 'Macbook', 'Desktop', 'Huawei', 'Mobile', 'PC',
            'Windows', 'Home', 'MyPC', 'Computer', 'Android'
        ]
        display_name = random.choice(NAME_LIST)
    return display_name


def send_telegram_message(text):
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
    telegram_retries = 5

    if telegram_token is None:
        logging.warning(
            "Telegram token is missing. No Telegram messages will be send!")
        return

    if telegram_chat_id is None:
        logging.warning(
            "Telegram chat_id is missing. No Telegram messages will be send!")
        return

    if len(telegram_token) < 3 or len(telegram_chat_id) < 3:
        logging.warning(
            "Telegram token or chat_id missing. No Telegram messages will be send!"
        )
        return

    url_req = f"https://api.telegram.org/bot{telegram_token}/sendMessage?chat_id={telegram_chat_id}&text={text}"

    tries = 0
    done = False
    while not done:
        results = requests.get(url_req)
        results = results.json()
        done = 'ok' in results and results['ok']
        tries += 1
        if not done and tries < telegram_retries:
            logging.error(
                "Sending Telegram message failed, retrying in 5 seconds...")
            time.sleep(5)
        if not done and tries >= telegram_retries:
            logging.error(
                f"Sending Telegram message failed {tries} times, please check your credentials!"
            )
            done = True


def check_connecting(zoom_pid, start_date, duration):
    logging.info("Check if connecting..")
    checks = 0
    connecting = False

    # Check if connecting
    if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'connecting.png'),
                                      confidence=0.9) is not None:
        connecting = True
        logging.info("Connecting..")

    # Wait while connecting
    # Exit when meeting ends after time
    while connecting:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom_pid), SIGQUIT)
            return

        if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                       'connecting.png'),
                                          confidence=0.9,
                                          minSearchTime=2) is None:
            logging.info("Maybe not connecting anymore..")
            checks += 1
            if checks >= 2:
                connecting = False
                logging.info("Not connecting anymore..")
                return
        time.sleep(2)


def check_error():
    # Sometimes invalid id error is displayed
    if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                   'invalid_meeting_id.png'),
                                      confidence=0.9) is not None:
        logging.warning("Maybe a invalid meeting id was inserted..")
        left = False
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'leave.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
            left = True
        except TypeError:
            # Valid id
            logging.info("Valid meeting id!")

        if not left:
            return True

        if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                       'join_meeting.png'),
                                          confidence=0.9) is not None:
            logging.error("Invalid meeting id!")
            return False
    if pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'authorized_attendees_only.png'),
                                      confidence=0.9) is not None:
        logging.error("This meeting is for authorized attendees only!")
        return False

    return True


def find_process_id_by_name(process_name):
    list_of_process_objects = []
    # Iterate over the all the running process
    for proc in process_iter():
        try:
            p_info = proc.as_dict(attrs=['pid', 'name', 'cmdline'])
            # Check if process name contains the given name string.
            if process_name.lower() in p_info['name'].lower():
                list_of_process_objects.append(p_info)
        except (NoSuchProcess, AccessDenied, ZombieProcess) as e:
            logging.error(e)
    return list_of_process_objects


def exit_process_by_name(name):
    list_of_process_ids = find_process_id_by_name(name)
    if len(list_of_process_ids) > 0:
        logging.info(name + " process exists | killing..")
        for elem in list_of_process_ids:
            process_id = elem['pid']
            try:
                os.kill(process_id, SIGKILL)
            except Exception as ex:
                logging.error("Could not terminate " + name + "[" +
                              str(process_id) + "]: " + str(ex))


def show_toolbars():
    logging.info("Show toolbars..")
    # Move mouse to show toolbars
    center_x = int(WIDTH / 2)
    center_y = int(HEIGHT / 2)

    # center
    pyautogui.moveTo(center_x, center_y)

    # right
    pyautogui.moveTo(center_x + 3, center_y, duration=0.2)

    # left
    pyautogui.moveTo(center_x - 3, center_y, duration=0.2)


def unmute():
    try:
        show_toolbars()
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'unmute.png'),
                                              confidence=0.9)
        pyautogui.click(x, y)
        return True
    except TypeError:
        logging.error("Could not unmute!")
        if DEBUG:
            pyautogui.screenshot((os.path.join(
                REC_PATH, f"{time.strftime(TIME_FORMAT)}-{MEETING_DESCRIPTION}")
                                  + "_unmute_error.png"))

        return False


def mute():
    try:
        show_toolbars()
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'mute.png'),
                                              confidence=0.9)
        pyautogui.click(x, y)
        return True
    except TypeError:
        logging.error("Could not mute!")
        if DEBUG:
            pyautogui.screenshot((os.path.join(
                REC_PATH, f"{time.strftime(TIME_FORMAT)}-{MEETING_DESCRIPTION}")
                                  + "_mute_error.png"))

        return False


def join(meet_id, meet_pw, duration, description):
    global VIDEO_PANEL_HIDED
    global MEETING_DESCRIPTION
    MEETING_DESCRIPTION = description

    ffmpeg_debug = None

    logging.info("Join meeting: " + MEETING_DESCRIPTION)

    if DEBUG:
        # Start recording
        resolution = str(WIDTH) + 'x' + str(HEIGHT)
        disp = os.getenv('DISPLAY')

        logging.info("Start recording..")

        filename = os.path.join(REC_PATH, time.strftime(
            TIME_FORMAT)) + "-" + MEETING_DESCRIPTION + "-JOIN.mkv"

        # Recording with ffmpeg
        command = "ffmpeg"
        command += " -nostats -loglevel error"
        ## Audio
        command += " -f pulse -ac 2 -i 1"
        ## Video
        command += " -f x11grab"
        command += " -draw_mouse 0"
        command += " -framerate 25"
        command += " -s " + resolution
        command += " -i " + disp
        #command += " -acodec pcm_s16le"
        command += " -c:v libx264rgb"
        command += " -crf 0"
        command += " -preset ultrafast"
        command += " "
        command += filename

        ffmpeg_debug = Popen(command,
                             stdout=STDOUT,
                             shell=True,
                             preexec_fn=os.setsid)
        atexit.register(os.killpg, os.getpgid(ffmpeg_debug.pid), SIGQUIT)

    # Exit Zoom if running
    exit_process_by_name("zoom")

    if meet_id.startswith('https://'):
        try:
            url = urlparse(meet_id)
            query = parse_qs(url.query)
            meet_pw = query.get("pwd")[0]
            meet_id = url.path.rsplit('/', 1)[-1]
        except Exception:
            logging.error("Invalid meeting url! Abort..", meet_id)
            return

    # Validate meeting id
    #   - The meeting ID can be a 10 or 11-digit number.
    #   - The 11-digit number is used for instant, scheduled or recurring meetings.
    #   - The 10-digit number is used for Personal Meeting IDs.
    #   - Meetings scheduled prior to April 12, 2020 may be 9-digits long.
    if bool(re.match("(\d){11}", meet_id)) or \
            bool(re.match("(\d){10}", meet_id)) or \
            bool(re.match("(\d){9}", meet_id)):
        logging.info("Valid meeting id! Join meeting..")
    else:
        logging.error("Invalid meeting id! Abort..", meet_id)
        return

    display_name = get_name()

    # Start Zoom and join meeting
    zoom = Popen(f'xdg-open "zoommtg://zoom.us/join?action=join&confno=' +
                 meet_id + '&pwd=' + meet_pw + '&uname=' + display_name + '"',
                 stdout=STDOUT,
                 shell=True,
                 preexec_fn=os.setsid)

    # Wait for Zoom is started
    list_of_process_ids = get_active_meeting()
    while len(list_of_process_ids) <= 0:
        logging.info("No Zoom process found!")
        list_of_process_ids = get_active_meeting()
        time.sleep(3)

    logging.info("Zoom started!")

    start_date = datetime.now()

    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    if not check_error():
        send_telegram_message(
            "Failed to join meeting {}!".format(MEETING_DESCRIPTION))
        logging.error("Failed to join meeting {}!".format(MEETING_DESCRIPTION))
        os.killpg(os.getpgid(zoom.pid), SIGQUIT)
        if DEBUG and ffmpeg_debug is not None:
            # Close ffmpeg
            os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
            atexit.unregister(os.killpg)
        return

    # Check if meeting is started by host
    logging.info("Check if meeting is started by host..")
    check_periods = 0
    meeting_started = True

    # Check if waiting for host
    if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                   'wait_for_host.png'),
                                      confidence=0.9,
                                      minSearchTime=4) is not None:
        meeting_started = False
        logging.info("Please wait for the host to start this meeting.")

    # Wait for the host to start this meeting
    # Exit when meeting ends after time
    while not meeting_started:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom.pid), SIGQUIT)
            if DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
                atexit.unregister(os.killpg)
            return

        if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                       'wait_for_host.png'),
                                          confidence=0.9) is None:
            logging.info("Maybe meeting was started now.")
            check_periods += 1
            if check_periods >= 2:
                meeting_started = True
                logging.info("Meeting started by host.")
                break
        time.sleep(2)

    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    # Check if in waiting room
    check_periods = 0
    waiting_room = False

    # Check if joined into waiting room
    logging.info("Check if joined into waiting room..")
    if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                   'waiting_room.png'),
                                      confidence=0.9,
                                      minSearchTime=5) is not None:
        waiting_room = True
        logging.info("Please wait, the meeting host will let you in soon..")

    # Wait while host will let you in
    # Exit when meeting ends after time
    while waiting_room:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom.pid), SIGQUIT)
            if DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
                atexit.unregister(os.killpg)
            return

        if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                       'waiting_room.png'),
                                          confidence=0.9) is None:
            logging.info("Maybe no longer in the waiting room..")
            check_periods += 1
            if check_periods >= 2:
                logging.info("No longer in the waiting room..")
                break
        time.sleep(2)

    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    in_meeting = False
    # Check if 'Leave' is shown
    if pyautogui.locateCenterOnScreen(
            os.path.join(IMG_PATH, 'leave.png'), confidence=0.9,
            minSearchTime=3) is not None or pyautogui.locateCenterOnScreen(
                os.path.join(IMG_PATH, 'view.png'),
                confidence=0.9,
                minSearchTime=3) is not None:
        in_meeting = True

    # Wait until 'Leave' is shown
    # Exit when meeting ends after time
    # Exit when attempts <= 3
    attempts = 0
    while not in_meeting and attempts <= 3:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom.pid), SIGQUIT)
            if DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
                atexit.unregister(os.killpg)
            return

        show_toolbars()
        if pyautogui.locateCenterOnScreen(
                os.path.join(IMG_PATH, 'leave.png'),
                confidence=0.9,
                minSearchTime=2) is not None or pyautogui.locateCenterOnScreen(
                    os.path.join(IMG_PATH, 'view.png'),
                    confidence=0.9,
                    minSearchTime=2):
            in_meeting = True
            break
        else:
            logging.info("Zoom not ready yet!")
            attempts += 1

    if not in_meeting or attempts >= 3:
        logging.error("Can not determine if already in meeting! Exit!")
        os.killpg(os.getpgid(zoom.pid), SIGQUIT)
        if DEBUG:
            os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
            atexit.unregister(os.killpg)
        join(meet_id, meet_pw, duration, description)
        return

    # Meeting joined
    logging.info("Joined meeting..")

    # Check if recording warning is shown at the beginning
    if (pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'meeting_is_being_recorded.png'),
                                       confidence=0.9,
                                       minSearchTime=2) is not None):
        logging.info("This meeting is being recorded..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'got_it.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
            logging.info("Accepted recording..")
        except TypeError:
            logging.error("Could not accept recording!")

    # Check if host is sharing poll results at the beginning
    if (pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'host_is_sharing_poll_results.png'),
                                       confidence=0.9,
                                       minSearchTime=2) is not None):
        logging.info("Host is sharing poll results..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'host_is_sharing_poll_results.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
            try:
                x, y = pyautogui.locateCenterOnScreen(os.path.join(
                    IMG_PATH, 'exit.png'),
                                                      confidence=0.9)
                pyautogui.click(x, y)
                logging.info("Closed poll results window..")
            except TypeError:
                logging.error("Could not exit poll results window!")
                if DEBUG:
                    pyautogui.screenshot(
                        os.path.join(
                            REC_PATH,
                            time.strftime(TIME_FORMAT) + "-" +
                            MEETING_DESCRIPTION) +
                        "_close_poll_results_error.png")
        except TypeError:
            logging.error("Could not find poll results window anymore!")
            if DEBUG:
                pyautogui.screenshot(
                    os.path.join(
                        REC_PATH,
                        time.strftime(TIME_FORMAT) + "-" +
                        MEETING_DESCRIPTION) + "_find_poll_results_error.png")

    # Start BackgroundThread
    bg_thread = BackgroundThread()

    # State: Already connected to computer audio
    show_toolbars()
    if pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH, 'unmute.png'),
                                      confidence=0.9,
                                      minSearchTime=3) is not None:
        logging.info("Already connected to computer audio..")
    else:
        logging.error("Not connected to computer audio! Exit!")
        os.killpg(os.getpgid(zoom.pid), SIGQUIT)
        bg_thread.terminate()
        if DEBUG:
            os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
            atexit.unregister(os.killpg)
        join(meet_id, meet_pw, duration, description)
        return

    # 'Say' something if path available (mounted)
    if os.path.exists(AUDIO_PATH):
        play_audio()

    time.sleep(2)
    logging.info("Enter fullscreen..")
    show_toolbars()
    try:
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'view.png'),
                                              confidence=0.9)
        pyautogui.click(x, y)
    except TypeError:
        logging.error("Could not find view!")
        if DEBUG:
            pyautogui.screenshot(
                os.path.join(
                    REC_PATH,
                    time.strftime(TIME_FORMAT) + "-" + MEETING_DESCRIPTION) +
                "_view_error.png")

    time.sleep(2)
    fullscreen = False
    try:
        x, y = pyautogui.locateCenterOnScreen(os.path.join(
            IMG_PATH, 'fullscreen.png'),
                                              confidence=0.9,
                                              minSearchTime=3)
        pyautogui.click(x, y)
        fullscreen = True
    except TypeError:
        logging.error("Could not find fullscreen!")
        if DEBUG:
            pyautogui.screenshot(
                os.path.join(
                    REC_PATH,
                    time.strftime(TIME_FORMAT) + "-" + MEETING_DESCRIPTION) +
                "_fullscreen_error.png")

    # Screen sharing already active
    if not fullscreen:
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'view_options.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not find view options!")
            if DEBUG:
                pyautogui.screenshot(
                    os.path.join(
                        REC_PATH,
                        time.strftime(TIME_FORMAT) + "-" +
                        MEETING_DESCRIPTION) + "_view_options_error.png")

        # Switch to fullscreen
        time.sleep(1)
        show_toolbars()

        logging.info("Enter fullscreen..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'enter_fullscreen.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not enter fullscreen!")
            if DEBUG:
                pyautogui.screenshot(
                    os.path.join(
                        REC_PATH,
                        time.strftime(TIME_FORMAT) + "-" +
                        MEETING_DESCRIPTION) + "_enter_fullscreen_error.png")

        time.sleep(2)

    # Check if screen sharing is active
    if (pyautogui.locateCenterOnScreen(os.path.join(IMG_PATH,
                                                    'you_are_viewing.png'),
                                       confidence=0.9) is not None):
        logging.info("Screen sharing active..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'view_options.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not find view options!")
            if DEBUG:
                pyautogui.screenshot(
                    os.path.join(
                        REC_PATH,
                        time.strftime(TIME_FORMAT) + "-" +
                        MEETING_DESCRIPTION) + "_view_options_error.png")

        time.sleep(2)
        # Hide video panel
        logging.info("Hide video panel..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'hide_video_panel.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
            VIDEO_PANEL_HIDED = True
        except TypeError:
            logging.error("Could not hide video panel!")
            if DEBUG:
                pyautogui.screenshot(
                    os.path.join(
                        REC_PATH,
                        time.strftime(TIME_FORMAT) + "-" +
                        MEETING_DESCRIPTION) + "_hide_video_panel_error.png")
    else:
        # Switch to speaker view
        show_toolbars()

        logging.info("Switch view..")
        try:
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'view.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.warning("Could not find view!")

        time.sleep(1)

        logging.info("Switch to speaker view..")
        try:
            # Speaker view
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'speaker_view.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.warning("Could not switch speaker view!")

        time.sleep(1)

        try:
            # Minimize panel
            logging.info("Minimize panel..")
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'minimize.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.warning("Could not minimize panel!")

    # Move mouse from screen
    pyautogui.click(int(WIDTH / 2), int(HEIGHT / 2))
    pyautogui.moveTo(10, int(HEIGHT * 0.05))

    if DEBUG and ffmpeg_debug is not None:
        os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
        atexit.unregister(os.killpg)

    # Audio
    # Start recording
    logging.info("Start recording..")

    filename = os.path.join(
        REC_PATH,
        time.strftime(TIME_FORMAT) + "-" + MEETING_DESCRIPTION) + ".mkv"

    resolution = str(WIDTH) + 'x' + str(HEIGHT)
    disp = os.getenv('DISPLAY')

    # Recording with ffmpeg
    command = "ffmpeg"
    command += " -nostats -loglevel error"
    ## Audio
    command += " -f pulse -ac 2 -i 1"
    ## Video
    command += " -f x11grab"
    command += " -draw_mouse 0"
    command += " -framerate 25"
    command += " -s " + resolution
    command += " -i " + disp
    #command += " -acodec pcm_s16le"
    command += " -c:v libx264rgb"
    command += " -crf 0"
    command += " -preset ultrafast"
    command += " "
    command += filename

    ffmpeg = Popen(command, stdout=STDOUT, shell=True, preexec_fn=os.setsid)

    atexit.register(os.killpg, os.getpgid(ffmpeg.pid), SIGQUIT)

    start_date = datetime.now()
    end_date = start_date + timedelta(seconds=duration)

    # Start thread to check active screen sharing
    hvo_thread = HideViewOptionsThread()

    # Send Telegram Notification
    send_telegram_message("Joined Meeting '{}' and started recording.".format(
        MEETING_DESCRIPTION))

    meeting_running = True
    while meeting_running:
        time_remaining = end_date - datetime.now()
        if time_remaining.total_seconds() < 0 or not ONGOING_MEETING:
            meeting_running = False
        else:
            print(f"Meeting ends in {time_remaining}", end="\r", flush=True)
        time.sleep(5)

    logging.info("Meeting ends at %s" % datetime.now())

    # Close everything
    if DEBUG and ffmpeg_debug is not None:
        os.killpg(os.getpgid(ffmpeg_debug.pid), SIGQUIT)
        atexit.unregister(os.killpg)

    os.killpg(os.getpgid(zoom.pid), SIGQUIT)
    os.killpg(os.getpgid(ffmpeg.pid), SIGQUIT)
    atexit.unregister(os.killpg)
    bg_thread.terminate()
    hvo_thread.terminate()

    if not ONGOING_MEETING:
        try:
            # Press OK after meeting ended by host
            x, y = pyautogui.locateCenterOnScreen(os.path.join(
                IMG_PATH, 'ok.png'),
                                                  confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            if DEBUG:
                pyautogui.screenshot(
                    os.path.join(
                        REC_PATH,
                        time.strftime(TIME_FORMAT) + "-" +
                        MEETING_DESCRIPTION) + "_ok_error.png")

    send_telegram_message("Meeting '{}' ended.".format(MEETING_DESCRIPTION))
    logging.info(f"Next meeting at {schedule.next_run()}")


def get_active_meeting():
    list_of_process_ids = list()
    for pid in find_process_id_by_name('zoom'):
        for param in pid['cmdline']:
            if str(param) == "/opt/zoom/zoom":
                list_of_process_ids.append(pid)
                break
        else:
            continue
        break
    return list_of_process_ids


def play_audio():
    # Get all files in audio directory
    files = os.listdir(AUDIO_PATH)
    # Filter .wav files
    files = list(filter(lambda f: f.endswith(".wav"), files))
    # Check if .wav files available
    if len(files) > 0:
        unmute()
        time.sleep(1)
        # Get random file
        audio_file = random.choice(files)
        path = os.path.join(AUDIO_PATH, audio_file)
        # Use paplay to play .wav file on specific Output
        command = "/usr/bin/paplay --device=microphone -p " + path
        play = Popen(command, shell=True, stdout=STDOUT, stderr=PIPE)
        _, err = play.communicate()
        if play.returncode != 0:
            logging.error("Failed playing file! - " + str(play.returncode) +
                          " - " + str(err))
        else:
            logging.info(
                "Successfully played audio file - {}".format(audio_file))
        time.sleep(1)
        mute()
    else:
        logging.error("No .wav files found!")


def join_ongoing_meeting():
    with open(CSV_PATH, mode='r') as csv_file:
        csv_reader = DictReader(csv_file, delimiter=CSV_DELIMITER)
        for row in csv_reader:
            # Check and join ongoing meeting
            curr_date = datetime.now()

            # Monday, tuesday, ..
            if row["weekday"].lower() == curr_date.strftime('%A').lower():
                curr_time = curr_date.time()

                start_time_csv = datetime.strptime(row["time"], '%H:%M')
                start_date = curr_date.replace(hour=start_time_csv.hour,
                                               minute=start_time_csv.minute)
                start_time = start_date.time()

                end_date = start_date + \
                    timedelta(seconds=int(row["duration"]) * 60)
                end_time = end_date.time()

                recent_duration = (end_date - curr_date).total_seconds()

                if start_time < end_time:
                    if start_time <= curr_time <= end_time and str(
                            row["record"]) == 'true':
                        logging.info("Join meeting that is currently running..")
                        join(meet_id=row["id"],
                             meet_pw=row["password"],
                             duration=recent_duration,
                             description=row["description"])
                else:  # crosses midnight
                    if curr_time >= start_time or curr_time <= end_time and str(
                            row["record"]) == 'true':
                        logging.info("Join meeting that is currently running..")
                        join(meet_id=row["id"],
                             meet_pw=row["password"],
                             duration=recent_duration,
                             description=row["description"])


def setup_schedule():
    with open(CSV_PATH, mode='r') as csv_file:
        csv_reader = DictReader(csv_file, delimiter=CSV_DELIMITER)
        line_count = 0
        for row in csv_reader:
            if str(row["record"]) == 'true':
                time = datetime.strptime(row["time"], '%H:%M')

                if (time - datetime.now()).seconds > 60:
                    time = time - timedelta(minutes=1)

                cmd_string = "schedule.every()." + row["weekday"] \
                             + ".at(\"" \
                             + time.strftime('%H:%M') \
                             + "\").do(join, meet_id=\"" + row["id"] \
                             + "\", meet_pw=\"" + row["password"] \
                             + "\", duration=" + str(int(row["duration"]) * 60) \
                             + ", description=\"" + row["description"] + "\")"

                cmd = compile(cmd_string, "<string>", "eval")
                eval(cmd)
                line_count += 1
        logging.info("Added %s meetings to schedule." % line_count)


def main():
    if not os.access(REC_PATH, os.W_OK):
        logging.error(
            "You do not have enough permission to write to recordings folder!")
        raise PermissionError()

    setup_schedule()
    logging.info(f"Next meeting at {schedule.next_run()}")
    join_ongoing_meeting()


if __name__ == '__main__':
    main()

while True:
    schedule.run_pending()
    time.sleep(15)