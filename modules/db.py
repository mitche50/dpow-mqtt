import configparser
import logging
import MySQLdb
import os

from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/config.ini'.format(os.getcwd()))

# DB connection settings
DB_HOST = config.get('db', 'host')
DB_USER = config.get('db', 'user')
DB_PW = config.get('db', 'password')
DB_SCHEMA = config.get('db', 'schema')

logger = logging.getLogger("dpow_db_log")
logger.setLevel(logging.INFO)

handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
logger.addHandler(handler)


def db_init():
    if not check_db_exist():
        logger.info("db didn't exist: {}".format(DB_SCHEMA))
        create_db()
    logger.info("db did exist: {}".format(DB_SCHEMA))
    create_tables()
    create_triggers()


def check_db_exist():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, use_unicode=True,
                         charset="utf8mb4")
    logger.info("Checking if schema exists: {}".format(DB_SCHEMA))
    sql = "SHOW DATABASES LIKE '{}'".format(DB_SCHEMA)
    db_cursor = db.cursor()
    exists = db_cursor.execute(sql)
    db_cursor.close()
    db.close()

    return exists == 1


def create_db():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    sql = 'CREATE DATABASE IF NOT EXISTS {}'.format(DB_SCHEMA)
    db_cursor.execute(sql)
    db.commit()
    db_cursor.close()
    db.close()
    logger.info('Created database')


def check_table_exists(table_name):
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    sql = "SHOW TABLES LIKE '{}'".format(table_name)
    db_cursor.execute(sql)
    result = db_cursor.fetchall()
    return result


def create_tables():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    try:
        check_exists = check_table_exists('client_log')
        if not check_exists:
            sql = """
            CREATE TABLE `client_log` (
              `date_desc` varchar(45) NOT NULL,
              `client_count` int(5) DEFAULT NULL,
              PRIMARY KEY (`date_desc`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;            
            """

            db_cursor.execute(sql)
            logger.info("Checking if client_log table was created: {}".format(
                check_table_exists('client_log')))

        check_exists = check_table_exists('clients')
        if not check_exists:
            sql = """
            CREATE TABLE `clients` (
              `client_id` varchar(100) CHARACTER SET utf8 COLLATE utf8_unicode_ci NOT NULL,
              `precache` int(11) DEFAULT NULL,
              `ondemand` int(11) DEFAULT NULL,
              `last_action` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
              `registered_ts` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`client_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

            db_cursor.execute(sql)
            logger.info("Checking if clients table was created: {}".format(
                check_table_exists('clients')))

        check_exists = check_table_exists('requests')
        if not check_exists:
            sql = """
            CREATE TABLE `requests` (
              `hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
              `client` varchar(66) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `work_type` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `work_value` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `work_difficulty` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `multiplier` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
              `response_length` decimal(10,4) DEFAULT NULL,
              `response_ts` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`hash`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """

            db_cursor.execute(sql)
            logger.info("Checking if requests table was created: {}".format(
                check_table_exists('requests')))

        check_exists = check_table_exists('service_log')
        if not check_exists:
            sql = """
            CREATE TABLE `service_log` (
              `date_desc` varchar(45) NOT NULL,
              `service_count` int(5) DEFAULT NULL,
              PRIMARY KEY (`date_desc`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;     
            """

            db_cursor.execute(sql)
            logger.info("Checking if service_log table was created: {}".format(
                check_table_exists('service_log')))

        check_exists = check_table_exists('services')
        if not check_exists:
            sql = """
            CREATE TABLE `services` (
              `service_name` varchar(100) NOT NULL,
              `service_website` varchar(100) DEFAULT NULL,
              `service_ondemand` int(11) DEFAULT NULL,
              `service_precache` int(11) DEFAULT NULL,
              `private_count` int(11) DEFAULT NULL,
              `registered_ts` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`service_name`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """

            db_cursor.execute(sql)
            logger.info("Checking if services table was created: {}".format(
                check_table_exists('services')))

        db.commit()
        db_cursor.close()
        db.close()

    except Exception as e:
        logger.info("Error creating tables for DB: {}".format(e))


def create_triggers():
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    db_cursor.execute("DROP TRIGGER IF EXISTS requests_AFTER_INSERT;")
    requests_trigger = """
                       CREATE TRIGGER `dpow_mqtt`.`requests_AFTER_INSERT` AFTER INSERT ON `requests` FOR EACH ROW
                       BEGIN
                           UPDATE `clients` SET `last_action` = CURRENT_TIMESTAMP WHERE `client_id` = NEW.`client`;
                       END
                       """

    db_cursor.execute(requests_trigger)
    logger.info("Triggers set.")


def get_db_data(db_call):
    """
    Retrieve data from DB with no values
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    db_cursor.execute(db_call)
    db_data = db_cursor.fetchall()
    db_cursor.close()
    db.close()
    return db_data


def get_db_data_values(db_call, values):
    """
    Retrieve data from DB with values
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    db_cursor = db.cursor()
    db_cursor.execute(db_call, values)
    db_data = db_cursor.fetchall()
    db_cursor.close()
    db.close()
    return db_data


def set_db_data(db_call, values):
    """
    Enter data into DB
    """
    db = MySQLdb.connect(host=DB_HOST, port=3306, user=DB_USER, passwd=DB_PW, db=DB_SCHEMA, use_unicode=True,
                         charset="utf8mb4")
    try:
        db_cursor = db.cursor()
        db_cursor.execute(db_call, values)
        db.commit()
        db_cursor.close()
        db.close()
        return None
    except MySQLdb.ProgrammingError as e:
        logger.info("{}: Exception entering data into database".format(datetime.now()))
        logger.info("{}: {}".format(datetime.now(), e))
        return e


def set_services(services):
    """
    Drop service table and insert new one.
    """
    delete_services_call = "DELETE FROM services"
    set_db_data(delete_services_call, None)

    create_row_call = ("INSERT INTO services (service_name, service_website, service_ondemand, service_precache) "
                       "VALUES ")
    create_row_data = []

    try:
        for index, service in enumerate(services):
            if index == 0:
                create_row_call = create_row_call + "(%s, %s, %s, %s)"
            else:
                create_row_call += " , (%s, %s, %s, %s)"

            create_row_data.append(service['display'])
            create_row_data.append(service['website'])
            create_row_data.append(service['ondemand'])
            create_row_data.append(service['precache'])

        create_row_call += (" ON DUPLICATE KEY UPDATE service_ondemand = VALUES(service_ondemand), "
                            "service_precache = VALUES(service_precache)")
        set_db_data(create_row_call, create_row_data)

    except Exception as e:
        logger.info("{}: Exception inserting services into database".format(datetime.now()))
        logger.info("{}: {}".format(datetime.now(), e))
        raise e

    logger.info("Services entered into DB.")


def get_day_list():
    pow_day_total_call = ("SELECT t1.ts, t1.overall, t2.precache, t3.ondemand "
                            "FROM "
                            "(SELECT date_format(response_ts, '%Y-%m-%d') as ts, count(work_type) as overall "
                            " FROM requests "
                            " WHERE response_ts >= CURRENT_TIMESTAMP() - INTERVAL 1 MONTH GROUP BY ts) as t1 "
                            "left join "
                            "(SELECT date_format(response_ts, '%Y-%m-%d') as ts, count(work_type) as precache "
                            " FROM requests "
                            " WHERE work_type = 'precache' "
                            " AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 1 MONTH GROUP BY ts) as t2 "
                            " on t1.ts = t2.ts "
                            " left join "
                            " (SELECT date_format(response_ts, '%Y-%m-%d') as ts, count(work_type) as ondemand "
                            " FROM requests  "
                            " WHERE work_type = 'ondemand' "
                            " AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 1 MONTH GROUP BY ts) as t3 "
                            " on t1.ts = t3.ts ORDER BY ts ASC;")
    pow_day_data = get_db_data(pow_day_total_call)
    return pow_day_data


def get_hour_list():
    pow_hour_total_call = ("SELECT t1.ts, t1.overall, t2.precache, t3.ondemand "
                            "FROM "
                            "(SELECT date_format(response_ts, '%Y-%m-%d %H') as ts, count(work_type) as overall "
                            " FROM requests "
                            " WHERE response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR GROUP BY ts) as t1 "
                            "left join "
                            "(SELECT date_format(response_ts, '%Y-%m-%d %H') as ts, count(work_type) as precache "
                            " FROM requests "
                            " WHERE work_type = 'precache' "
                            " AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR GROUP BY ts) as t2 "
                            " on t1.ts = t2.ts "
                            " left join "
                            " (SELECT date_format(response_ts, '%Y-%m-%d %H') as ts, count(work_type) as ondemand "
                            " FROM requests  "
                            " WHERE work_type = 'ondemand' "
                            " AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR GROUP BY ts) as t3 "
                            " on t1.ts = t3.ts ORDER BY ts ASC;")
    hour_data = get_db_data(pow_hour_total_call)
    return hour_data

def get_minute_list():
    pow_minute_total_call = ("SELECT t1.ts, t1.overall, t2.precache, t3.ondemand "
                            "FROM "
                            "(SELECT date_format(response_ts, '%Y-%m-%d %H:%i') as ts, count(work_type) as overall "
                            "FROM requests "
                            "WHERE response_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTE GROUP BY ts) as t1 "
                            "left join "
                            "(SELECT date_format(response_ts, '%Y-%m-%d %H:%i') as ts, count(work_type) as precache "
                             "FROM requests "
                             "WHERE work_type = 'precache' "
                             "AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTE GROUP BY ts) as t2 "
                             "on t1.ts = t2.ts "
                             "left join "
                             "(SELECT date_format(response_ts, '%Y-%m-%d %H:%i') as ts, count(work_type) as ondemand "
                             "FROM requests "
                             "WHERE work_type = 'ondemand' "
                             "AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTE GROUP BY ts) as t3 "
                             "on t1.ts = t3.ts ORDER BY ts ASC;")
    minute_data = get_db_data(pow_minute_total_call)
    return minute_data
