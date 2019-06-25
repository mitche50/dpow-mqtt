#!/path/to/dpow-mqtt/venv/bin/python3

from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

import configparser
import json
import logging
import os
import paho.mqtt.client as mqtt
import redis
import requests

import modules.db as db

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/config.ini'.format(os.getcwd()))

logger = logging.getLogger("dpow_log")
logger.setLevel(logging.INFO)

handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-mqtt.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
logger.addHandler(handler)

NODE_IP = config.get('nano', 'node_ip')
POW_USER = config.get('pow', 'username')
POW_PW = config.get('pow', 'password')
MQTT_IP = config.get('pow', 'mqtt_ip')
MQTT_PORT = int(config.get('pow', 'mqtt_port'))
REDIS_HOST = config.get('redis', 'host')
REDIS_PORT = int(config.get('redis', 'port'))
REDIS_DB = int(config.get('redis', 'db'))


def get_work_mult(work_value, work_hash):
    """
    When a result message is received, retrieve the work multiplier
    """
    data = {
        "action": "work_validate",
        "work": work_value,
        "hash": work_hash
    }
    json_request = json.dumps(data)
    r = requests.post('{}'.format(NODE_IP), data=json_request)
    rx = r.json()

    return rx


def on_connect(client, userdata, flags, rc):
    """
    On connection to the MQTT server, automatically subscribe to merchant_order_requests topic
    """
    logger.info("{}: Connected to DPOW Server with result code {}".format(datetime.now(), str(rc)))
    client.subscribe('work/#')
    client.subscribe('result/#')
    client.subscribe('statistics')


def on_message(client, userdata, msg):
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
        topic = msg.topic
        topic = topic.split('/')
        if topic[0] == 'work':
            work_type = topic[1]
            message = msg.payload.decode().split(',')
            work_hash = message[0]
            work_difficulty = message[1]
            mapping = {'work_type': work_type, 'work_difficulty': work_difficulty, 'timestamp': str(datetime.now())}
            r.hmset(work_hash, mapping)

            logger.info("{}: work topic received: Work type = {}, hash: {}, difficulty: {}".format(datetime.now(),
                                                                                                   work_type,
                                                                                                   work_hash,
                                                                                                   work_difficulty))
        elif topic[0] == 'result':
            message = msg.payload.decode().split(',')
            work_hash = message[0]
            work_value = message[1]
            work_client = message[2]

            hmreturn = r.hmget(work_hash, ['work_type', 'timestamp', 'work_difficulty'])

            work_type = hmreturn[0].decode()
            request_time = datetime.strptime(hmreturn[1].decode(), '%Y-%m-%d %H:%M:%S.%f')
            work_difficulty = hmreturn[2].decode()

            if work_difficulty != 'ffffffc000000000':
                # Add work multiplier logic for V19
                # work_multiplier = get_work_mult(work_value, work_hash)
                work_multiplier = "1.2"
            else:
                # Add work multiplier logic for V19
                # work_multiplier = get_work_mult(work_value, work_hash)
                work_multiplier = "1"

            time_diff_micro = (datetime.now() - request_time).microseconds
            time_difference = round(time_diff_micro * (10 ** -6), 4)

            client_sql = "INSERT IGNORE INTO dpow_mqtt.clients SET client_id = %s"

            request_sql = ("INSERT IGNORE INTO requests "
                           "(hash, client, work_type, work_value, work_difficulty, multiplier, response_length) "
                           "VALUES (%s, %s, %s, %s, %s, %s, %s)")

            db.set_db_data(client_sql, [work_client, ])
            db.set_db_data(request_sql, [work_hash, work_client, work_type, work_value,
                                         work_difficulty, work_multiplier, time_difference])

        elif topic[0] == 'statistics':
            stats = json.loads(msg.payload.decode())
            logger.info("Stats call received: ", stats)
            try:
                db.set_services(stats['services']['public'])

                private_call = ("INSERT INTO services"
                                " (service_name, service_ondemand, service_precache, private_count)"
                                " VALUES ('private', %s, %s, %s)"
                                " ON DUPLICATE KEY UPDATE service_ondemand = VALUES(service_ondemand),"
                                " service_precache = VALUES(service_precache),"
                                " private_count = VALUES(private_count)")
                private_stats = stats['services']['private']
                db.set_db_data(private_call, [private_stats['ondemand'],
                                              private_stats['precache'],
                                              private_stats['count']])

            except Exception as e:
                logger.info("Error logger.infoing public services: {}".format(e))
                logger.info(stats)
        else:
            try:
                logger.info("UNEXPECTED MESSAGE")
                logger.info("TOPIC: {}".format(topic[0].upper()))
                logger.info("message: {}".format(msg.payload))
            except Exception as e:
                logger.info("exception: {}".format(e))

    except Exception as e:
        logger.info("Error: {}".format(e))


if __name__ == "__main__":
    db.db_init()

    c = mqtt.Client()

    c.on_connect = on_connect
    c.on_message = on_message

    c.username_pw_set(POW_USER, password=POW_PW)
    c.connect(MQTT_IP, MQTT_PORT)

    c.loop_forever()