from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

import os
import uuid
import time


from dotenv import load_dotenv

from sqlalchemy import text

from config import db_engine


load_dotenv()


# =========================================
# ADMIN BLUEPRINT
# =========================================

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# =========================================
# ADMIN CREDENTIALS
# =========================================

ADMIN_USERNAME = os.getenv(
    "ADMIN_USERNAME"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD"
)


# =========================================
# ADMIN LOGIN
# =========================================

@admin_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def admin_login():

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

            if (
                username ==
                ADMIN_USERNAME

                and

                password ==
                ADMIN_PASSWORD
            ):

                # Start a completely new session
                session.clear()

                session["admin_logged_in"] = True

                session["admin_username"] = (
                    ADMIN_USERNAME
                )

                # Start 20-minute inactivity timer
                session["admin_last_activity"] = time.time()

                return redirect(
                    url_for(
                        "admin.admin_dashboard"
                    )
                )

            flash(
                "Invalid admin credentials.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        return render_template(
            "admin_login.html"
        )

    except Exception:

        flash(
            "Unable to process admin login. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_login"
            )
        )

    finally:
        pass

# =========================================
# ADMIN AUTHENTICATION CHECK
# =========================================

def admin_required():

    try:

        return (
            session.get(
                "admin_logged_in"
            )
            is True
        )

    except Exception:

        return False

    finally:
        pass

# =========================================
# ADMIN DASHBOARD
# =========================================

@admin_bp.route(
    "/dashboard"
)
def admin_dashboard():

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

        # =====================================
        # GET TOTAL COMMISSION
        # =====================================

        with db_engine.begin() as connection:

            revenue_result = connection.execute(
                text("""
                    SELECT
                        COALESCE(
                            SUM(commisionamount),
                            0
                        ) AS totalrevenue

                    FROM adminscommision
                """)
            ).fetchone()

            # =====================================
            # GET CURRENT ACCOUNT DETAILS
            # =====================================

            account = connection.execute(
                text("""
                    SELECT
                        id,
                        bankaccountnumber,
                        name,
                        ifsccode,
                        upiid

                    FROM accountdetails

                    ORDER BY id DESC

                    LIMIT 1
                """)
            ).fetchone()

        total_revenue = float(
            revenue_result.totalrevenue
            or 0
        )

        return render_template(

            "admin_dashboard.html",

            total_revenue=
                total_revenue,

            account=
                account

        )

    except Exception:

        flash(
            "Unable to load the admin dashboard. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_login"
            )
        )

    finally:
        pass


# =========================================
# UPDATE ACCOUNT DETAILS
# =========================================

@admin_bp.route(
    "/update-account-details",
    methods=["POST"]
)
def update_account_details():

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

        bankaccountnumber = str(
            request.form.get(
                "bankaccountnumber",
                ""
            )
        ).strip()

        name = str(
            request.form.get(
                "name",
                ""
            )
        ).strip()

        ifsccode = str(
            request.form.get(
                "ifsccode",
                ""
            )
        ).strip()

        upiid = str(
            request.form.get(
                "upiid",
                ""
            )
        ).strip()

        # =====================================
        # ALL FIELDS REQUIRED
        # =====================================

        if not all(
            [
                bankaccountnumber,
                name,
                ifsccode,
                upiid
            ]
        ):

            flash(
                "All account details are required.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.admin_dashboard"
                )
            )

        # =====================================
        # REPLACE OLD DETAILS
        # =====================================

        with db_engine.begin() as connection:

            # Delete old record(s)

            connection.execute(
                text("""
                    DELETE FROM accountdetails
                """)
            )

            # Insert new record

            connection.execute(
                text("""
                    INSERT INTO accountdetails
                    (
                        bankaccountnumber,
                        name,
                        ifsccode,
                        upiid
                    )
                    VALUES
                    (
                        :bankaccountnumber,
                        :name,
                        :ifsccode,
                        :upiid
                    )
                """),
                {
                    "bankaccountnumber":
                        bankaccountnumber,

                    "name":
                        name,

                    "ifsccode":
                        ifsccode,

                    "upiid":
                        upiid
                }
            )

        flash(
            "Account details updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    except Exception:

        flash(
            "Unable to update account details. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    finally:
        pass



# =========================================
# WITHDRAWAL PAGE
# =========================================

@admin_bp.route(
    "/withdrawal"
)
def admin_withdrawal():

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

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
            #
            # ADMIN:
            # primary = 1
            # secondary = 0
            #
            # EMPLOYEE:
            # primary = 1
            # secondary = 1
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
                        timestamp,

                        CASE
                            WHEN
                                primaryapprovedby = 1
                                AND secondaryapprovedby = 1
                            THEN 'Employee'

                            WHEN
                                primaryapprovedby = 1
                                AND secondaryapprovedby = 0
                            THEN 'Admin'

                            ELSE '-'
                        END AS approvedby

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

            "admin_withdrawal.html",

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
                "admin.admin_dashboard"
            )
        )

    finally:
        pass


# =========================================
# PROCESS WITHDRAWAL
# =========================================

@admin_bp.route(
    "/withdrawal/process/<withdrawalid>",
    methods=["POST"]
)
def process_withdrawal(withdrawalid):

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

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
                    "admin.admin_withdrawal"
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

            if not withdrawal:

                flash(
                    "Withdrawal request not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin.admin_withdrawal"
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
                        "admin.admin_withdrawal"
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
                        "admin.admin_withdrawal"
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
                        "admin.admin_withdrawal"
                    )
                )

            # =====================================
            # DEDUCT MONEY
            # =====================================

            connection.execute(
                text("""
                    UPDATE lpusers
                    SET
                        money = money - :amount
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
            # APPROVE WITHDRAWAL
            #
            # ADMIN = PRIMARY
            # =====================================

            connection.execute(
                text("""
                    UPDATE withdrawals
                    SET
                        utr = :utr,
                        status = 'Approved',
                        primaryapprovedby = 1,
                        secondaryapprovedby = 0
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
                "admin.admin_withdrawal"
            )
        )

    except Exception:

        flash(
            "Unable to process the withdrawal. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_withdrawal"
            )
        )

    finally:
        pass


# =========================================
# ADD BALANCE
# =========================================

@admin_bp.route(
    "/add-balance"
)
def admin_add_balance():

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

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
            # TOTAL PENDING COUNT
            # =====================================

            pending_count_result = connection.execute(
                text("""
                    SELECT
                        COUNT(*) AS total
                    FROM topup
                    WHERE status = 'Pending'
                """)
            ).fetchone()

            total_pending = int(
                pending_count_result.total
            )

            # =====================================
            # PENDING TOP-UP REQUESTS
            # =====================================

            pending_topups = connection.execute(
                text("""
                    SELECT
                        topupid,
                        userid,
                        phonenumber,
                        amount,
                        date,
                        utr
                    FROM topup
                    WHERE status = 'Pending'
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
            # TOTAL HISTORY COUNT
            # =====================================

            history_count_result = connection.execute(
                text("""
                    SELECT
                        COUNT(*) AS total
                    FROM topup
                    WHERE status != 'Pending'
                """)
            ).fetchone()

            total_history = int(
                history_count_result.total
            )

            # =====================================
            # TOP-UP HISTORY
            #
            # ADMIN:
            # primary = 1
            # secondary = 0
            #
            # EMPLOYEE:
            # primary = 1
            # secondary = 1
            # =====================================

            history = connection.execute(
                text("""
                    SELECT
                        topupid,
                        phonenumber,
                        amount,
                        date,
                        utr,
                        status,
                        approvedbyprimary,
                        approvedbysecondary,

                        CASE
                            WHEN
                                approvedbyprimary = 1
                                AND approvedbysecondary = 1
                            THEN 'Employee'

                            WHEN
                                approvedbyprimary = 1
                                AND approvedbysecondary = 0
                            THEN 'Admin'

                            ELSE '-'
                        END AS approvedby

                    FROM topup

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
        # CALCULATE PAGES
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

            "admin_add_balance.html",

            pending_topups=
                pending_topups,

            history=
                history,

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
            "Unable to load top-up details. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    finally:
        pass



# =========================================
# APPROVE TOP-UP
# =========================================

@admin_bp.route(
    "/add-balance/approve/<topupid>",
    methods=["POST"]
)
def approve_topup(topupid):

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

        with db_engine.begin() as connection:

            # =====================================
            # LOCK THE TOP-UP RECORD
            # =====================================

            topup = connection.execute(
                text("""
                    SELECT
                        topupid,
                        userid,
                        amount,
                        status
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

            if not topup:

                flash(
                    "Top-up request not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin.admin_add_balance"
                    )
                )

            # =====================================
            # ONLY PENDING CAN BE APPROVED
            # =====================================

            if topup.status != "Pending":

                flash(
                    "This top-up has already been processed.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin.admin_add_balance"
                    )
                )

            amount = float(
                topup.amount
            )

            # =====================================
            # ADD MONEY TO USER
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
                        amount,

                    "userid":
                        topup.userid
                }
            )

            # =====================================
            # MARK TOP-UP APPROVED
            #
            # ADMIN = PRIMARY
            # =====================================

            connection.execute(
                text("""
                    UPDATE topup
                    SET
                        status = 'Approved',
                        approvedbyprimary = 1,
                        approvedbysecondary = 0
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
                "admin.admin_add_balance"
            )
        )

    except Exception:

        flash(
            "Unable to approve the top-up. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_add_balance"
            )
        )

    finally:
        pass



# =========================================
# REJECT TOP-UP
# =========================================

@admin_bp.route(
    "/add-balance/reject/<topupid>",
    methods=["POST"]
)
def reject_topup(topupid):

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

        with db_engine.begin() as connection:

            # =====================================
            # LOCK TOP-UP
            # =====================================

            topup = connection.execute(
                text("""
                    SELECT
                        topupid,
                        status
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

            if not topup:

                flash(
                    "Top-up request not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin.admin_add_balance"
                    )
                )

            # =====================================
            # ONLY PENDING CAN BE REJECTED
            # =====================================

            if topup.status != "Pending":

                flash(
                    "This top-up has already been processed.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin.admin_add_balance"
                    )
                )

            # =====================================
            # REJECT
            #
            # NO MONEY IS ADDED
            # =====================================

            connection.execute(
                text("""
                    UPDATE topup
                    SET
                        status = 'Rejected',
                        approvedbyprimary = 1,
                        approvedbysecondary = 0
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
                "admin.admin_add_balance"
            )
        )

    except Exception:

        flash(
            "Unable to reject the top-up. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_add_balance"
            )
        )

    finally:
        pass



# =========================================
# ADD EMPLOYEE PAGE
# =========================================

@admin_bp.route(
    "/add-employee",
    methods=["GET", "POST"]
)
def admin_add_employee():

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

        # =====================================
        # ADD EMPLOYEE
        # =====================================

        if request.method == "POST":

            employee_username = str(
                request.form.get(
                    "employeeusername",
                    ""
                )
            ).strip()

            password = str(
                request.form.get(
                    "password",
                    ""
                )
            ).strip()

            # =================================
            # REQUIRED FIELDS
            # =================================

            if not employee_username or not password:

                flash(
                    "Employee username and password are required.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin.admin_add_employee"
                    )
                )

            # =================================
            # CREATE EMPLOYEE UUID
            # =================================

            employeeid = str(
                uuid.uuid4()
            )

            # =================================
            # ADMIN WHO CREATED EMPLOYEE
            # =================================

            madeby = session.get(
                "admin_username"
            )

            with db_engine.begin() as connection:

                # =============================
                # CHECK DUPLICATE USERNAME
                # =============================

                existing_employee = connection.execute(
                    text("""
                        SELECT
                            employeeid
                        FROM employee
                        WHERE employeeusername =
                            :employeeusername
                        LIMIT 1
                    """),
                    {
                        "employeeusername":
                            employee_username
                    }
                ).fetchone()

                if existing_employee:

                    flash(
                        "Employee username already exists.",
                        "error"
                    )

                    return redirect(
                        url_for(
                            "admin.admin_add_employee"
                        )
                    )

                # =============================
                # INSERT EMPLOYEE
                # =============================

                connection.execute(
                    text("""
                        INSERT INTO employee
                        (
                            employeeid,
                            employeeusername,
                            password,
                            madeby
                        )
                        VALUES
                        (
                            :employeeid,
                            :employeeusername,
                            :password,
                            :madeby
                        )
                    """),
                    {
                        "employeeid":
                            employeeid,

                        "employeeusername":
                            employee_username,

                        "password":
                            password,

                        "madeby":
                            madeby
                    }
                )

            flash(
                "Employee added successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "admin.admin_add_employee"
                )
            )

        # =====================================
        # LOAD ALL EMPLOYEES
        # =====================================

        with db_engine.begin() as connection:

            employees = connection.execute(
                text("""
                    SELECT
                        employeeid,
                        employeeusername,
                        madeby,
                        timestamp
                    FROM employee
                    ORDER BY timestamp DESC
                """)
            ).fetchall()

        return render_template(
            "admin_add_employee.html",
            employees=employees
        )

    except Exception:

        flash(
            "Unable to process employee management. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_dashboard"
            )
        )

    finally:
        pass



# =========================================
# DELETE EMPLOYEE
# =========================================

@admin_bp.route(
    "/add-employee/delete/<employeeid>",
    methods=["POST"]
)
def delete_employee(employeeid):

    try:

        if not admin_required():

            return redirect(
                url_for(
                    "admin.admin_login"
                )
            )

        # Genuine admin activity
        session["admin_last_activity"] = time.time()

        with db_engine.begin() as connection:

            employee = connection.execute(
                text("""
                    SELECT
                        employeeid
                    FROM employee
                    WHERE employeeid =
                        :employeeid
                    LIMIT 1
                """),
                {
                    "employeeid":
                        employeeid
                }
            ).fetchone()

            if not employee:

                flash(
                    "Employee not found.",
                    "error"
                )

                return redirect(
                    url_for(
                        "admin.admin_add_employee"
                    )
                )

            connection.execute(
                text("""
                    DELETE FROM employee
                    WHERE employeeid =
                        :employeeid
                """),
                {
                    "employeeid":
                        employeeid
                }
            )

        flash(
            "Employee deleted successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.admin_add_employee"
            )
        )

    except Exception:

        flash(
            "Unable to delete the employee. Please try again.",
            "error"
        )

        return redirect(
            url_for(
                "admin.admin_add_employee"
            )
        )

    finally:
        pass


# =========================================
# ADMIN LOGOUT
# =========================================

@admin_bp.route(
    "/logout"
)
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )


    session.pop(
        "admin_username",
        None
    )


    return redirect(
        url_for(
            "admin.admin_login"
        )
    )