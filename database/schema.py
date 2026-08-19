from sqlalchemy import create_engine, text
from config import DB_CONFIG


def create_database():

    with engine.begin() as connection:

        connection.execute(
            text(
                "CREATE DATABASE IF NOT EXISTS lodoplayer"
            )
        )

        print("Database 'lodoplayer' is ready.")



def create_tables():

    database_url = (
        f"mysql+pymysql://{DB_CONFIG['user']}:"
        f"{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:"
        f"{DB_CONFIG['port']}/"
        f"{DB_CONFIG['database']}"
    )

    db_engine = create_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        future=True
    )

    with db_engine.begin() as connection:

        connection.execute(text("""

            CREATE TABLE IF NOT EXISTS lpusers (

                username VARCHAR(100) PRIMARY KEY,

                password VARCHAR(255) NOT NULL,

                phonenumber VARCHAR(20) NOT NULL,

                status VARCHAR(20) NOT NULL DEFAULT 'active',

                blocked BOOLEAN NOT NULL DEFAULT FALSE

            )

        """))

        print("Table 'lpusers' is ready.")

from sqlalchemy import text
from config import server_engine, db_engine


def create_database():

    with server_engine.begin() as connection:

        connection.execute(
            text("""
                CREATE DATABASE IF NOT EXISTS lodoplayer
            """)
        )

        print("Database 'lodoplayer' is ready.")


def create_tables():

    with db_engine.begin() as connection:

        connection.execute(text("""

            CREATE TABLE IF NOT EXISTS lpusers(
                
               userid CHAR(36) PRIMARY KEY,

               username VARCHAR(100) NOT NULL UNIQUE,

               password VARCHAR(255) NOT NULL,

               phonenumber VARCHAR(20) NOT NULL,
               money DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                 bankname VARCHAR(150) NULL,

        bankaccountnumber VARCHAR(50) NULL,

        ifsccode VARCHAR(20) NULL,

        upiid VARCHAR(150) NULL,
            
               status VARCHAR(20) NOT NULL DEFAULT 'active',

               blocked BOOLEAN NOT NULL DEFAULT FALSE

            )

        """))
        connection.execute(text("""

            CREATE TABLE IF NOT EXISTS accountdetails(

               id INT PRIMARY KEY AUTO_INCREMENT,

               bankaccountnumber VARCHAR(50) NOT NULL,

               name VARCHAR(150) NOT NULL,

               ifsccode VARCHAR(20) NOT NULL,

               upiid VARCHAR(150) NOT NULL,

               timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

           )

        """))
        connection.execute(text("""

    CREATE TABLE IF NOT EXISTS topup(

        topupid CHAR(36) PRIMARY KEY,

        userid CHAR(36) NOT NULL,

        phonenumber VARCHAR(20) NOT NULL,

        amount DECIMAL(12,2) NOT NULL,

        date DATE NOT NULL,

        utr VARCHAR(100) NOT NULL,

        status VARCHAR(20) NOT NULL DEFAULT 'Pending',

        approvedbyprimary BOOLEAN NOT NULL DEFAULT FALSE,

        approvedbysecondary BOOLEAN NOT NULL,

        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

    )

        """))
        connection.execute(text("""

    CREATE TABLE IF NOT EXISTS withdrawals(

        withdrawalid CHAR(36) PRIMARY KEY,

        userid CHAR(36) NOT NULL,

        amount DECIMAL(12,2) NOT NULL,

        utr VARCHAR(100) NULL,

        status VARCHAR(20) NOT NULL DEFAULT 'Pending',

        primaryapprovedby BOOLEAN NOT NULL DEFAULT FALSE,

        secondaryapprovedby BOOLEAN NOT NULL DEFAULT FALSE,

        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

    )

"""))
         
        connection.execute(text("""
    CREATE TABLE IF NOT EXISTS passwordupdatelimits(

        userid CHAR(36) PRIMARY KEY,

        updatecount INT NOT NULL DEFAULT 0,

        windowstart TIMESTAMP NULL,

        status BOOLEAN NOT NULL DEFAULT FALSE

    )

"""))
        connection.execute(text("""

    CREATE TABLE IF NOT EXISTS usersmatches(

        matchbatchnumber CHAR(8) PRIMARY KEY,

        initiateduseruuid CHAR(36) NOT NULL,

        amount DECIMAL(12,2) NOT NULL,

        matchstarttime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

        initiatedusercolor VARCHAR(20) NOT NULL,

        secondplayeruuid CHAR(36) NULL,

        secondplayeraccepttime TIMESTAMP NULL,

        secondplayercolor VARCHAR(20) NULL,

        timelength INT NOT NULL DEFAULT 60,

        matchterminatedbytime BOOLEAN NOT NULL DEFAULT FALSE,

        winner CHAR(36) NULL, 
        user1ready BOOLEAN NOT NULL DEFAULT FALSE,
        user2ready BOOLEAN NOT NULL DEFAULT FALSE,
        matchstarted BOOLEAN NOT NULL DEFAULT FALSE,
        terminatedby BOOLEAN NULL DEFAULT NULL,
        terminatedtime TIMESTAMP NULL,terminatedbyother BOOLEAN NOT NULL DEFAULT FALSE,player1lastmovetime TIMESTAMP NULL,
        player2lastmovetime TIMESTAMP NULL
    )

"""))   
  
        connection.execute(text("""
             CREATE TABLE IF NOT EXISTS adminscommision (

    batchnumber CHAR(8) PRIMARY KEY,

    totalamount DECIMAL(12,2) NOT NULL,

    commisionamount DECIMAL(12,2) NOT NULL,

    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

)
             

        """))   
         
        connection.execute(text("""

    CREATE TABLE IF NOT EXISTS ludogamestate(

        id BIGINT AUTO_INCREMENT PRIMARY KEY,

        matchbatchnumber CHAR(8) NOT NULL UNIQUE,

        currentturnuuid CHAR(36) NOT NULL,

        lastdice INT NULL,

        consecutivesix INT NOT NULL DEFAULT 0,

        mustmove BOOLEAN NOT NULL DEFAULT FALSE,

        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP

    )

        """))    
             

        connection.execute(text("""

    CREATE TABLE IF NOT EXISTS ludocoins(

        id BIGINT AUTO_INCREMENT PRIMARY KEY,

        matchbatchnumber CHAR(8) NOT NULL,

        playeruuid CHAR(36) NOT NULL,

        coinindex INT NOT NULL,

        position INT NOT NULL DEFAULT -1,

        stepsmoved INT NOT NULL DEFAULT 0,

        finished BOOLEAN NOT NULL DEFAULT FALSE,

        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,

        UNIQUE (
            matchbatchnumber,
            playeruuid,
            coinindex
        )

    )

        """))        

        connection.execute(text("""

    CREATE TABLE IF NOT EXISTS employee(

        employeeid CHAR(36) PRIMARY KEY,

        employeeusername VARCHAR(100) NOT NULL UNIQUE,

        password VARCHAR(255) NOT NULL,

        madeby VARCHAR(100) NOT NULL,

        timestamp TIMESTAMP NOT NULL
            DEFAULT CURRENT_TIMESTAMP

    )

        """))   
          
        

        

def initialize_database():

    create_database()   
    create_tables()