import time

from config import db_engine
from sqlalchemy import text


def check_match_timeouts():

    # PUT YOUR EXISTING check_match_timeouts()
    # FUNCTION HERE EXACTLY AS IT IS.
    #
    # Do not change its match logic.


def match_timeout_worker():

    while True:

        try:

            check_match_timeouts()

        except Exception:
            pass

        time.sleep(60)


if __name__ == "__main__":

    match_timeout_worker()