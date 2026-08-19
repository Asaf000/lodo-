import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

import time

from sqlalchemy import text

from config import db_engine


# =========================================
# EMPLOYEE BLUEPRINT
# =========================================

employee_bp = Blueprint(
    "employee",
    __name__,
    url_prefix="/employee"
)


# =========================================
# EMPLOYEE LOGIN
# =========================================

@employee_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def employee_login():

    try:

        if request.method == "POST":

            username = str(
                request.form.get(
                    "username",
                    ""
                )
            ).strip()

            password = str(
                request.form.get(
                    "password",
                    ""
                )
            ).strip()

            # =====================================
            # VALIDATE CREDENTIALS
            # =====================================

            with db_engine.begin() as connection:

                employee = connection.execute(
                    text("""
                        SELECT
                            employeeid,
                            employeeusername
                        FROM employee
                        WHERE employeeusername =
                            :username
                        AND password =
                            :password
                        LIMIT 1
                    """),
                    {
                        "username":
                            username,

                        "password":
                            password
                    }
                ).fetchone()

            if employee:

                # Start a completely new session
                session.clear()

                session["employee_logged_in"] = True

                session["employeeid"] = (
                    employee.employeeid
                )

                session["employee_username"] = (
                    employee.employeeusername
                )

                # Start 20-minute inactivity timer
                session["employee_last_activity"] = (
                    time.time()
                )

                return redirect(
                    url_for(
                        "employee.employee_dashboard"
                    )
                )

            flash(
                "Invalid employee credentials.",
                "error"
            )

            return redirect(
                url_for(
                    "employee.employee_login"
                )
            )

        return render_template(
            "employee_login.html"
        )

    except Exception:

        flash(
            "Unable to process employee login. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "employee.employee_login"
            )
        )

    finally:
        pass



# =========================================
# EMPLOYEE AUTHENTICATION CHECK
# =========================================

def employee_required():

    try:

        return (
            session.get(
                "employee_logged_in"
            )
            is True
        )

    except Exception:

        return False

    finally:
        pass

# =========================================
# EMPLOYEE DASHBOARD
# =========================================

@employee_bp.route(
    "/dashboard"
)
def employee_dashboard():

    try:

        if not employee_required():

            return redirect(
                url_for(
                    "employee.employee_login"
                )
            )

        # Genuine employee activity
        session["employee_last_activity"] = time.time()

        return render_template(
            "employee_dashboard.html"
        )

    except Exception:

        return redirect(
            url_for(
                "employee.employee_login"
            )
        )

    finally:
        pass



# =========================================
# EMPLOYEE BALANCE
# =========================================

@employee_bp.route(
    "/balance"
)
def employee_balance():

    try:

        if not employee_required():

            return redirect(
                url_for(
                    "employee.employee_login"
                )
            )

        # Genuine employee activity
        session["employee_last_activity"] = time.time()

        # =====================================
        # PENDING PAGE
        # =====================================

        pending_page = request.args.get(
            "pending_page",
            1,
            type=int
        )

        if pending_page < 1:

            pending_page = 1

        # =====================================
        # HISTORY PAGE
        # =====================================

        history_page = request.args.get(
            "history_page",
            1,
            type=int
        )

        if history_page < 1:

            history_page = 1

        per_page = 50

        pending_offset = (
            pending_page - 1
        ) * per_page

        history_offset = (
            history_page - 1
        ) * per_page

        with db_engine.begin() as connection:

            # =====================================
            # EMPLOYEE ACTION REQUESTS
            #
            # ONLY COMPLETELY PENDING TOPUPS
            #
            # primary = 0
            # secondary = 0
            # status = Pending
            #
            # IMPORTANT:
            # Admin-approved topups are NOT shown.
            # =====================================

            pending_count = connection.execute(
                text("""
                    SELECT
                        COUNT(*) AS total
                    FROM topup
                    WHERE
                        status = 'Pending'
                        AND approvedbyprimary = 0
                        AND approvedbysecondary = 0
                """)
            ).fetchone()

            total_pending = int(
                pending_count.total
            )

            # =====================================
            # EMPLOYEE TOPUP REQUESTS
            # =====================================

            employee_topups = connection.execute(
                text("""
                    SELECT
                        topupid,
                        userid,
                        phonenumber,
                        amount,
                        date,
                        utr,
                        status,
                        approvedbyprimary,
                        approvedbysecondary
                    FROM topup
                    WHERE
                        status = 'Pending'
                        AND approvedbyprimary = 0
                        AND approvedbysecondary = 0
                    ORDER BY timestamp ASC
                    LIMIT :limit
                    OFFSET :offset
                """),
                {
                    "limit":
                        per_page,

                    "offset":
                        pending_offset
                }
            ).fetchall()

            # =====================================
            # HISTORY COUNT
            #
            # Employee-completed transactions:
            # secondary = 1
            # =====================================

            history_count = connection.execute(
                text("""
                    SELECT
                        COUNT(*) AS total
                    FROM topup
                    WHERE approvedbysecondary = 1
                """)
            ).fetchone()

            total_history = int(
                history_count.total
            )

            # =====================================
            # TOPUP HISTORY
            # =====================================

            topup_history = connection.execute(
                text("""
                    SELECT
                        topupid,
                        phonenumber,
                        amount,
                        date,
                        utr,
                        status,
                        approvedbyprimary,
                        approvedbysecondary
                    FROM topup
                    WHERE approvedbysecondary = 1
                    ORDER BY timestamp DESC
                    LIMIT :limit
                    OFFSET :offset
                """),
                {
                    "limit":
                        per_page,

                    "offset":
                        history_offset
                }
            ).fetchall()

        # =====================================
        # PAGE COUNTS
        # =====================================

        total_pending_pages = (
            (
                total_pending +
                per_page -
                1
            )
            // per_page
        )

        total_history_pages = (
            (
                total_history +
                per_page -
                1
            )
            // per_page
        )

        return render_template(

            "employee_balance.html",

            employee_topups=
                employee_topups,

            topup_history=
                topup_history,

            pending_page=
                pending_page,

            total_pending_pages=
                total_pending_pages,

            history_page=
                history_page,

            total_history_pages=
                total_history_pages

        )

    except Exception:

        flash(
            "Unable to load balance details. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "employee.employee_dashboard"
            )
        )

    finally:
        pass



# =========================================
# EMPLOYEE APPROVE TOP-UP
# =========================================

@employee_bp.route(
    "/balance/approve/<topupid>",
    methods=["POST"]
)
def employee_approve_topup(
    topupid
):

    try:

        if not employee_required():

            return redirect(
                url_for(
                    "employee.employee_login"
                )
            )

        # Genuine employee activity
        session["employee_last_activity"] = time.time()

        with db_engine.begin() as connection:

            # =====================================
            # LOCK TOP-UP
            # =====================================

            topup = connection.execute(
                text("""
                    SELECT
                        topupid,
                        userid,
                        amount,
                        status,
                        approvedbyprimary,
                        approvedbysecondary
                    FROM topup
                    WHERE topupid =
                        :topupid
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "topupid":
                        topupid
                }
            ).fetchone()

            # =====================================
            # NOT FOUND
            # =====================================

            if not topup:

                flash(
                    "Top-up request not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_balance"
                    )
                )

            # =====================================
            # ALREADY PROCESSED
            # =====================================

            if topup.approvedbysecondary == 1:

                flash(
                    "This top-up has already been processed.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_balance"
                    )
                )

            # =====================================
            # ONLY COMPLETELY PENDING
            #
            # Employee must NOT process:
            #
            # status = Approved
            # primary = 1
            # =====================================

            if (
                topup.status != "Pending"
                or
                topup.approvedbyprimary != 0
                or
                topup.approvedbysecondary != 0
            ):

                flash(
                    "This top-up is not available for employee processing.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_balance"
                    )
                )

            # =====================================
            # FIND USER
            # =====================================

            user = connection.execute(
                text("""
                    SELECT
                        userid
                    FROM lpusers
                    WHERE userid =
                        :userid
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "userid":
                        topup.userid
                }
            ).fetchone()

            if not user:

                flash(
                    "User associated with this top-up was not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_balance"
                    )
                )

            # =====================================
            # ADD MONEY
            # =====================================

            connection.execute(
                text("""
                    UPDATE lpusers
                    SET
                        money =
                            money + :amount
                    WHERE userid =
                        :userid
                """),
                {
                    "amount":
                        topup.amount,

                    "userid":
                        topup.userid
                }
            )

            # =====================================
            # EMPLOYEE COMPLETES APPROVAL
            #
            # PRIMARY = 1
            # SECONDARY = 1
            # =====================================

            connection.execute(
                text("""
                    UPDATE topup
                    SET
                        status = 'Approved',
                        approvedbyprimary = 1,
                        approvedbysecondary = 1
                    WHERE topupid =
                        :topupid
                """),
                {
                    "topupid":
                        topupid
                }
            )

        flash(
            "Top-up approved successfully.",
            "success"
        )

        return redirect(
            url_for(
                "employee.employee_balance"
            )
        )

    except Exception:

        flash(
            "Unable to approve the top-up. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "employee.employee_balance"
            )
        )

    finally:
        pass



# =========================================
# EMPLOYEE REJECT TOP-UP
# =========================================

@employee_bp.route(
    "/balance/reject/<topupid>",
    methods=["POST"]
)
def employee_reject_topup(
    topupid
):

    try:

        if not employee_required():

            return redirect(
                url_for(
                    "employee.employee_login"
                )
            )

        # Genuine employee activity
        session["employee_last_activity"] = time.time()

        with db_engine.begin() as connection:

            # =====================================
            # LOCK TOP-UP
            # =====================================

            topup = connection.execute(
                text("""
                    SELECT
                        topupid,
                        status,
                        approvedbyprimary,
                        approvedbysecondary
                    FROM topup
                    WHERE topupid =
                        :topupid
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "topupid":
                        topupid
                }
            ).fetchone()

            # =====================================
            # NOT FOUND
            # =====================================

            if not topup:

                flash(
                    "Top-up request not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_balance"
                    )
                )

            # =====================================
            # ALREADY PROCESSED
            # =====================================

            if topup.approvedbysecondary == 1:

                flash(
                    "This top-up has already been processed.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_balance"
                    )
                )

            # =====================================
            # ONLY COMPLETELY PENDING
            # =====================================

            if (
                topup.status != "Pending"
                or
                topup.approvedbyprimary != 0
                or
                topup.approvedbysecondary != 0
            ):

                flash(
                    "This top-up is not available for employee processing.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_balance"
                    )
                )

            # =====================================
            # REJECT
            #
            # NO MONEY IS ADDED
            #
            # PRIMARY = 1
            # SECONDARY = 1
            # =====================================

            connection.execute(
                text("""
                    UPDATE topup
                    SET
                        status = 'Rejected',
                        approvedbyprimary = 1,
                        approvedbysecondary = 1
                    WHERE topupid =
                        :topupid
                """),
                {
                    "topupid":
                        topupid
                }
            )

        flash(
            "Top-up rejected.",
            "success"
        )

        return redirect(
            url_for(
                "employee.employee_balance"
            )
        )

    except Exception:

        flash(
            "Unable to reject the top-up. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "employee.employee_balance"
            )
        )

    finally:
        pass



# =========================================
# EMPLOYEE WITHDRAWAL
# =========================================
@employee_bp.route(
    "/withdrawal"
)
def employee_withdrawal():

    try:

        if not employee_required():

            return redirect(
                url_for(
                    "employee.employee_login"
                )
            )

        # Genuine employee activity
        session["employee_last_activity"] = time.time()

        # =====================================
        # PENDING PAGE
        # =====================================

        pending_page = request.args.get(
            "pending_page",
            1,
            type=int
        )

        if pending_page < 1:

            pending_page = 1

        # =====================================
        # HISTORY PAGE
        # =====================================

        history_page = request.args.get(
            "history_page",
            1,
            type=int
        )

        if history_page < 1:

            history_page = 1

        per_page = 50

        pending_offset = (
            pending_page - 1
        ) * per_page

        history_offset = (
            history_page - 1
        ) * per_page

        with db_engine.begin() as connection:

            # =====================================
            # TOTAL PENDING WITHDRAWALS
            # =====================================

            pending_count = connection.execute(
                text("""
                    SELECT
                        COUNT(*) AS total
                    FROM withdrawals
                    WHERE status = 'Pending'
                """)
            ).fetchone()

            total_pending = int(
                pending_count.total
            )

            # =====================================
            # PENDING WITHDRAWALS
            #
            # ONLY PENDING REQUESTS
            # =====================================

            pending_withdrawals = connection.execute(
                text("""
                    SELECT
                      w.withdrawalid,
                      w.userid,
                      w.amount,
                      w.timestamp,

                      u.bankname,
                      u.bankaccountnumber,
                      u.ifsccode,
                      u.upiid

                    FROM withdrawals w

                    LEFT JOIN lpusers u
                      ON u.userid = w.userid

                    WHERE w.status = 'Pending'

                    ORDER BY w.timestamp ASC

                    LIMIT :limit

                    OFFSET :offset

                """),
                {
                    "limit":
                        per_page,

                    "offset":
                        pending_offset
                }
            ).fetchall()

            # =====================================
            # TOTAL HISTORY
            # =====================================

            history_count = connection.execute(
                text("""
                    SELECT
                        COUNT(*) AS total
                    FROM withdrawals
                    WHERE status != 'Pending'
                """)
            ).fetchone()

            total_history = int(
                history_count.total
            )

            # =====================================
            # WITHDRAWAL HISTORY
            # =====================================

            withdrawal_history = connection.execute(
                text("""
                    SELECT
                        withdrawalid,
                        amount,
                        utr,
                        status,
                        primaryapprovedby,
                        secondaryapprovedby,
                        timestamp
                    FROM withdrawals
                    WHERE status != 'Pending'
                    ORDER BY timestamp DESC
                    LIMIT :limit
                    OFFSET :offset
                """),
                {
                    "limit":
                        per_page,

                    "offset":
                        history_offset
                }
            ).fetchall()

        # =====================================
        # TOTAL PAGES
        # =====================================

        total_pending_pages = (
            (
                total_pending +
                per_page -
                1
            )
            // per_page
        )

        total_history_pages = (
            (
                total_history +
                per_page -
                1
            )
            // per_page
        )

        return render_template(

            "employee_withdrawal.html",

            pending_withdrawals=
                pending_withdrawals,

            withdrawal_history=
                withdrawal_history,

            pending_page=
                pending_page,

            total_pending_pages=
                total_pending_pages,

            history_page=
                history_page,

            total_history_pages=
                total_history_pages

        )

    except Exception:

        flash(
            "Unable to load withdrawal details. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "employee.employee_dashboard"
            )
        )

    finally:
        pass



# =========================================
# EMPLOYEE PROCESS WITHDRAWAL
# =========================================

@employee_bp.route(
    "/withdrawal/process/<withdrawalid>",
    methods=["POST"]
)
def employee_process_withdrawal(
    withdrawalid
):

    try:

        if not employee_required():

            return redirect(
                url_for(
                    "employee.employee_login"
                )
            )

        # Genuine employee activity
        session["employee_last_activity"] = time.time()

        utr = str(
            request.form.get(
                "utr",
                ""
            )
        ).strip()

        # =====================================
        # UTR REQUIRED
        # =====================================

        if not utr:

            flash(
                "UTR is required.",
                "error"
            )

            return redirect(
                url_for(
                    "employee.employee_withdrawal"
                )
            )

        with db_engine.begin() as connection:

            # =====================================
            # LOCK WITHDRAWAL
            # =====================================

            withdrawal = connection.execute(
                text("""
                    SELECT
                        withdrawalid,
                        userid,
                        amount,
                        status
                    FROM withdrawals
                    WHERE withdrawalid =
                        :withdrawalid
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "withdrawalid":
                        withdrawalid
                }
            ).fetchone()

            # =====================================
            # NOT FOUND
            # =====================================

            if not withdrawal:

                flash(
                    "Withdrawal request not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_withdrawal"
                    )
                )

            # =====================================
            # ONLY PENDING CAN BE PROCESSED
            # =====================================

            if withdrawal.status != "Pending":

                flash(
                    "This withdrawal has already been processed.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_withdrawal"
                    )
                )

            amount = float(
                withdrawal.amount
            )

            # =====================================
            # CHECK USER BALANCE
            # =====================================

            user = connection.execute(
                text("""
                    SELECT
                        money
                    FROM lpusers
                    WHERE userid =
                        :userid
                    LIMIT 1
                    FOR UPDATE
                """),
                {
                    "userid":
                        withdrawal.userid
                }
            ).fetchone()

            if not user:

                flash(
                    "User associated with this withdrawal was not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_withdrawal"
                    )
                )

            current_money = float(
                user.money
            )

            # =====================================
            # INSUFFICIENT BALANCE
            # =====================================

            if current_money < amount:

                flash(
                    "User does not have sufficient balance for this withdrawal.",
                    "error"
                )

                return redirect(
                    url_for(
                        "employee.employee_withdrawal"
                    )
                )

            # =====================================
            # DEDUCT MONEY
            # =====================================

            connection.execute(
                text("""
                    UPDATE lpusers
                    SET
                        money =
                            money - :amount
                    WHERE userid =
                        :userid
                """),
                {
                    "amount":
                        amount,

                    "userid":
                        withdrawal.userid
                }
            )

            # =====================================
            # EMPLOYEE APPROVES
            #
            # PRIMARY = 1
            # SECONDARY = 1
            # =====================================

            connection.execute(
                text("""
                    UPDATE withdrawals
                    SET
                        utr = :utr,
                        status = 'Approved',
                        primaryapprovedby = 1,
                        secondaryapprovedby = 1
                    WHERE withdrawalid =
                        :withdrawalid
                """),
                {
                    "utr":
                        utr,

                    "withdrawalid":
                        withdrawalid
                }
            )

        flash(
            "Withdrawal approved successfully.",
            "success"
        )

        return redirect(
            url_for(
                "employee.employee_withdrawal"
            )
        )

    except Exception:

        flash(
            "Unable to process the withdrawal. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "employee.employee_withdrawal"
            )
        )

    finally:
        pass



# =========================================
# EMPLOYEE LOGOUT
# =========================================

@employee_bp.route(
    "/logout"
)
def employee_logout():

    session.pop(
        "employee_logged_in",
        None
    )


    session.pop(
        "employeeid",
        None
    )


    session.pop(
        "employee_username",
        None
    )


    return redirect(
        url_for(
            "employee.employee_login"
        )
    )