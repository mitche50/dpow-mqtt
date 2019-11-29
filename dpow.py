from datetime import datetime
from flask import Flask, render_template
from logging.handlers import TimedRotatingFileHandler

import configparser
import json
import logging
import os
import redis
import requests

import modules.db as db

config = configparser.ConfigParser()
config.read('config.ini')

logger = logging.getLogger("dpow_log")
logger.setLevel(logging.INFO)

handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-flask.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
logger.addHandler(handler)

app = Flask(__name__)

REDIS_HOST = config.get('redis', 'host')
REDIS_PORT = config.get('redis', 'port')
REDIS_PW = config.get('redis', 'pw')

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PW) 

pow_count_call = "SELECT count(hash) FROM requests WHERE response_ts >= NOW() - INTERVAL 24 HOUR;"
pow_ratio_call = ("SELECT work_type, count(work_type) FROM requests"
                  " WHERE response_ts >= NOW() - INTERVAL 24 HOUR"
                  " GROUP BY work_type order by work_type ASC;")
service_count_call = ("SELECT((SELECT count(service_name) FROM services WHERE service_name != 'private') + "
                      "(SELECT private_count FROM services WHERE service_name = 'private'));")
unlisted_service_call = "SELECT private_count FROM services WHERE service_name = 'private';"
client_count_call = "SELECT count(client_id) FROM clients WHERE last_action >= NOW() - INTERVAL 24 HOUR;"
services_24hr_call = ("SELECT ((SELECT service_count FROM service_log WHERE date_desc = 'today') "
                      "- (SELECT service_count FROM service_log WHERE date_desc = 'yesterday'))")
clients_24hr_call = ("SELECT ((SELECT client_count FROM client_log WHERE date_desc = 'today') "
                     "- (SELECT client_count FROM client_log WHERE date_desc = 'yesterday'))")
work_24hr_call = ("SELECT (SELECT count(hash) FROM requests WHERE response_ts >= NOW() - INTERVAL 1 DAY) "
                  "- (SELECT count(hash) FROM requests WHERE response_ts < NOW() - INTERVAL 1 DAY "
                  "   AND response_ts >= NOW() - INTERVAL 2 DAY)")
diff_24hr_call = ("SELECT round((SELECT avg(multiplier) FROM requests WHERE response_ts >= NOW() - INTERVAL 1 DAY) "
                  "- (SELECT avg(multiplier) FROM requests WHERE response_ts < NOW() - INTERVAL 1 DAY "
                  "   AND response_ts >= NOW() - INTERVAL 2 DAY),2)")
services_call = ("SELECT service_name, service_website, (service_ondemand + service_precache) as pow "
                 "FROM services "
                 "WHERE service_name != 'private' "
                 "ORDER BY pow DESC")
clients_call = ("SELECT client_id, IFNULL(ondemand, 0) as ondemand, IFNULL(precache, 0) as precache "
                "FROM dpow_mqtt.clients ORDER BY (ondemand + precache) DESC")
avg_difficulty_call = "SELECT round(avg(multiplier),2) FROM requests WHERE response_ts >= NOW() - INTERVAL 30 MINUTE"
avg_requests_call = ("SELECT date_format(response_ts, '%Y-%m-%d'), count(hash) FROM requests "
                     "WHERE response_ts >= NOW() - INTERVAL 1 MONTH "
                     "GROUP BY date_format(response_ts, '%Y-%m-%d')")
avg_requests_min_call = ("SELECT date_format(response_ts, '%Y-%m-%d %H:%i'), count(hash) FROM requests "
                         "WHERE response_ts >= NOW() - INTERVAL 60 minute "
                         "GROUP BY date_format(response_ts, '%Y-%m-%d %H:%i');")
avg_requests_hour_call = ("SELECT date_format(response_ts, '%Y-%m-%d %H'), count(hash) FROM requests "
                          "WHERE response_ts >= NOW() - INTERVAL 24 hour "
                          "GROUP BY date_format(response_ts, '%Y-%m-%d %H');")

avg_overall_call = ("SELECT avg(response_length) FROM requests "
                    "WHERE response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR")
live_chart_call = "SELECT response_length FROM requests ORDER BY response_ts DESC LIMIT 25;"


@app.route("/upcheck")
def upcheck():
    post_url = "https://dpow.nanocenter.org/upcheck"
    response = requests.get(post_url)
    if response.text != 'up':
        return 'Offline'
    return 'up'


@app.route("/")
@app.route("/index")
def index():
    # Get current POW count
    pow_count_data = db.get_db_data(pow_count_call)
    pow_count = int(pow_count_data[0][0])

    # Get POW type ratio
    on_demand_count = 0
    precache_count = 0
    pow_ratio_data = db.get_db_data(pow_ratio_call)

    for pow in pow_ratio_data:
        if pow[0] == 'ondemand':
            on_demand_count = pow[1]
        elif pow[0] == 'precache':
            precache_count = pow[1]
    if pow_count > 0:
        on_demand_ratio = round((on_demand_count / pow_count) * 100, 1)
        precache_ratio = round((precache_count / pow_count) * 100, 1)
    else:
        on_demand_ratio = 0
        precache_ratio = 0

    # Get service count
    service_count_data = db.get_db_data(service_count_call)
    service_count = int(service_count_data[0][0])

    # Get unlisted / listed services
    unlisted_service_data = db.get_db_data(unlisted_service_call)
    unlisted_services = int(unlisted_service_data[0][0])
    listed_services = service_count - unlisted_services

    # Get client count
    client_count_data = db.get_db_data(client_count_call)
    client_count = int(client_count_data[0][0])

    work_24hr_data = db.get_db_data(work_24hr_call)
    work_24hr = work_24hr_data[0][0]

    # Get info for Services section
    services_table = db.get_db_data(services_call)

    unlisted_services_call = "SELECT private_count FROM services where service_name = 'private'"
    unlisted_services_data = db.get_db_data(unlisted_services_call)
    unlisted_count = unlisted_services_data[0][0]

    unlisted_pow_call = "SELECT service_ondemand + service_precache FROM services WHERE service_name = 'private'"
    unlisted_pow_data = db.get_db_data(unlisted_pow_call)
    unlisted_pow = unlisted_pow_data[0][0]

    # Get info for Clients section
    clients_table = db.get_db_data(clients_call)

    # POW charts from redis
    redis_minute_data, redis_minute_precache, redis_minute_ondemand = [], [], []
    redis_hour_data, redis_hour_precache, redis_hour_ondemand = [], [], []
    redis_day_data, redis_day_precache, redis_day_ondemand = [], [], []
    redis_avg_data, redis_avg_precache, redis_avg_ondemand = [], [], []

    for i in range(0, r.llen("minute_data")):
        redis_minute_data.append(json.loads(r.lindex("minute_data", i).decode('utf-8')))
        redis_minute_ondemand.append(json.loads(r.lindex("minute_ondemand", i).decode('utf-8')))
        redis_minute_precache.append(json.loads(r.lindex("minute_precache", i).decode('utf-8')))
    
    for i in range(0, r.llen("day_data")):
        redis_day_data.append(json.loads(r.lindex("day_data", i).decode('utf-8')))
        redis_day_ondemand.append(json.loads(r.lindex("day_ondemand", i).decode('utf-8')))
        redis_day_precache.append(json.loads(r.lindex("day_precache", i).decode('utf-8')))
    
    for i in range(0, r.llen("hour_data")):
        redis_hour_data.append(json.loads(r.lindex("hour_data", i).decode('utf-8')))
        redis_hour_ondemand.append(json.loads(r.lindex("hour_ondemand", i).decode('utf-8')))
        redis_hour_precache.append(json.loads(r.lindex("hour_precache", i).decode('utf-8')))

    for i in range(0, r.llen("avg_data")):
        redis_avg_data.append(json.loads(r.lindex("avg_data", i).decode('utf-8')))
        redis_avg_ondemand.append(json.loads(r.lindex("avg_ondemand", i).decode('utf-8')))
        redis_avg_precache.append(json.loads(r.lindex("avg_precache", i).decode('utf-8')))

    avg_combined_time = db.get_avg()
    avg_overall_data = db.get_db_data(avg_overall_call)
    avg_requests_data = db.get_db_data(avg_requests_call)
    avg_requests_min = db.get_db_data(avg_requests_min_call)
    avg_requests_hour = db.get_db_data(avg_requests_hour_call)
    total_requests = 0
    count_requests = 0
    total_requests_min = 0
    count_requests_min = 0
    total_requests_hour = 0
    count_requests_hour = 0

    live_chart_data = db.get_db_data(live_chart_call)
    live_chart_prefill = []
    for row in live_chart_data:
        live_chart_prefill.append(float(row[0]))

    for row in avg_requests_data:
        total_requests += row[1]
        count_requests += 1
    for row in avg_requests_min:
        total_requests_min += row[1]
        count_requests_min += 1
    for row in avg_requests_hour:
        total_requests_hour += row[1]
        count_requests_hour += 1

    if count_requests > 0:
        requests_avg = int(total_requests / count_requests)
    else:
        requests_avg = 0
    if count_requests_hour > 0:
        requests_avg_hour = int(total_requests_hour / count_requests_hour)
    else:
        requests_avg_hour = 0
    if count_requests_min > 0:
        requests_avg_min = int(total_requests_min / count_requests_min)
    else:
        requests_avg_min = 0

    if avg_overall_data[0][0] is not None:
        avg_overall = round(float(avg_overall_data[0][0]), 1)
    else:
        avg_overall = 0

    avg_difficulty_data = db.get_db_data(avg_difficulty_call)
    if avg_difficulty_data[0][0] is not None:
        avg_difficulty = round(avg_difficulty_data[0][0], 1)
    else:
        avg_difficulty = 1.0

    return render_template('index.html', pow_count=pow_count, on_demand_ratio=on_demand_ratio,
                           precache_ratio=precache_ratio, service_count=service_count, client_count=client_count,
                           listed_services=listed_services, unlisted_services=unlisted_services, work_24hr=work_24hr,
                           services_table=services_table, unlisted_count=unlisted_count, unlisted_pow=unlisted_pow,
                           clients_table=clients_table, avg_overall=avg_overall, avg_combined_time=avg_combined_time,
                           avg_difficulty=avg_difficulty, requests_avg=requests_avg,
                           live_chart_prefill=live_chart_prefill, requests_avg_hour=requests_avg_hour,
                           requests_avg_min=requests_avg_min, 
                           minute_data=redis_minute_data, minute_precache=redis_minute_precache, minute_ondemand=redis_minute_ondemand,
                           hour_data=redis_hour_data, hour_precache=redis_hour_precache, hour_ondemand=redis_hour_ondemand,
                           day_data=redis_day_data, day_precache=redis_day_precache, day_ondemand=redis_day_ondemand,
                           avg_combined_data=redis_avg_data, avg_precache=redis_avg_precache, avg_ondemand=redis_avg_ondemand)


if __name__ == "__main__":
    app.run(host='0.0.0.0')
