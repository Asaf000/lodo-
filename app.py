from flask import Flask, render_template, request, redirect, url_for, flash, session
from sqlalchemy import create_engine, text
from config import server_engine, db_engine, DB_CONFIG
from database.schema import initialize_database

import os
import uuid
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# =========================================================
# SESSION SECURITY
# =========================================================

SESSION_INACTIVITY_LIMIT = timedelta(minutes=20)


def update_user_activity():
    """
    Update the authenticated user's last activity time.
    """
    if "userid" in session:
        session["last_activity"] = time.time()


def session_has_expired():
    """
    Check whether the authenticated user's session
    has been inactive for more than 20 minutes.
    """

    if "userid" not in session:
        return False

    last_activity = session.get("last_activity")

    # If this is an old session that doesn't have
    # last_activity, initialize it instead of
    # immediately logging the user out.
    if last_activity is None:
        session["last_activity"] = time.time()
        return False

    inactive_seconds = (
        time.time() - last_activity
    )

    return (
        inactive_seconds
        > SESSION_INACTIVITY_LIMIT.total_seconds()
    )

@app.before_request
def check_session_timeout():

    # No logged-in user
    if "userid" not in session:
        return None

    # Check whether session has expired
    if session_has_expired():

        session.clear()

        # Game/API requests should receive JSON
        # instead of an HTML redirect.
        if (
            request.path.startswith("/ludo")
            or request.path.startswith("/match-")
            or request.path.startswith("/exit-match/")
        ):
            return {
                "success": False,
                "message": "Session expired. Please login again.",
                "session_expired": True
            }, 401

        # Normal browser page
        return redirect(
            url_for("login")
        )

    return None


from admin import admin_bp

app.register_blueprint(
    admin_bp
)

from employee import employee_bp
app.register_blueprint(
    employee_bp
)


# =========================================
# LUDO SAFE PHYSICAL POSITIONS
# =========================================

LUDO_SAFE_POSITIONS = {
    20,
    30,
    40,
    50
}

@app.route("/", methods=["GET", "POST"])
def login():

    try:

        if request.method == "POST":

            username = str(
                request.form.get("username", "")
            ).strip()

            password = str(
                request.form.get("password", "")
            ).strip()

            with db_engine.begin() as connection:

                user = connection.execute(
                    text("""
                        SELECT userid
                        FROM lpusers
                        WHERE username = :username
                        AND password = :password
                        LIMIT 1
                    """),
                    {
                        "username": username,
                        "password": password
                    }
                ).fetchone()

            if user:

                # Start a completely new session
                session.clear()

                # Store authenticated user
                session["userid"] = user.userid

                # Start inactivity timer
                session["last_activity"] = time.time()

                return redirect(
                    url_for("dashboard")
                )

            flash(
                "Invalid inputs.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        return render_template(
            "login.html"
        )

    except Exception:

        # Do not expose internal error details
        flash(
            "Unable to process your request. Please try again.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    finally:
        pass


@app.route("/create-account", methods=["GET", "POST"])
def create_account():

    try:

        if request.method == "POST":

            userid = str(uuid.uuid4())

            username = str(
                request.form.get("username", "")
            ).strip()

            password = str(
                request.form.get("password", "")
            ).strip()

            phonenumber = str(
                request.form.get("phonenumber", "")
            ).strip()

            with db_engine.begin() as connection:

                connection.execute(
                    text("""
                        INSERT INTO lpusers
                        (
                            userid,
                            username,
                            password,
                            phonenumber
                        )
                        VALUES
                        (
                            :userid,
                            :username,
                            :password,
                            :phonenumber
                        )
                    """),
                    {
                        "userid": userid,
                        "username": username,
                        "password": password,
                        "phonenumber": phonenumber
                    }
                )

            flash(
                "Your account has been created successfully.",
                "success"
            )

            return redirect(
                url_for("create_account")
            )

        return render_template(
            "create_account.html"
        )

    except Exception:

        flash(
            "Unable to create your account. Please try again.",
            "error"
        )

        return redirect(
            url_for("create_account")
        )

    finally:
        pass

@app.route("/dashboard")
def dashboard():

    try:

        if "userid" not in session:

            return redirect(
                url_for("login")
            )

        # Genuine authenticated page activity
        update_user_activity()

        return render_template(
            "dashboard.html"
        )

    except Exception:

        return redirect(
            url_for("login")
        )

    finally:
        pass


def get_available_matches(userid):

    try:

        with db_engine.begin() as connection:

            matches = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        amount,
                        initiatedusercolor,
                        matchstarttime
                    FROM usersmatches
                    WHERE matchterminatedbytime = 0
                    AND initiateduseruuid != :userid
                    AND secondplayeruuid IS NULL
                    ORDER BY matchstarttime ASC
                """),
                {
                    "userid": userid
                }
            ).fetchall()

        return matches

    except Exception:

        return []

    finally:
        pass


@app.route("/match-ready-status")
def match_ready_status():

    try:

        if "userid" not in session:
            return {
                "status": "unauthorized"
            }, 401

        current_userid = session["userid"]

        with db_engine.begin() as connection:

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        user1ready,
                        user2ready,
                        matchstarted,
                        matchterminatedbytime
                    FROM usersmatches
                    WHERE
                        matchterminatedbytime = 0
                        AND (
                            initiateduseruuid = :userid
                            OR secondplayeruuid = :userid
                        )
                        AND secondplayeruuid IS NOT NULL
                    ORDER BY matchstarttime DESC
                    LIMIT 1
                """),
                {
                    "userid": current_userid
                }
            ).fetchone()

        if not match:

            return {
                "match_found": False
            }

        return {
            "match_found": True,

            "matchbatchnumber":
                match.matchbatchnumber,

            "user1ready":
                bool(match.user1ready),

            "user2ready":
                bool(match.user2ready),

            "matchstarted":
                bool(match.matchstarted)
        }

    except Exception:

        return {
            "match_found": False,
            "error": "Unable to check match status"
        }, 500

    finally:
        pass


@app.route("/classic-dashboard", methods=["GET", "POST"])
def classic_dashboard():

    try:

        # -----------------------------------------
        # LOGIN CHECK
        # -----------------------------------------

        if "userid" not in session:
            return redirect(url_for("login"))

        current_userid = session["userid"]

        # Genuine user activity
        update_user_activity()

        # -----------------------------------------
        # GET CURRENT USER BALANCE
        # -----------------------------------------

        with db_engine.begin() as connection:

            result = connection.execute(
                text("""
                    SELECT money
                    FROM lpusers
                    WHERE userid = :userid
                """),
                {
                    "userid": current_userid
                }
            ).fetchone()

        balance = result.money if result else 0

        # -----------------------------------------
        # CHECK ACTIVE INITIATED MATCH
        # -----------------------------------------

        with db_engine.begin() as connection:

            active_match = connection.execute(
                text("""
                    SELECT matchbatchnumber
                    FROM usersmatches
                    WHERE initiateduseruuid = :userid
                    AND matchterminatedbytime = 0
                    LIMIT 1
                """),
                {
                    "userid": current_userid
                }
            ).fetchone()

        can_start_match = active_match is None

        # ==================================================
        # POST REQUEST
        # ==================================================

        if request.method == "POST":

            action = request.form.get("action")

            # ==================================================
            # INITIATE NEW MATCH
            # ==================================================

            if action == "initiate_match":

                # User cannot initiate another active match

                if not can_start_match:

                    return redirect(
                        url_for("classic_dashboard")
                    )

                # -----------------------------------------
                # GET AMOUNT
                # -----------------------------------------

                try:

                    amount = int(
                        request.form.get("amount", 0)
                    )

                except (ValueError, TypeError):

                    flash(
                        "Invalid amount.",
                        "error"
                    )

                    return redirect(
                        url_for("classic_dashboard")
                    )

                # -----------------------------------------
                # AMOUNT VALIDATION
                # -----------------------------------------

                if (
                    amount < 50
                    or amount > 5000000
                    or amount % 50 != 0
                ):

                    flash(
                        "Invalid amount.",
                        "error"
                    )

                    return redirect(
                        url_for("classic_dashboard")
                    )

                # -----------------------------------------
                # BALANCE CHECK
                # -----------------------------------------

                if balance < amount:

                    flash(
                        "Low Balance. Please increase the balance to continue.",
                        "error"
                    )

                    return redirect(
                        url_for("classic_dashboard")
                    )

                # -----------------------------------------
                # GET SELECTED COLOR
                # -----------------------------------------

                selected_color = request.form.get("color")

                # -----------------------------------------
                # OPEN COLOR MODAL
                # -----------------------------------------

                if not selected_color:

                    return render_template(
                        "classic_dashboard.html",

                        balance=balance,

                        matches=get_available_matches(
                            current_userid
                        ),

                        selected_amount=amount,

                        show_color_modal=True,

                        can_start_match=
                            can_start_match,

                        should_monitor_match=False
                    )

                # -----------------------------------------
                # VALID COLORS
                # -----------------------------------------

                allowed_colors = {
                    "red",
                    "blue",
                    "green",
                    "yellow"
                }

                if selected_color not in allowed_colors:

                    flash(
                        "Please select a valid colour.",
                        "error"
                    )

                    return redirect(
                        url_for("classic_dashboard")
                    )

                # -----------------------------------------
                # CREATE NEW MATCH
                # -----------------------------------------

                with db_engine.begin() as connection:

                    while True:

                        matchbatchnumber = str(
                            uuid.uuid4().int
                        )[-8:]

                        existing_match = connection.execute(
                            text("""
                                SELECT matchbatchnumber
                                FROM usersmatches
                                WHERE matchbatchnumber =
                                    :matchbatchnumber
                            """),
                            {
                                "matchbatchnumber":
                                    matchbatchnumber
                            }
                        ).fetchone()

                        if not existing_match:
                            break

                    connection.execute(
                        text("""
                            INSERT INTO usersmatches
                            (
                                matchbatchnumber,
                                initiateduseruuid,
                                amount,
                                matchstarttime,
                                initiatedusercolor,
                                timelength,
                                matchterminatedbytime,
                                user1ready,
                                user2ready,
                                matchstarted,
                                terminatedby,
                                terminatedtime,
                                terminatedbyother
                            )
                            VALUES
                            (
                                :matchbatchnumber,
                                :initiateduseruuid,
                                :amount,
                                NOW(),
                                :initiatedusercolor,
                                60,
                                0,
                                0,
                                0,
                                0,
                                NULL,
                                NULL,
                                0
                            )
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber,

                            "initiateduseruuid":
                                current_userid,

                            "amount":
                                amount,

                            "initiatedusercolor":
                                selected_color
                        }
                    )

                flash(
                    "Match started successfully.",
                    "success"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # ==================================================
            # JOIN EXISTING MATCH
            # ==================================================

            elif action == "join_match":

                matchbatchnumber = request.form.get(
                    "matchbatchnumber"
                )

                selected_color = request.form.get(
                    "color"
                )

                if not matchbatchnumber:

                    flash(
                        "Match not found.",
                        "error"
                    )

                    return redirect(
                        url_for("classic_dashboard")
                    )

                with db_engine.begin() as connection:

                    match = connection.execute(
                        text("""
                            SELECT
                                matchbatchnumber,
                                amount,
                                initiateduseruuid,
                                initiatedusercolor,
                                secondplayeruuid,
                                matchterminatedbytime
                            FROM usersmatches
                            WHERE matchbatchnumber =
                                :matchbatchnumber

                            AND matchterminatedbytime = 0

                            AND initiateduseruuid != :userid

                            AND secondplayeruuid IS NULL

                            LIMIT 1
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber,

                            "userid":
                                current_userid
                        }
                    ).fetchone()

                    if not match:

                        flash(
                            "This match is no longer available.",
                            "error"
                        )

                        return redirect(
                            url_for("classic_dashboard")
                        )

                    # -----------------------------------------
                    # SECOND PLAYER BALANCE CHECK
                    # -----------------------------------------

                    if balance < match.amount:

                        flash(
                            "Low Balance. Please add balance to continue.",
                            "error"
                        )

                        return redirect(
                            url_for("classic_dashboard")
                        )

                    # -----------------------------------------
                    # OPEN COLOR MODAL
                    # -----------------------------------------

                    if not selected_color:

                        return render_template(
                            "classic_dashboard.html",

                            balance=balance,

                            matches=get_available_matches(
                                current_userid
                            ),

                            join_match_number=
                                matchbatchnumber,

                            initiator_color=
                                match.initiatedusercolor,

                            show_join_color_modal=True,

                            can_start_match=
                                can_start_match,

                            should_monitor_match=False
                        )

                    # -----------------------------------------
                    # VALID COLORS
                    # -----------------------------------------

                    allowed_colors = {
                        "red",
                        "blue",
                        "green",
                        "yellow"
                    }

                    if selected_color not in allowed_colors:

                        flash(
                            "Please select a valid colour.",
                            "error"
                        )

                        return redirect(
                            url_for("classic_dashboard")
                        )

                    # -----------------------------------------
                    # PLAYER 1 COLOR CANNOT BE USED
                    # -----------------------------------------

                    if selected_color == match.initiatedusercolor:

                        flash(
                            "Please select another color. "
                            "This color is already selected by Player 1.",
                            "error"
                        )

                        return redirect(
                            url_for("classic_dashboard")
                        )

                    # -----------------------------------------
                    # ADD SECOND PLAYER
                    # -----------------------------------------

                    connection.execute(
                        text("""
                            UPDATE usersmatches
                            SET
                                secondplayeruuid =
                                    :secondplayeruuid,

                                secondplayeraccepttime =
                                    NOW(),

                                secondplayercolor =
                                    :secondplayercolor

                            WHERE matchbatchnumber =
                                :matchbatchnumber

                            AND secondplayeruuid IS NULL

                            AND matchterminatedbytime = 0
                        """),
                        {
                            "secondplayeruuid":
                                current_userid,

                            "secondplayercolor":
                                selected_color,

                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    )

                # Player 2 is now part of a match.
                # Redirect back to dashboard.

                return redirect(
                    url_for(
                        "classic_dashboard"
                    )
                )

            # ==================================================
            # READY / NOT READY
            # ==================================================

            elif action == "ready_match":

                matchbatchnumber = request.form.get(
                    "matchbatchnumber"
                )

                ready_value = request.form.get(
                    "ready"
                )

                if not matchbatchnumber:

                    return redirect(
                        url_for("classic_dashboard")
                    )

                ready = (
                    True
                    if ready_value == "1"
                    else False
                )

                with db_engine.begin() as connection:

                    # -----------------------------------------
                    # GET MATCH
                    # -----------------------------------------

                    match = connection.execute(
                        text("""
                            SELECT
                                initiateduseruuid,
                                secondplayeruuid,
                                user1ready,
                                user2ready,
                                matchstarted,
                                matchterminatedbytime
                            FROM usersmatches
                            WHERE matchbatchnumber =
                                :matchbatchnumber
                            LIMIT 1
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    ).fetchone()

                    if not match:

                        flash(
                            "Match not found.",
                            "error"
                        )

                        return redirect(
                            url_for("classic_dashboard")
                        )

                    # -----------------------------------------
                    # CHECK PLAYER
                    # -----------------------------------------

                    if (
                        current_userid !=
                        match.initiateduseruuid

                        and

                        current_userid !=
                        match.secondplayeruuid
                    ):

                        flash(
                            "You are not part of this match.",
                            "error"
                        )

                        return redirect(
                            url_for("classic_dashboard")
                        )

                    # ==================================================
                    # TERMINATE OTHER MATCHES
                    # ONLY WHEN USER CLICKS START
                    # ==================================================

                    if ready:

                        connection.execute(
                            text("""
                                UPDATE usersmatches
                                SET
                                    matchterminatedbytime = 1,

                                    terminatedbyother = 1,

                                    terminatedtime = NOW()

                                WHERE
                                    matchbatchnumber !=
                                        :currentmatch

                                AND matchterminatedbytime = 0

                                AND (
                                    initiateduseruuid = :userid

                                    OR

                                    secondplayeruuid = :userid
                                )
                            """),
                            {
                                "currentmatch":
                                    matchbatchnumber,

                                "userid":
                                    current_userid
                            }
                        )

                    # -----------------------------------------
                    # SET PLAYER READY
                    # -----------------------------------------

                    if (
                        current_userid ==
                        match.initiateduseruuid
                    ):

                        connection.execute(
                            text("""
                                UPDATE usersmatches
                                SET
                                    user1ready = :ready

                                WHERE matchbatchnumber =
                                    :matchbatchnumber
                            """),
                            {
                                "ready":
                                    ready,

                                "matchbatchnumber":
                                    matchbatchnumber
                            }
                        )

                    elif (
                        current_userid ==
                        match.secondplayeruuid
                    ):

                        connection.execute(
                            text("""
                                UPDATE usersmatches
                                SET
                                    user2ready = :ready

                                WHERE matchbatchnumber =
                                    :matchbatchnumber
                            """),
                            {
                                "ready":
                                    ready,

                                "matchbatchnumber":
                                    matchbatchnumber
                            }
                        )

                    # -----------------------------------------
                    # CHECK BOTH PLAYERS
                    # -----------------------------------------

                    updated_match = connection.execute(
                        text("""
                            SELECT
                                user1ready,
                                user2ready
                            FROM usersmatches
                            WHERE matchbatchnumber =
                                :matchbatchnumber
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    ).fetchone()

                    # ==================================================
                    # START MATCH
                    # ==================================================

                    if (
                        updated_match
                        and
                        updated_match.user1ready
                        and
                        updated_match.user2ready
                    ):

                        # -----------------------------------------
                        # START MATCH + INACTIVITY TIMERS
                        # -----------------------------------------

                        connection.execute(
                            text("""
                                UPDATE usersmatches
                                SET
                                    matchstarted = 1,

                                    player1lastmovetime =
                                        NOW(),

                                    player2lastmovetime =
                                        NOW()

                                WHERE matchbatchnumber =
                                    :matchbatchnumber
                            """),
                            {
                                "matchbatchnumber":
                                    matchbatchnumber
                            }
                        )

                        # ==================================================
                        # INITIALIZE LUDO GAME
                        # ==================================================

                        existing_game = connection.execute(
                            text("""
                                SELECT id
                                FROM ludogamestate
                                WHERE matchbatchnumber =
                                    :matchbatchnumber
                                LIMIT 1
                                FOR UPDATE
                            """),
                            {
                                "matchbatchnumber":
                                    matchbatchnumber
                            }
                        ).fetchone()

                        # -----------------------------------------
                        # CREATE GAME ONLY ONCE
                        # -----------------------------------------

                        if not existing_game:

                            # -----------------------------------------
                            # CREATE LUDO GAME STATE
                            # -----------------------------------------

                            connection.execute(
                                text("""
                                    INSERT INTO ludogamestate
                                    (
                                        matchbatchnumber,
                                        currentturnuuid,
                                        lastdice,
                                        consecutivesix,
                                        mustmove
                                    )
                                    VALUES
                                    (
                                        :matchbatchnumber,
                                        :currentturnuuid,
                                        NULL,
                                        0,
                                        0
                                    )
                                """),
                                {
                                    "matchbatchnumber":
                                        matchbatchnumber,

                                    # Player 1 starts
                                    "currentturnuuid":
                                        match.initiateduseruuid
                                }
                            )

                            # -----------------------------------------
                            # CREATE PLAYER 1 COINS
                            # -----------------------------------------

                            for coinindex in range(1, 5):

                                connection.execute(
                                    text("""
                                        INSERT INTO ludocoins
                                        (
                                            matchbatchnumber,
                                            playeruuid,
                                            coinindex,
                                            position,
                                            stepsmoved,
                                            finished
                                        )
                                        VALUES
                                        (
                                            :matchbatchnumber,
                                            :playeruuid,
                                            :coinindex,
                                            -1,
                                            0,
                                            0
                                        )
                                    """),
                                    {
                                        "matchbatchnumber":
                                            matchbatchnumber,

                                        "playeruuid":
                                            match.initiateduseruuid,

                                        "coinindex":
                                            coinindex
                                    }
                                )

                            # -----------------------------------------
                            # CREATE PLAYER 2 COINS
                            # -----------------------------------------

                            for coinindex in range(1, 5):

                                connection.execute(
                                    text("""
                                        INSERT INTO ludocoins
                                        (
                                            matchbatchnumber,
                                            playeruuid,
                                            coinindex,
                                            position,
                                            stepsmoved,
                                            finished
                                        )
                                        VALUES
                                        (
                                            :matchbatchnumber,
                                            :playeruuid,
                                            :coinindex,
                                            -1,
                                            0,
                                            0
                                        )
                                    """),
                                    {
                                        "matchbatchnumber":
                                            matchbatchnumber,

                                        "playeruuid":
                                            match.secondplayeruuid,

                                        "coinindex":
                                            coinindex
                                    }
                                )

                # ==================================================
                # CHECK MATCH STATE
                # ==================================================

                with db_engine.begin() as connection:

                    final_match = connection.execute(
                        text("""
                            SELECT
                                matchstarted,
                                matchterminatedbytime
                            FROM usersmatches
                            WHERE matchbatchnumber =
                                :matchbatchnumber
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    ).fetchone()

                if (
                    final_match
                    and
                    final_match.matchstarted
                    and
                    not final_match.matchterminatedbytime
                ):

                    return redirect(
                        url_for("lodo_player_game")
                    )

                return redirect(
                    url_for("classic_dashboard")
                )

        # ==================================================
        # GET REQUEST
        # ==================================================

        # -----------------------------------------
        # READY MATCH FROM URL
        # -----------------------------------------

        ready_match_number = request.args.get(
            "ready_match"
        )

        show_ready_modal = False

        if ready_match_number:

            with db_engine.begin() as connection:

                ready_match = connection.execute(
                    text("""
                        SELECT
                            matchbatchnumber,
                            initiateduseruuid,
                            secondplayeruuid,
                            user1ready,
                            user2ready,
                            matchstarted,
                            matchterminatedbytime
                        FROM usersmatches
                        WHERE matchbatchnumber =
                            :matchbatchnumber
                        AND matchterminatedbytime = 0
                        LIMIT 1
                    """),
                    {
                        "matchbatchnumber":
                            ready_match_number
                    }
                ).fetchone()

            if (
                ready_match

                and

                (
                    current_userid ==
                        ready_match.initiateduseruuid

                    or

                    current_userid ==
                        ready_match.secondplayeruuid
                )

                and

                ready_match.secondplayeruuid is not None

                and

                not ready_match.matchstarted
            ):

                show_ready_modal = True

        # ==================================================
        # AVAILABLE MATCHES
        # ==================================================

        matches = get_available_matches(
            current_userid
        )

        # ==================================================
        # DETERMINE WHETHER POLLING IS NEEDED
        # ==================================================

        with db_engine.begin() as connection:

            monitor_match = connection.execute(
                text("""
                    SELECT matchbatchnumber
                    FROM usersmatches
                    WHERE
                        matchterminatedbytime = 0

                        AND (
                            initiateduseruuid = :userid

                            OR

                            secondplayeruuid = :userid
                        )

                        AND secondplayeruuid IS NOT NULL

                        AND matchstarted = 0

                    ORDER BY matchstarttime DESC

                    LIMIT 1
                """),
                {
                    "userid":
                        current_userid
                }
            ).fetchone()

        should_monitor_match = (
            monitor_match is not None
        )

        # ==================================================
        # FINAL RENDER
        # ==================================================

        return render_template(
            "classic_dashboard.html",

            balance=balance,

            matches=matches,

            can_start_match=
                can_start_match,

            show_ready_modal=
                show_ready_modal,

            ready_match_number=
                ready_match_number,

            should_monitor_match=
                should_monitor_match
        )

    except Exception:

        flash(
            "Unable to process your request. Please try again.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass

@app.route("/match-status/<matchbatchnumber>")
def match_status(matchbatchnumber):

    try:

        if "userid" not in session:
            return {
                "status": "unauthorized"
            }, 401

        current_userid = session["userid"]

        with db_engine.begin() as connection:

            match = connection.execute(
                text("""
                    SELECT
                        initiateduseruuid,
                        secondplayeruuid,
                        user1ready,
                        user2ready,
                        matchstarted,
                        matchterminatedbytime
                    FROM usersmatches
                    WHERE matchbatchnumber = :matchbatchnumber
                    LIMIT 1
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

        if not match:

            return {
                "status": "not_found"
            }, 404

        if (
            current_userid != match.initiateduseruuid
            and
            current_userid != match.secondplayeruuid
        ):

            return {
                "status": "forbidden"
            }, 403

        return {
            "match_started":
                bool(match.matchstarted),

            "user1_ready":
                bool(match.user1ready),

            "user2_ready":
                bool(match.user2ready)
        }

    except Exception:

        return {
            "status": "error",
            "message": "Unable to fetch match status"
        }, 500

    finally:
        pass


@app.route("/lodo-player-game")
def lodo_player_game():

    try:

        # -----------------------------------------
        # LOGIN CHECK
        # -----------------------------------------

        if "userid" not in session:
            return redirect(
                url_for("login")
            )

        current_userid = session["userid"]

        # Genuine user activity
        update_user_activity()

        # -----------------------------------------
        # FIND CURRENT ACTIVE MATCH
        # -----------------------------------------

        with db_engine.begin() as connection:

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        amount,
                        initiatedusercolor,
                        secondplayercolor,
                        matchstarted,
                        matchterminatedbytime
                    FROM usersmatches
                    WHERE
                        matchstarted = 1

                        AND matchterminatedbytime = 0

                        AND (
                            initiateduseruuid = :userid
                            OR secondplayeruuid = :userid
                        )

                    ORDER BY matchstarttime DESC

                    LIMIT 1
                """),
                {
                    "userid": current_userid
                }
            ).fetchone()

        # -----------------------------------------
        # NO ACTIVE MATCH
        # -----------------------------------------

        if not match:

            flash(
                "No active match found.",
                "error"
            )

            return redirect(
                url_for("classic_dashboard")
            )

        # -----------------------------------------
        # DETERMINE OTHER PLAYER
        # -----------------------------------------

        if current_userid == match.initiateduseruuid:

            opponent_uuid = match.secondplayeruuid

            player_color = match.initiatedusercolor

            opponent_color = match.secondplayercolor

        else:

            opponent_uuid = match.initiateduseruuid

            player_color = match.secondplayercolor

            opponent_color = match.initiatedusercolor

        # -----------------------------------------
        # RENDER GAME
        # -----------------------------------------

        return render_template(
            "lodoplayergame.html",

            match=match,

            current_userid=current_userid,

            opponent_uuid=opponent_uuid,

            player_color=player_color,

            opponent_color=opponent_color
        )

    except Exception:

        flash(
            "Unable to open the game. Please try again.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass

@app.route("/ludo-game-state/<matchbatchnumber>", methods=["GET"])
def ludo_game_state(matchbatchnumber):

    try:

        # -----------------------------------------
        # LOGIN CHECK
        # -----------------------------------------

        if "userid" not in session:
            return {
                "success": False,
                "message": "Not logged in"
            }, 401

        current_userid = session["userid"]

        with db_engine.begin() as connection:

            # -----------------------------------------
            # GET MATCH
            # -----------------------------------------

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        initiatedusercolor,
                        secondplayercolor,
                        matchstarted,
                        matchterminatedbytime,
                        terminatedby,
                        terminatedtime,
                        player1lastmovetime,
                        player2lastmovetime,
                        winner
                    FROM usersmatches
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # -----------------------------------------
            # MATCH NOT FOUND
            # -----------------------------------------

            if not match:

                return {
                    "success": False,
                    "message": "Match not found"
                }, 404

            # -----------------------------------------
            # VERIFY PLAYER
            # -----------------------------------------

            if (
                current_userid !=
                match.initiateduseruuid

                and

                current_userid !=
                match.secondplayeruuid
            ):

                return {
                    "success": False,
                    "message": "You are not part of this match"
                }, 403

            # -----------------------------------------
            # MATCH MUST BE STARTED
            # -----------------------------------------

            if not match.matchstarted:

                return {
                    "success": False,
                    "message": "Match has not started"
                }, 400

            # -----------------------------------------
            # GET GAME STATE
            # -----------------------------------------

            game = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        currentturnuuid,
                        lastdice,
                        consecutivesix,
                        mustmove
                    FROM ludogamestate
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            if not game:

                return {
                    "success": False,
                    "message": "Game state not found"
                }, 404

            # -----------------------------------------
            # GET ALL COINS
            # -----------------------------------------

            coins = connection.execute(
                text("""
                    SELECT
                        playeruuid,
                        coinindex,
                        position,
                        stepsmoved,
                        finished
                    FROM ludocoins
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    ORDER BY
                        playeruuid,
                        coinindex
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchall()

        # -----------------------------------------
        # FORMAT COINS
        # -----------------------------------------

        coin_data = []

        for coin in coins:

            coin_data.append({
                "playeruuid":
                    coin.playeruuid,

                "coinindex":
                    coin.coinindex,

                "position":
                    coin.position,

                "stepsmoved":
                    coin.stepsmoved,

                "finished":
                    bool(coin.finished)
            })

        # -----------------------------------------
        # DETERMINE END REASON WITHOUT STORING IT
        # -----------------------------------------

        end_reason = None

        if match.matchterminatedbytime and match.winner:

            # Normal win: winner has all four coins at the center.
            winner_finished = sum(
                1
                for coin in coin_data
                if coin["playeruuid"] == match.winner
                and coin["finished"]
            )

            if winner_finished == 4:

                end_reason = "won"

            elif (
                match.terminatedby == 1
                and match.terminatedtime
            ):

                # For a terminated match, use the existing
                # last-move timestamps to distinguish
                # timeout from voluntary exit.

                if match.winner == match.initiateduseruuid:

                    loser_last_move = (
                        match.player2lastmovetime
                    )

                else:

                    loser_last_move = (
                        match.player1lastmovetime
                    )

                inactive = (
                    loser_last_move is not None
                    and
                    match.terminatedtime >=
                    loser_last_move +
                    timedelta(minutes=10)
                )

                if inactive:

                    end_reason = "opponent_inactive"

                else:

                    end_reason = "opponent_left"

            else:

                end_reason = "opponent_left"

        # -----------------------------------------
        # RETURN GAME STATE
        # -----------------------------------------

        return {
            "success": True,

            "match": {
                "matchbatchnumber":
                    match.matchbatchnumber,

                "player1": {
                    "uuid":
                        match.initiateduseruuid,

                    "color":
                        match.initiatedusercolor
                },

                "player2": {
                    "uuid":
                        match.secondplayeruuid,

                    "color":
                        match.secondplayercolor
                },

                "match_started":
                    bool(match.matchstarted),

                "terminated":
                    bool(match.matchterminatedbytime),

                "winner":
                    match.winner,

                "end_reason":
                    end_reason
            },

            "game": {
                "current_turn":
                    game.currentturnuuid,

                "last_dice":
                    game.lastdice,

                "consecutive_sixes":
                    game.consecutivesix,

                "move_pending":
                    bool(game.mustmove)
            },

            "coins":
                coin_data
        }

    except Exception:

        return {
            "success": False,
            "message": "Unable to fetch game state"
        }, 500

    finally:
        pass


@app.route(
    "/ludo-roll-dice/<matchbatchnumber>",
    methods=["POST"]
)
def ludo_roll_dice(matchbatchnumber):

    try:

        # =========================================
        # LOGIN CHECK
        # =========================================

        if "userid" not in session:

            return {
                "success": False,
                "message": "Not logged in"
            }, 401

        current_userid = session["userid"]

        # Real user activity
        update_user_activity()

        with db_engine.begin() as connection:

            # =========================================
            # GET MATCH
            # =========================================

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        matchstarted,
                        matchterminatedbytime
                    FROM usersmatches
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # =========================================
            # MATCH NOT FOUND
            # =========================================

            if not match:

                return {
                    "success": False,
                    "message": "Match not found"
                }, 404

            # =========================================
            # VERIFY PLAYER
            # =========================================

            if (
                current_userid !=
                match.initiateduseruuid

                and

                current_userid !=
                match.secondplayeruuid
            ):

                return {
                    "success": False,
                    "message":
                        "You are not part of this match"
                }, 403

            # =========================================
            # MATCH MUST BE STARTED
            # =========================================

            if not match.matchstarted:

                return {
                    "success": False,
                    "message":
                        "Match has not started"
                }, 400

            # =========================================
            # MATCH MUST NOT BE TERMINATED
            # =========================================

            if match.matchterminatedbytime:

                return {
                    "success": False,
                    "message":
                        "Match has already ended"
                }, 400

            # =========================================
            # GET GAME STATE
            # =========================================

            game = connection.execute(
                text("""
                    SELECT
                        currentturnuuid,
                        lastdice,
                        consecutivesix,
                        mustmove
                    FROM ludogamestate
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # =========================================
            # GAME STATE NOT FOUND
            # =========================================

            if not game:

                return {
                    "success": False,
                    "message":
                        "Game state not found"
                }, 404

            # =========================================
            # CHECK TURN
            # =========================================

            if (
                game.currentturnuuid
                !=
                current_userid
            ):

                return {
                    "success": False,
                    "message":
                        "It is not your turn"
                }, 403

            # =========================================
            # PREVENT SECOND ROLL
            # =========================================

            if game.mustmove:

                return {
                    "success": False,
                    "message":
                        "You must move a coin first"
                }, 400

            # =========================================
            # GENERATE DICE
            # =========================================

            dice = (
                uuid.uuid4().int % 6
            ) + 1

            # =========================================
            # CONSECUTIVE SIX
            # =========================================

            if dice == 6:

                consecutive6 = (
                    game.consecutivesix + 1
                )

            else:

                consecutive6 = 0

            # =========================================
            # THREE CONSECUTIVE SIXES
            # =========================================

            if consecutive6 >= 3:

                # Reset dice state.

                connection.execute(
                    text("""
                        UPDATE ludogamestate
                        SET
                            lastdice = 6,
                            consecutivesix = 0,
                            mustmove = 0
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

                # -----------------------------------------
                # GIVE TURN TO OPPONENT
                # -----------------------------------------

                if (
                    current_userid ==
                    match.initiateduseruuid
                ):

                    next_player = (
                        match.secondplayeruuid
                    )

                else:

                    next_player = (
                        match.initiateduseruuid
                    )

                connection.execute(
                    text("""
                        UPDATE ludogamestate
                        SET
                            currentturnuuid =
                                :next_player
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "next_player":
                            next_player,

                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

                # -----------------------------------------
                # UPDATE ACTIVITY TIME
                # -----------------------------------------

                if (
                    current_userid ==
                    match.initiateduseruuid
                ):

                    connection.execute(
                        text("""
                            UPDATE usersmatches
                            SET
                                player1lastmovetime =
                                    NOW()
                            WHERE
                                matchbatchnumber =
                                    :matchbatchnumber
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    )

                else:

                    connection.execute(
                        text("""
                            UPDATE usersmatches
                            SET
                                player2lastmovetime =
                                    NOW()
                            WHERE
                                matchbatchnumber =
                                    :matchbatchnumber
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    )

                return {

                    "success": True,

                    "dice": 6,

                    "consecutive6": 3,

                    "mustmove": False,

                    "turnended": True,

                    "nextturnuuid":
                        next_player
                }

            # =========================================
            # CHECK WHETHER ANY COIN CAN MOVE
            # =========================================

            movable_coin = connection.execute(
                text("""
                    SELECT
                        coinindex
                    FROM ludocoins
                    WHERE
                        matchbatchnumber =
                            :matchbatchnumber
                    AND
                        playeruuid =
                            :playeruuid
                    AND
                        finished = 0
                    AND
                        position >= 0
                    AND
                        stepsmoved + :dice <= 57
                    LIMIT 1
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber,

                    "playeruuid":
                        current_userid,

                    "dice":
                        dice
                }
            ).fetchone()

            # =========================================
            # NO LEGAL MOVE
            # =========================================

            if (
                dice != 6
                and
                not movable_coin
            ):

                # -----------------------------------------
                # DETERMINE NEXT PLAYER
                # -----------------------------------------

                if (
                    current_userid ==
                    match.initiateduseruuid
                ):

                    next_player = (
                        match.secondplayeruuid
                    )

                else:

                    next_player = (
                        match.initiateduseruuid
                    )

                # -----------------------------------------
                # UPDATE GAME STATE
                # -----------------------------------------

                connection.execute(
                    text("""
                        UPDATE ludogamestate
                        SET
                            currentturnuuid =
                                :next_player,

                            lastdice = NULL,

                            mustmove = 0,

                            consecutivesix = 0
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "next_player":
                            next_player,

                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

                # -----------------------------------------
                # UPDATE ACTIVITY TIME
                # -----------------------------------------

                if (
                    current_userid ==
                    match.initiateduseruuid
                ):

                    connection.execute(
                        text("""
                            UPDATE usersmatches
                            SET
                                player1lastmovetime =
                                    NOW()
                            WHERE
                                matchbatchnumber =
                                    :matchbatchnumber
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    )

                else:

                    connection.execute(
                        text("""
                            UPDATE usersmatches
                            SET
                                player2lastmovetime =
                                    NOW()
                            WHERE
                                matchbatchnumber =
                                    :matchbatchnumber
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber
                        }
                    )

                # -----------------------------------------
                # RETURN
                # -----------------------------------------

                return {

                    "success": True,

                    "dice": dice,

                    "consecutive6":
                        consecutive6,

                    "mustmove": False,

                    "turnended": True,

                    "nextturnuuid":
                        next_player
                }

            # =========================================
            # NORMAL DICE RESULT
            # =========================================

            connection.execute(
                text("""
                    UPDATE ludogamestate
                    SET
                        lastdice = :dice,

                        consecutivesix =
                            :consecutive6,

                        mustmove = 1
                    WHERE
                        matchbatchnumber =
                            :matchbatchnumber
                """),
                {
                    "dice":
                        dice,

                    "consecutive6":
                        consecutive6,

                    "matchbatchnumber":
                        matchbatchnumber
                }
            )

            # =========================================
            # UPDATE PLAYER ACTIVITY TIME
            # =========================================

            if (
                current_userid ==
                match.initiateduseruuid
            ):

                connection.execute(
                    text("""
                        UPDATE usersmatches
                        SET
                            player1lastmovetime =
                                NOW()
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

            else:

                connection.execute(
                    text("""
                        UPDATE usersmatches
                        SET
                            player2lastmovetime =
                                NOW()
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

        # =========================================
        # SUCCESS
        # =========================================

        return {

            "success": True,

            "dice":
                dice,

            "consecutive6":
                consecutive6,

            "mustmove": True,

            "turnended": False,

            "nextturnuuid":
                current_userid
        }

    except Exception:

        return {
            "success": False,
            "message":
                "Unable to roll dice"
        }, 500

    finally:
        pass


@app.route(
    "/ludo-move-coin/<matchbatchnumber>",
    methods=["POST"]
)
def ludo_move_coin(matchbatchnumber):

    try:

        # =========================================
        # LOGIN CHECK
        # =========================================

        if "userid" not in session:

            return {
                "success": False,
                "message": "Not logged in"
            }, 401

        current_userid = session["userid"]

        # Genuine user activity
        update_user_activity()

        # =========================================
        # GET REQUEST DATA
        # =========================================

        data = request.get_json(
            silent=True
        ) or {}

        try:

            coinindex = int(
                data.get("coinindex")
            )

        except (TypeError, ValueError):

            return {
                "success": False,
                "message": "Invalid coin"
            }, 400

        # =========================================
        # VALID COIN INDEX
        # =========================================

        if coinindex < 1 or coinindex > 4:

            return {
                "success": False,
                "message": "Invalid coin"
            }, 400

        with db_engine.begin() as connection:

            # =========================================
            # GET MATCH
            # =========================================

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        initiatedusercolor,
                        secondplayercolor,
                        matchstarted,
                        matchterminatedbytime,
                        winner
                    FROM usersmatches
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # =========================================
            # MATCH NOT FOUND
            # =========================================

            if not match:

                return {
                    "success": False,
                    "message":
                        "Match not found"
                }, 404

            # =========================================
            # VERIFY PLAYER
            # =========================================

            if (
                current_userid !=
                match.initiateduseruuid

                and

                current_userid !=
                match.secondplayeruuid
            ):

                return {
                    "success": False,
                    "message":
                        "You are not part of this match"
                }, 403

            # =========================================
            # MATCH MUST BE STARTED
            # =========================================

            if not match.matchstarted:

                return {
                    "success": False,
                    "message":
                        "Match has not started"
                }, 400

            # =========================================
            # MATCH MUST NOT BE TERMINATED
            # =========================================

            if match.matchterminatedbytime:

                return {
                    "success": False,
                    "message":
                        "Match has already ended"
                }, 400

            # =========================================
            # GET GAME STATE
            # =========================================

            game = connection.execute(
                text("""
                    SELECT
                        currentturnuuid,
                        lastdice,
                        consecutivesix,
                        mustmove
                    FROM ludogamestate
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # =========================================
            # GAME NOT FOUND
            # =========================================

            if not game:

                return {
                    "success": False,
                    "message":
                        "Game state not found"
                }, 404

            # =========================================
            # VERIFY TURN
            # =========================================

            if (
                game.currentturnuuid
                !=
                current_userid
            ):

                return {
                    "success": False,
                    "message":
                        "It is not your turn"
                }, 403

            # =========================================
            # VERIFY DICE
            # =========================================

            if not game.mustmove:

                return {
                    "success": False,
                    "message":
                        "Roll the dice first"
                }, 400

            if game.lastdice is None:

                return {
                    "success": False,
                    "message":
                        "Dice value not found"
                }, 400

            dice = int(
                game.lastdice
            )

            # =========================================
            # GET SELECTED COIN
            # =========================================

            coin = connection.execute(
                text("""
                    SELECT
                        coinindex,
                        position,
                        stepsmoved,
                        finished
                    FROM ludocoins
                    WHERE
                        matchbatchnumber =
                            :matchbatchnumber
                    AND
                        playeruuid =
                            :playeruuid
                    AND
                        coinindex =
                            :coinindex
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber,

                    "playeruuid":
                        current_userid,

                    "coinindex":
                        coinindex
                }
            ).fetchone()

            # =========================================
            # COIN NOT FOUND
            # =========================================

            if not coin:

                return {
                    "success": False,
                    "message":
                        "Coin not found"
                }, 404

            # =========================================
            # COIN ALREADY FINISHED
            # =========================================

            if coin.finished:

                return {
                    "success": False,
                    "message":
                        "This coin has already finished"
                }, 400

            current_position = int(
                coin.position
            )

            current_steps = int(
                coin.stepsmoved
            )

            # =========================================
            # HOME COIN
            # =========================================

            if current_position == -1:

                # A coin can leave home
                # only with a six.

                if dice != 6:

                    return {
                        "success": False,
                        "message":
                            "You need a 6 to move this coin out"
                    }, 400

                # Logical position 0
                # means the player's
                # starting square.

                new_position = 0
                new_steps = 0

            # =========================================
            # COIN ALREADY ON BOARD
            # =========================================

            else:

                new_steps = (
                    current_steps +
                    dice
                )

                new_position = new_steps

            # =========================================
            # CANNOT MOVE BEYOND FINISH
            # =========================================

            if new_steps > 57:

                return {
                    "success": False,
                    "message":
                        "This coin cannot move that far"
                }, 400

            # =========================================
            # UPDATE MOVING COIN
            # =========================================

            if new_steps == 57:

                connection.execute(
                    text("""
                        UPDATE ludocoins
                        SET
                            position = 57,
                            stepsmoved = 57,
                            finished = 1
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                        AND
                            playeruuid =
                                :playeruuid
                        AND
                            coinindex =
                                :coinindex
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber,

                        "playeruuid":
                            current_userid,

                        "coinindex":
                            coinindex
                    }
                )

            else:

                connection.execute(
                    text("""
                        UPDATE ludocoins
                        SET
                            position =
                                :position,

                            stepsmoved =
                                :stepsmoved
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                        AND
                            playeruuid =
                                :playeruuid
                        AND
                            coinindex =
                                :coinindex
                    """),
                    {
                        "position":
                            new_position,

                        "stepsmoved":
                            new_steps,

                        "matchbatchnumber":
                            matchbatchnumber,

                        "playeruuid":
                            current_userid,

                        "coinindex":
                            coinindex
                    }
                )

            # =========================================
            # CAPTURE INFORMATION
            # =========================================

            captured_coins = []

            # Capture is possible only while
            # the coin is on the main 52-cell
            # track.

            if (
                0 <= new_position <= 51
            ):

                # =====================================
                # COLOR BASED START POSITIONS
                # =====================================

                COLOR_START_POSITIONS = {

                    "red": 0,

                    "green": 13,

                    "yellow": 26,

                    "blue": 39
                }

                # =====================================
                # SAFE PHYSICAL POSITIONS
                #
                # Based on the actual board.
                # =====================================

                LUDO_SAFE_POSITIONS = {
                    8,
                    21,
                    34,
                    47,
                    0,
                    13,
                    26,
                    39
                }

                # =====================================
                # DETERMINE MOVING PLAYER COLOR
                # =====================================

                if (
                    current_userid ==
                    match.initiateduseruuid
                ):

                    moving_color = (
                        match.initiatedusercolor
                    )

                    opponent_uuid = (
                        match.secondplayeruuid
                    )

                else:

                    moving_color = (
                        match.secondplayercolor
                    )

                    opponent_uuid = (
                        match.initiateduseruuid
                    )

                # =====================================
                # GET MOVING PLAYER START POSITION
                # =====================================

                moving_start_position = (
                    COLOR_START_POSITIONS.get(
                        moving_color
                    )
                )

                if (
                    moving_start_position
                    is None
                ):

                    return {
                        "success": False,
                        "message":
                            "Invalid player color"
                    }, 400

                # =====================================
                # CONVERT LOGICAL → PHYSICAL
                # =====================================

                moving_physical_position = (
                    (
                        moving_start_position
                        +
                        new_position
                    ) % 52
                )

                # =====================================
                # ONLY CAPTURE ON NON-SAFE CELL
                # =====================================

                if (
                    moving_physical_position
                    not in
                    LUDO_SAFE_POSITIONS
                ):

                    # =================================
                    # GET OPPONENT COINS
                    # =================================

                    opponent_coins = connection.execute(
                        text("""
                            SELECT
                                coinindex,
                                position,
                                stepsmoved,
                                finished
                            FROM ludocoins
                            WHERE
                                matchbatchnumber =
                                    :matchbatchnumber
                            AND
                                playeruuid =
                                    :opponent_uuid
                            AND
                                finished = 0
                            AND
                                position >= 0
                            AND
                                position <= 51
                            FOR UPDATE
                        """),
                        {
                            "matchbatchnumber":
                                matchbatchnumber,

                            "opponent_uuid":
                                opponent_uuid
                        }
                    ).fetchall()

                    same_cell_coins = []

                    # =================================
                    # FIND OPPONENT COINS
                    # ON SAME PHYSICAL CELL
                    # =================================

                    for opponent_coin in opponent_coins:

                        opponent_position = int(
                            opponent_coin.position
                        )

                        # =================================
                        # DETERMINE OPPONENT COLOR
                        # =================================

                        if (
                            opponent_uuid ==
                            match.initiateduseruuid
                        ):

                            opponent_color = (
                                match.initiatedusercolor
                            )

                        else:

                            opponent_color = (
                                match.secondplayercolor
                            )

                        # =================================
                        # GET OPPONENT START POSITION
                        # =================================

                        opponent_start_position = (
                            COLOR_START_POSITIONS.get(
                                opponent_color
                            )
                        )

                        if (
                            opponent_start_position
                            is None
                        ):

                            continue

                        # =================================
                        # CONVERT OPPONENT
                        # LOGICAL → PHYSICAL
                        # =================================

                        opponent_physical_position = (
                            (
                                opponent_start_position
                                +
                                opponent_position
                            ) % 52
                        )

                        # =================================
                        # SAME PHYSICAL CELL
                        # =================================

                        if (
                            opponent_physical_position
                            ==
                            moving_physical_position
                        ):

                            same_cell_coins.append(
                                opponent_coin
                            )

                    # =================================
                    # CAPTURE ONE COIN
                    #
                    # Two opponent coins on the
                    # same square form a block.
                    # =================================

                    if len(same_cell_coins) == 1:

                        captured_coin = (
                            same_cell_coins[0]
                        )

                        connection.execute(
                            text("""
                                UPDATE ludocoins
                                SET
                                    position = -1,
                                    stepsmoved = 0,
                                    finished = 0
                                WHERE
                                    matchbatchnumber =
                                        :matchbatchnumber
                                AND
                                    playeruuid =
                                        :opponent_uuid
                                AND
                                    coinindex =
                                        :coinindex
                            """),
                            {
                                "matchbatchnumber":
                                    matchbatchnumber,

                                "opponent_uuid":
                                    opponent_uuid,

                                "coinindex":
                                    captured_coin.coinindex
                            }
                        )

                        captured_coins.append(
                            int(
                                captured_coin.coinindex
                            )
                        )

            # =========================================
            # UPDATE PLAYER ACTIVITY TIME
            # =========================================

            if (
                current_userid ==
                match.initiateduseruuid
            ):

                connection.execute(
                    text("""
                        UPDATE usersmatches
                        SET
                            player1lastmovetime =
                                NOW()
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

            else:

                connection.execute(
                    text("""
                        UPDATE usersmatches
                        SET
                            player2lastmovetime =
                                NOW()
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

            # =========================================
            # CHECK PLAYER WIN
            # =========================================

            finished_count = connection.execute(
                text("""
                    SELECT COUNT(*) AS total
                    FROM ludocoins
                    WHERE
                        matchbatchnumber =
                            :matchbatchnumber
                    AND
                        playeruuid =
                            :playeruuid
                    AND
                        finished = 1
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber,

                    "playeruuid":
                        current_userid
                }
            ).fetchone()

            # =========================================
            # PLAYER WON
            # =========================================

            if (
                finished_count
                and
                int(finished_count.total) == 4
            ):

                connection.execute(
                    text("""
                        UPDATE usersmatches
                        SET
                            winner = :winner,
                            matchterminatedbytime = 1,
                            terminatedtime = NOW()
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                            AND
                            matchterminatedbytime = 0
                    """),
                    {
                        "winner":
                            current_userid,

                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

                # Clear consumed dice.

                connection.execute(
                    text("""
                        UPDATE ludogamestate
                        SET
                            lastdice = NULL,
                            mustmove = 0
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

                return {
                    "success": True,

                    "coinindex":
                        coinindex,

                    "position":
                        new_position,

                    "stepsmoved":
                        new_steps,

                    "finished":
                        True,

                    "winner":
                        current_userid,

                    "gameover":
                        True,

                    "dice":
                        dice,

                    "captured_coins":
                        captured_coins
                }

            # =========================================
            # REACHED CENTER
            #
            # SAME PLAYER GETS EXTRA TURN
            # =========================================

            if new_steps == 57:

                connection.execute(
                    text("""
                        UPDATE ludogamestate
                        SET
                            currentturnuuid =
                                :currentturn,

                            lastdice = NULL,

                            mustmove = 0
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "currentturn":
                            current_userid,

                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

                next_turn = current_userid

            # =========================================
            # SIX
            #
            # SAME PLAYER KEEPS TURN
            # =========================================

            elif dice == 6:

                connection.execute(
                    text("""
                        UPDATE ludogamestate
                        SET
                            currentturnuuid =
                                :currentturn,

                            lastdice = NULL,

                            mustmove = 0
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "currentturn":
                            current_userid,

                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

                next_turn = current_userid

            # =========================================
            # NORMAL MOVE
            #
            # OTHER PLAYER GETS TURN
            # =========================================

            else:

                if (
                    current_userid ==
                    match.initiateduseruuid
                ):

                    next_turn = (
                        match.secondplayeruuid
                    )

                else:

                    next_turn = (
                        match.initiateduseruuid
                    )

                connection.execute(
                    text("""
                        UPDATE ludogamestate
                        SET
                            currentturnuuid =
                                :nextturn,

                            lastdice = NULL,

                            mustmove = 0,

                            consecutivesix = 0
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                    """),
                    {
                        "nextturn":
                            next_turn,

                        "matchbatchnumber":
                            matchbatchnumber
                    }
                )

            # =========================================
            # SUCCESS
            # =========================================

            return {

                "success": True,

                "coinindex":
                    coinindex,

                "position":
                    new_position,

                "stepsmoved":
                    new_steps,

                "finished":
                    new_steps == 57,

                "dice":
                    dice,

                "nextturnuuid":
                    next_turn,

                "captured_coins":
                    captured_coins
            }

    except Exception:

        return {
            "success": False,
            "message":
                "Unable to move coin"
        }, 500

    finally:
        pass


@app.route(
    "/exit-match/<matchbatchnumber>",
    methods=["POST"]
)
def exit_match(matchbatchnumber):

    try:

        # -----------------------------------------
        # LOGIN CHECK
        # -----------------------------------------

        if "userid" not in session:
            return redirect(
                url_for("login")
            )

        current_userid = session["userid"]

        # Genuine user activity
        update_user_activity()

        with db_engine.begin() as connection:

            # -----------------------------------------
            # GET ACTIVE MATCH
            # -----------------------------------------

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        matchstarted,
                        matchterminatedbytime
                    FROM usersmatches
                    WHERE
                        matchbatchnumber = :matchbatchnumber
                    LIMIT 1
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # -----------------------------------------
            # MATCH NOT FOUND
            # -----------------------------------------

            if not match:

                flash(
                    "Match not found.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # -----------------------------------------
            # VERIFY PLAYER
            # -----------------------------------------

            if (
                current_userid !=
                match.initiateduseruuid

                and

                current_userid !=
                match.secondplayeruuid
            ):

                flash(
                    "You are not part of this match.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # -----------------------------------------
            # MATCH ALREADY TERMINATED
            # -----------------------------------------

            if match.matchterminatedbytime:

                flash(
                    "This match has already ended.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # -----------------------------------------
            # MATCH MUST HAVE STARTED
            # -----------------------------------------

            if not match.matchstarted:

                flash(
                    "This match has not started yet.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # -----------------------------------------
            # DETERMINE WINNER
            # -----------------------------------------

            if current_userid == match.initiateduseruuid:

                winner = match.secondplayeruuid

            else:

                winner = match.initiateduseruuid

            # -----------------------------------------
            # TERMINATE MATCH
            # -----------------------------------------

            connection.execute(
                text("""
                    UPDATE usersmatches
                    SET
                        matchterminatedbytime = 1,
                        terminatedby = 1,
                        terminatedtime = NOW(),
                        winner = :winner
                    WHERE
                        matchbatchnumber =
                            :matchbatchnumber
                        AND
                        matchterminatedbytime = 0
                """),
                {
                    "winner": winner,

                    "matchbatchnumber":
                        matchbatchnumber
                }
            )

        flash(
            "You exited the match. The match has been terminated.",
            "success"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    except Exception:

        flash(
            "Unable to exit the match. Please try again.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass


@app.route(
    "/terminate-match/<matchbatchnumber>",
    methods=["POST"]
)
def terminate_match(matchbatchnumber):

    try:

        # =========================================
        # LOGIN CHECK
        # =========================================

        if "userid" not in session:
            return redirect(
                url_for("login")
            )

        current_userid = session["userid"]

        # Genuine user activity
        update_user_activity()

        # =========================================
        # EVERYTHING BELOW IS ONE TRANSACTION
        # =========================================

        with db_engine.begin() as connection:

            # =========================================
            # GET AND LOCK THE MATCH
            # =========================================

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        amount,
                        matchstarted,
                        matchterminatedbytime,
                        winner
                    FROM usersmatches
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # =========================================
            # MATCH NOT FOUND
            # =========================================

            if not match:

                flash(
                    "Match not found.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # =========================================
            # VERIFY CURRENT PLAYER
            # =========================================

            if (
                current_userid !=
                match.initiateduseruuid

                and

                current_userid !=
                match.secondplayeruuid
            ):

                flash(
                    "You are not a player in this match.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # =========================================
            # MATCH ALREADY TERMINATED
            # =========================================

            if match.matchterminatedbytime:

                flash(
                    "This match has already ended.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # =========================================
            # MATCH MUST HAVE STARTED
            # =========================================

            if not match.matchstarted:

                flash(
                    "This match has not started yet.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # =========================================
            # CHECK SECOND PLAYER EXISTS
            # =========================================

            if not match.secondplayeruuid:

                flash(
                    "The other player has not joined this match.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # =========================================
            # DETERMINE LOSER AND WINNER
            # =========================================

            loser_uuid = current_userid

            if current_userid == match.initiateduseruuid:

                winner_uuid = match.secondplayeruuid

            else:

                winner_uuid = match.initiateduseruuid

            # =========================================
            # MATCH AMOUNT
            # =========================================

            match_amount = match.amount

            # =========================================
            # TOTAL MATCH AMOUNT
            #
            # Player 1 amount + Player 2 amount
            # =========================================

            total_amount = match_amount * 2

            # =========================================
            # 15% ADMIN COMMISSION
            # =========================================

            commission_amount = (
                total_amount * 15 / 100
            )

            # =========================================
            # WINNER'S NET GAIN
            #
            # Winner already owns his own amount.
            #
            # Therefore only the loser's amount
            # minus commission is added.
            # =========================================

            winner_gain = (
                match_amount -
                commission_amount
            )

            # =========================================
            # LOCK BOTH USER BALANCES
            # =========================================

            users = connection.execute(
                text("""
                    SELECT
                        userid,
                        money
                    FROM lpusers
                    WHERE userid IN (
                        :loser_uuid,
                        :winner_uuid
                    )
                    ORDER BY userid
                    FOR UPDATE
                """),
                {
                    "loser_uuid":
                        loser_uuid,

                    "winner_uuid":
                        winner_uuid
                }
            ).fetchall()

            if len(users) != 2:

                flash(
                    "Unable to find both players.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # =========================================
            # GET LOSER FROM ALREADY LOCKED USERS
            # =========================================

            loser = next(
                (
                    user
                    for user in users
                    if user.userid == loser_uuid
                ),
                None
            )

            # =========================================
            # CHECK LOSER BALANCE
            #
            # Important because the money was NOT
            # deducted when the match started.
            # =========================================

            if not loser:

                flash(
                    "Player account not found.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            if loser.money < match_amount:

                flash(
                    "The player's balance is insufficient to settle this match.",
                    "error"
                )

                return redirect(
                    url_for("classic_dashboard")
                )

            # =========================================
            # DEDUCT LOSER'S AMOUNT
            # =========================================

            connection.execute(
                text("""
                    UPDATE lpusers
                    SET money = money - :amount
                    WHERE userid = :userid
                """),
                {
                    "amount":
                        match_amount,

                    "userid":
                        loser_uuid
                }
            )

            # =========================================
            # ADD WINNER'S NET GAIN
            # =========================================

            connection.execute(
                text("""
                    UPDATE lpusers
                    SET money = money + :winner_gain
                    WHERE userid = :userid
                """),
                {
                    "winner_gain":
                        winner_gain,

                    "userid":
                        winner_uuid
                }
            )

            # =========================================
            # RECORD ADMIN COMMISSION
            # =========================================

            connection.execute(
                text("""
                    INSERT INTO adminscommision
                    (
                        batchnumber,
                        totalamount,
                        commisionamount,
                        timestamp
                    )
                    VALUES
                    (
                        :batchnumber,
                        :totalamount,
                        :commission_amount,
                        NOW()
                    )
                """),
                {
                    "batchnumber":
                        matchbatchnumber,

                    "totalamount":
                        total_amount,

                    "commission_amount":
                        commission_amount
                }
            )

            # =========================================
            # TERMINATE MATCH
            # =========================================

            connection.execute(
                text("""
                    UPDATE usersmatches
                    SET
                        matchterminatedbytime = 1,
                        terminatedby = 1,
                        terminatedtime = NOW(),
                        winner = :winner
                    WHERE
                        matchbatchnumber =
                            :matchbatchnumber
                        AND
                        matchterminatedbytime = 0
                """),
                {
                    "winner":
                        winner_uuid,

                    "matchbatchnumber":
                        matchbatchnumber
                }
            )

        # =========================================
        # SUCCESS
        # =========================================

        flash(
            "You exited the match. The match has been terminated.",
            "success"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    except Exception:

        flash(
            "Unable to terminate the match.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass

@app.route(
    "/ludo/initialize/<matchbatchnumber>",
    methods=["POST"]
)
def initialize_ludo_game(matchbatchnumber):

    try:

        # -----------------------------------------
        # LOGIN CHECK
        # -----------------------------------------

        if "userid" not in session:

            return {
                "success": False,
                "message": "Not logged in"
            }, 401

        current_userid = session["userid"]

        # Genuine user activity
        update_user_activity()

        with db_engine.begin() as connection:

            # -----------------------------------------
            # GET MATCH
            # -----------------------------------------

            match = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        matchstarted,
                        matchterminatedbytime
                    FROM usersmatches
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # -----------------------------------------
            # MATCH NOT FOUND
            # -----------------------------------------

            if not match:

                return {
                    "success": False,
                    "message": "Match not found"
                }, 404

            # -----------------------------------------
            # VERIFY CURRENT USER
            # -----------------------------------------

            if (
                current_userid !=
                match.initiateduseruuid

                and

                current_userid !=
                match.secondplayeruuid
            ):

                return {
                    "success": False,
                    "message":
                        "You are not a player in this match"
                }, 403

            # -----------------------------------------
            # MATCH MUST BE STARTED
            # -----------------------------------------

            if not match.matchstarted:

                return {
                    "success": False,
                    "message":
                        "Match has not started yet"
                }, 400

            # -----------------------------------------
            # MATCH MUST NOT BE TERMINATED
            # -----------------------------------------

            if match.matchterminatedbytime:

                return {
                    "success": False,
                    "message":
                        "Match has already ended"
                }, 400

            # -----------------------------------------
            # BOTH PLAYERS MUST EXIST
            # -----------------------------------------

            if not match.secondplayeruuid:

                return {
                    "success": False,
                    "message":
                        "Second player not found"
                }, 400

            # -----------------------------------------
            # CHECK WHETHER GAME ALREADY EXISTS
            # -----------------------------------------

            existing_game = connection.execute(
                text("""
                    SELECT
                        id
                    FROM ludogamestate
                    WHERE matchbatchnumber =
                        :matchbatchnumber
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber
                }
            ).fetchone()

            # -----------------------------------------
            # GAME ALREADY INITIALIZED
            # -----------------------------------------

            if existing_game:

                return {
                    "success": True,
                    "message":
                        "Ludo game already initialized",
                    "matchbatchnumber":
                        matchbatchnumber
                }

            # -----------------------------------------
            # CREATE GAME STATE
            # -----------------------------------------

            connection.execute(
                text("""
                    INSERT INTO ludogamestate
                    (
                        matchbatchnumber,
                        currentturnuuid,
                        lastdice,
                        consecutivesix,
                        mustmove
                    )
                    VALUES
                    (
                        :matchbatchnumber,
                        :currentturnuuid,
                        NULL,
                        0,
                        0
                    )
                """),
                {
                    "matchbatchnumber":
                        matchbatchnumber,

                    # Player 1 starts initially
                    "currentturnuuid":
                        match.initiateduseruuid
                }
            )

            # -----------------------------------------
            # CREATE PLAYER 1 COINS
            # -----------------------------------------

            for coinindex in range(1, 5):

                connection.execute(
                    text("""
                        INSERT INTO ludocoins
                        (
                            matchbatchnumber,
                            playeruuid,
                            coinindex,
                            position,
                            stepsmoved,
                            finished
                        )
                        VALUES
                        (
                            :matchbatchnumber,
                            :playeruuid,
                            :coinindex,
                            -1,
                            0,
                            0
                        )
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber,

                        "playeruuid":
                            match.initiateduseruuid,

                        "coinindex":
                            coinindex
                    }
                )

            # -----------------------------------------
            # CREATE PLAYER 2 COINS
            # -----------------------------------------

            for coinindex in range(1, 5):

                connection.execute(
                    text("""
                        INSERT INTO ludocoins
                        (
                            matchbatchnumber,
                            playeruuid,
                            coinindex,
                            position,
                            stepsmoved,
                            finished
                        )
                        VALUES
                        (
                            :matchbatchnumber,
                            :playeruuid,
                            :coinindex,
                            -1,
                            0,
                            0
                        )
                    """),
                    {
                        "matchbatchnumber":
                            matchbatchnumber,

                        "playeruuid":
                            match.secondplayeruuid,

                        "coinindex":
                            coinindex
                    }
                )

        # -----------------------------------------
        # SUCCESS
        # -----------------------------------------

        return {
            "success": True,
            "message":
                "Ludo game initialized successfully",
            "matchbatchnumber":
                matchbatchnumber
        }

    except Exception:

        return {
            "success": False,
            "message":
                "Unable to initialize Ludo game"
        }, 500

    finally:
        pass


@app.route("/save-account-details", methods=["POST"])
def save_account_details():

    try:

        if "userid" not in session:
            return redirect(
                url_for("login")
            )

        # Genuine user activity
        update_user_activity()

        bankname = request.form.get(
            "bankname",
            ""
        ).strip()

        bankaccountnumber = request.form.get(
            "bankaccountnumber",
            ""
        ).strip()

        ifsccode = request.form.get(
            "ifsccode",
            ""
        ).strip()

        upiid = request.form.get(
            "upiid",
            ""
        ).strip()

        bank_complete = (
            bankname
            and bankaccountnumber
            and ifsccode
        )

        upi_complete = bool(upiid)

        if not bank_complete and not upi_complete:

            flash(
                "Please fill either your UPI ID or complete bank details.",
                "error"
            )

            return redirect(
                url_for("classic_dashboard")
            )

        with db_engine.begin() as connection:

            connection.execute(
                text("""
                    UPDATE lpusers
                    SET
                        bankname = :bankname,
                        bankaccountnumber = :bankaccountnumber,
                        ifsccode = :ifsccode,
                        upiid = :upiid
                    WHERE userid = :userid
                """),
                {
                    "bankname":
                        bankname if bank_complete else None,

                    "bankaccountnumber":
                        bankaccountnumber
                        if bank_complete
                        else None,

                    "ifsccode":
                        ifsccode if bank_complete else None,

                    "upiid":
                        upiid if upi_complete else None,

                    "userid":
                        session["userid"]
                }
            )

        flash(
            "Account details updated successfully.",
            "success"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    except Exception:

        flash(
            "Unable to update account details. Please try again.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass

@app.route("/balance", methods=["GET", "POST"])
def balance():

    try:

        if "userid" not in session:
            return redirect(
                url_for("login")
            )

        current_userid = session["userid"]

        # Genuine authenticated user activity
        update_user_activity()

        if request.method == "POST":

            topupid = str(
                uuid.uuid4()
            )

            amount = float(
                request.form.get("amount")
            )

            utr = str(
                request.form.get("utr")
            ).strip()

            date = request.form.get("date")

            with db_engine.begin() as connection:

                phone = connection.execute(
                    text("""
                        SELECT
                            phonenumber
                        FROM lpusers
                        WHERE userid = :userid
                    """),
                    {
                        "userid":
                            current_userid
                    }
                ).fetchone()

                connection.execute(
                    text("""
                        INSERT INTO topup
                        (
                            topupid,
                            userid,
                            phonenumber,
                            amount,
                            date,
                            utr,
                            approvedbysecondary
                        )
                        VALUES
                        (
                            :topupid,
                            :userid,
                            :phonenumber,
                            :amount,
                            :date,
                            :utr,
                            :approvedbysecondary
                        )
                    """),
                    {
                        "topupid":
                            topupid,

                        "userid":
                            current_userid,

                        "phonenumber":
                            phone.phonenumber,

                        "amount":
                            amount,

                        "date":
                            date,

                        "utr":
                            utr,

                        "approvedbysecondary":
                            True
                    }
                )

            flash(
                "Top-up request submitted successfully.",
                "success"
            )

            return redirect(
                url_for("balance")
            )

        # =========================================
        # GET ACCOUNT DETAILS + TOP-UP HISTORY
        # =========================================

        with db_engine.begin() as connection:

            account = connection.execute(
                text("""
                    SELECT
                        bankaccountnumber,
                        name,
                        ifsccode,
                        upiid
                    FROM accountdetails
                    WHERE id = 1
                """)
            ).fetchone()

            topups = connection.execute(
                text("""
                    SELECT
                        amount,
                        utr,
                        date,
                        status,
                        approvedbyprimary
                    FROM topup
                    WHERE userid = :userid
                    ORDER BY timestamp DESC
                """),
                {
                    "userid":
                        current_userid
                }
            ).fetchall()

        return render_template(
            "balance.html",
            account=account,
            topups=topups
        )

    except Exception:

        flash(
            "Unable to process your balance request. Please try again.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass

@app.route("/withdrawal", methods=["GET", "POST"])
def withdrawal():

    try:

        if "userid" not in session:
            return redirect(
                url_for("login")
            )

        current_userid = session["userid"]

        # Genuine authenticated user activity
        update_user_activity()

        if request.method == "POST":

            withdrawalid = str(
                uuid.uuid4()
            )

            try:
                amount = float(
                    request.form.get("amount", 0)
                )
            except (ValueError, TypeError):

                flash(
                    "Invalid amount.",
                    "error"
                )

                return redirect(
                    url_for("withdrawal")
                )

            paymentmethod = request.form.get(
                "paymentmethod"
            )

            with db_engine.begin() as connection:

                user = connection.execute(
                    text("""
                        SELECT
                            money,
                            bankname,
                            bankaccountnumber,
                            ifsccode,
                            upiid
                        FROM lpusers
                        WHERE userid = :userid
                    """),
                    {
                        "userid":
                            current_userid
                    }
                ).fetchone()

                if not user:

                    flash(
                        "User not found.",
                        "error"
                    )

                    return redirect(
                        url_for("logout")
                    )

                # -----------------------------------------
                # CHECK BALANCE
                # -----------------------------------------

                if user.money < amount:

                    flash(
                        "Balance not available.",
                        "error"
                    )

                    return redirect(
                        url_for("withdrawal")
                    )

                # -----------------------------------------
                # BANK WITHDRAWAL
                # -----------------------------------------

                if paymentmethod == "bank":

                    if (
                        not user.bankname
                        or
                        not user.bankaccountnumber
                        or
                        not user.ifsccode
                    ):

                        flash(
                            "Please fill up your bank details first.",
                            "error"
                        )

                        return redirect(
                            url_for("withdrawal")
                        )

                # -----------------------------------------
                # UPI WITHDRAWAL
                # -----------------------------------------

                elif paymentmethod == "upi":

                    if not user.upiid:

                        flash(
                            "Please fill up your UPI ID first.",
                            "error"
                        )

                        return redirect(
                            url_for("withdrawal")
                        )

                else:

                    flash(
                        "Please select a payment method.",
                        "error"
                    )

                    return redirect(
                        url_for("withdrawal")
                    )

                # -----------------------------------------
                # INSERT WITHDRAWAL REQUEST
                # -----------------------------------------

                connection.execute(
                    text("""
                        INSERT INTO withdrawals
                        (
                            withdrawalid,
                            userid,
                            amount,
                            utr,
                            status,
                            primaryapprovedby,
                            secondaryapprovedby
                        )
                        VALUES
                        (
                            :withdrawalid,
                            :userid,
                            :amount,
                            NULL,
                            'Pending',
                            0,
                            0
                        )
                    """),
                    {
                        "withdrawalid":
                            withdrawalid,

                        "userid":
                            current_userid,

                        "amount":
                            amount
                    }
                )

            flash(
                "Withdrawal request submitted successfully.",
                "success"
            )

            return redirect(
                url_for("withdrawal")
            )

        # =========================================
        # GET WITHDRAWAL HISTORY
        # =========================================

        with db_engine.begin() as connection:

            withdrawals = connection.execute(
                text("""
                    SELECT
                        amount,
                        utr,
                        status,
                        primaryapprovedby
                    FROM withdrawals
                    WHERE userid = :userid
                    ORDER BY timestamp DESC
                """),
                {
                    "userid":
                        current_userid
                }
            ).fetchall()

        return render_template(
            "withdrawal.html",
            withdrawals=withdrawals
        )

    except Exception:

        flash(
            "Unable to process your withdrawal request. Please try again.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass

@app.route("/profile", methods=["GET", "POST"])
def profile():

    try:

        if "userid" not in session:
            return redirect(
                url_for("login")
            )

        current_userid = session["userid"]

        # Genuine authenticated user activity
        update_user_activity()

        with db_engine.begin() as connection:

            if request.method == "POST":

                newpassword = str(
                    request.form.get("password", "")
                ).strip()

                limit = connection.execute(
                    text("""
                        SELECT
                            updatecount,
                            windowstart,
                            status
                        FROM passwordupdatelimits
                        WHERE userid = :userid
                    """),
                    {
                        "userid":
                            current_userid
                    }
                ).fetchone()

                # First Password Update
                if not limit:

                    connection.execute(
                        text("""
                            INSERT INTO passwordupdatelimits
                            (
                                userid,
                                updatecount,
                                windowstart,
                                status
                            )
                            VALUES
                            (
                                :userid,
                                1,
                                NOW(),
                                1
                            )
                        """),
                        {
                            "userid":
                                current_userid
                        }
                    )

                else:

                    windowstart = limit.windowstart

                    if (
                        windowstart
                        and
                        datetime.now() >=
                        windowstart +
                        timedelta(hours=24)
                    ):

                        connection.execute(
                            text("""
                                UPDATE passwordupdatelimits
                                SET
                                    updatecount = 1,
                                    windowstart = NOW(),
                                    status = 1
                                WHERE userid = :userid
                            """),
                            {
                                "userid":
                                    current_userid
                            }
                        )

                    elif limit.updatecount >= 5:

                        flash(
                            "You have used the daily password update limit.",
                            "error"
                        )

                        return redirect(
                            url_for("profile")
                        )

                    else:

                        connection.execute(
                            text("""
                                UPDATE passwordupdatelimits
                                SET
                                    updatecount =
                                        updatecount + 1
                                WHERE userid = :userid
                            """),
                            {
                                "userid":
                                    current_userid
                            }
                        )

                # Update Password
                connection.execute(
                    text("""
                        UPDATE lpusers
                        SET password = :password
                        WHERE userid = :userid
                    """),
                    {
                        "password":
                            newpassword,

                        "userid":
                            current_userid
                    }
                )

                flash(
                    "Password updated successfully.",
                    "success"
                )

                return redirect(
                    url_for("profile")
                )

            user = connection.execute(
                text("""
                    SELECT
                        username,
                        phonenumber
                    FROM lpusers
                    WHERE userid = :userid
                """),
                {
                    "userid":
                        current_userid
                }
            ).fetchone()

        return render_template(
            "profile.html",
            user=user
        )

    except Exception:

        flash(
            "Unable to process your profile request. Please try again.",
            "error"
        )

        return redirect(
            url_for("classic_dashboard")
        )

    finally:
        pass


@app.route("/matches")
def matches():

    if "userid" not in session:
        return redirect(url_for("login"))

    current_userid = session["userid"]

    try:

        # =====================================
        # PAGINATION
        # =====================================

        page = request.args.get(
            "page",
            1,
            type=int
        )

        if page < 1:
            page = 1

        per_page = 20

        offset = (
            page - 1
        ) * per_page


        with db_engine.begin() as connection:

            # =====================================
            # TOTAL MATCH COUNT
            # =====================================

            count_result = connection.execute(
                text("""
                    SELECT
                        COUNT(*) AS total

                    FROM usersmatches

                    WHERE secondplayeruuid =
                        :userid
                """),
                {
                    "userid":
                        current_userid
                }
            ).fetchone()

            total_matches = int(
                count_result.total
            )


            # =====================================
            # GET MATCHES
            # =====================================

            played_matches = connection.execute(
                text("""
                    SELECT

                        m.matchbatchnumber,

                        m.amount,

                        m.initiateduseruuid,

                        m.secondplayeruuid,

                        m.winner,

                        p1.username AS player1_username,

                        p2.username AS player2_username,

                        w.username AS winner_username

                    FROM usersmatches m

                    LEFT JOIN lpusers p1
                        ON p1.userid =
                            m.initiateduseruuid

                    LEFT JOIN lpusers p2
                        ON p2.userid =
                            m.secondplayeruuid

                    LEFT JOIN lpusers w
                        ON w.userid =
                            m.winner

                    WHERE m.secondplayeruuid =
                        :userid

                    ORDER BY
                        m.matchstarttime DESC

                    LIMIT :limit

                    OFFSET :offset
                """),
                {
                    "userid":
                        current_userid,

                    "limit":
                        per_page,

                    "offset":
                        offset
                }
            ).fetchall()


        # =====================================
        # TOTAL PAGES
        # =====================================

        total_pages = (
            (
                total_matches +
                per_page -
                1
            )
            // per_page
        )


        return render_template(
            "matches.html",

            played_matches=
                played_matches,

            page=
                page,

            total_pages=
                total_pages
        )


    except Exception:

        return {
            "success": False,
            "message": "Unable to load matches"
        }, 500


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

def check_match_timeouts():

    try:

        with db_engine.begin() as connection:

            # =========================================
            # GET ALL ACTIVE MATCHES
            # =========================================

            matches = connection.execute(
                text("""
                    SELECT
                        matchbatchnumber,
                        initiateduseruuid,
                        secondplayeruuid,
                        amount,
                        player1lastmovetime,
                        player2lastmovetime,
                        matchstarted,
                        matchterminatedbytime

                    FROM usersmatches

                    WHERE
                        matchstarted = 1
                        AND matchterminatedbytime = 0
                        AND secondplayeruuid IS NOT NULL

                    FOR UPDATE
                """)
            ).fetchall()


            # =========================================
            # CHECK EACH MATCH
            # =========================================

            for match in matches:

                loser_uuid = None
                winner_uuid = None


                # =====================================
                # PLAYER 1 TIMEOUT
                # =====================================

                if match.player1lastmovetime:

                    result = connection.execute(
                        text("""
                            SELECT
                                NOW() >= DATE_ADD(
                                    :lastmovetime,
                                    INTERVAL 10 MINUTE
                                ) AS expired
                        """),
                        {
                            "lastmovetime":
                                match.player1lastmovetime
                        }
                    ).fetchone()

                    if result and result.expired:

                        loser_uuid = (
                            match.initiateduseruuid
                        )

                        winner_uuid = (
                            match.secondplayeruuid
                        )


                # =====================================
                # PLAYER 2 TIMEOUT
                # =====================================

                if (
                    not loser_uuid
                    and
                    match.player2lastmovetime
                ):

                    result = connection.execute(
                        text("""
                            SELECT
                                NOW() >= DATE_ADD(
                                    :lastmovetime,
                                    INTERVAL 10 MINUTE
                                ) AS expired
                        """),
                        {
                            "lastmovetime":
                                match.player2lastmovetime
                        }
                    ).fetchone()

                    if result and result.expired:

                        loser_uuid = (
                            match.secondplayeruuid
                        )

                        winner_uuid = (
                            match.initiateduseruuid
                        )


                # =====================================
                # NO TIMEOUT
                # =====================================

                if not loser_uuid:

                    continue


                # =====================================
                # PREVENT DOUBLE TERMINATION
                # =====================================

                current_match = connection.execute(
                    text("""
                        SELECT
                            matchterminatedbytime
                        FROM usersmatches
                        WHERE matchbatchnumber =
                            :matchbatchnumber
                        FOR UPDATE
                    """),
                    {
                        "matchbatchnumber":
                            match.matchbatchnumber
                    }
                ).fetchone()


                if (
                    not current_match
                    or
                    current_match.matchterminatedbytime
                ):

                    continue


                # =====================================
                # MATCH AMOUNT
                # =====================================

                match_amount = match.amount


                # =====================================
                # TOTAL AMOUNT
                #
                # PLAYER 1 + PLAYER 2
                # =====================================

                total_amount = (
                    match_amount * 2
                )


                # =====================================
                # 15% COMMISSION
                # =====================================

                commission_amount = (
                    total_amount * 15 / 100
                )


                # =====================================
                # WINNER NET GAIN
                #
                # Winner already owns their own
                # match amount.
                #
                # Therefore only the loser's amount
                # minus commission is added.
                # =====================================

                winner_gain = (
                    match_amount -
                    commission_amount
                )


                # =====================================
                # GET LOSER BALANCE
                # =====================================

                loser = connection.execute(
                    text("""
                        SELECT
                            money
                        FROM lpusers
                        WHERE userid = :userid
                        FOR UPDATE
                    """),
                    {
                        "userid":
                            loser_uuid
                    }
                ).fetchone()


                if not loser:

                    print(
                        f"[TIMEOUT ERROR] "
                        f"Loser account not found: "
                        f"{loser_uuid}"
                    )

                    continue


                # =====================================
                # CHECK LOSER BALANCE
                # =====================================

                if loser.money < match_amount:

                    print(
                        f"[TIMEOUT ERROR] "
                        f"Insufficient balance for "
                        f"loser {loser_uuid}"
                    )

                    continue


                # =====================================
                # DEDUCT LOSER
                # =====================================

                connection.execute(
                    text("""
                        UPDATE lpusers
                        SET
                            money = money - :amount
                        WHERE userid = :userid
                    """),
                    {
                        "amount":
                            match_amount,

                        "userid":
                            loser_uuid
                    }
                )


                # =====================================
                # CREDIT WINNER
                # =====================================

                connection.execute(
                    text("""
                        UPDATE lpusers
                        SET
                            money = money + :winner_gain
                        WHERE userid = :userid
                    """),
                    {
                        "winner_gain":
                            winner_gain,

                        "userid":
                            winner_uuid
                    }
                )


                # =====================================
                # RECORD ADMIN COMMISSION
                # =====================================

                connection.execute(
                    text("""
                        INSERT INTO adminscommision
                        (
                            batchnumber,
                            totalamount,
                            commisionamount,
                            timestamp
                        )
                        VALUES
                        (
                            :batchnumber,
                            :totalamount,
                            :commissionamount,
                            NOW()
                        )
                    """),
                    {
                        "batchnumber":
                            match.matchbatchnumber,

                        "totalamount":
                            total_amount,

                        "commissionamount":
                            commission_amount
                    }
                )


                # =====================================
                # TERMINATE MATCH
                # =====================================

                connection.execute(
                    text("""
                        UPDATE usersmatches
                        SET
                            matchterminatedbytime = 1,
                            terminatedby = 1,
                            terminatedtime = NOW(),
                            winner = :winner
                        WHERE
                            matchbatchnumber =
                                :matchbatchnumber
                            AND
                            matchterminatedbytime = 0
                    """),
                    {
                        "winner":
                            winner_uuid,

                        "matchbatchnumber":
                            match.matchbatchnumber
                    }
                )


                # =====================================
                # LOG
                # =====================================

                print(
                    f"[TIMEOUT] "
                    f"Match {match.matchbatchnumber} "
                    f"terminated."
                )

                print(
                    f"[TIMEOUT] "
                    f"Loser: {loser_uuid}"
                )

                print(
                    f"[TIMEOUT] "
                    f"Winner: {winner_uuid}"
                )

                print(
                    f"[TIMEOUT] "
                    f"Loser deducted: ₹{match_amount}"
                )

                print(
                    f"[TIMEOUT] "
                    f"Winner credited: ₹{winner_gain}"
                )

                print(
                    f"[TIMEOUT] "
                    f"Commission: ₹{commission_amount}"
                )


    except Exception as e:

        print(
            "[TIMEOUT CHECKER ERROR]",
            e
        )

def match_timeout_worker():

    while True:

        check_match_timeouts()

        time.sleep(300)


initialize_database()


initialize_database()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000))
    )
