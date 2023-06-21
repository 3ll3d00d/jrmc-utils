import logging
import sys
import time

from mediaserver import MediaServer

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

if __name__ == '__main__':
    mc = MediaServer(sys.argv[1], (sys.argv[2], sys.argv[3]))
    for ms in range(199, 4880000, 200):
        logger.info(f'Setting {ms}')

        if mc.set_position(ms):
            pos = mc.get_position()
            if pos == 0:
                raise ValueError(f'Playback stopped at {ms}')
            elif pos != ms:
                logger.info(f"Position should be {ms} but is {pos}, backing off 100ms")
                time.sleep(0.1)
                pos = mc.get_position()
                if pos != ms:
                    logger.info(f"Position should be {ms} but is {pos}, backing off 500ms")
                    time.sleep(0.5)
                    pos = mc.get_position()
                    if pos != ms:
                        raise ValueError(f"Mismatch {ms} vs {pos}")
        else:
            raise ValueError(f'Failed to set {ms}')
