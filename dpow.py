from datetime import datetime
from flask import Flask, render_template
from logging.handlers import TimedRotatingFileHandler

import json
import logging
import os
import requests

import modules.db as db

logger = logging.getLogger("dpow_log")
logger.setLevel(logging.INFO)

handler = TimedRotatingFileHandler('{}/logs/{:%Y-%m-%d}-flask.log'.format(os.getcwd(), datetime.now()),
                                   when="d",
                                   interval=1,
                                   backupCount=5)
logger.addHandler(handler)

app = Flask(__name__)

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
clients_call = ("SELECT t1.client, ( t1.total - IFNULL(t2.ondemand, 0) ), IFNULL(t2.ondemand, 0) FROM "
                "   (SELECT client, count(client) as total FROM "
                "   requests GROUP BY client) as t1"
                " left join "
                "   (SELECT client, count(client) as ondemand FROM "
                "   requests WHERE work_type = 'ondemand' GROUP BY client) as t2"
                " on t1.client = t2.client"
                " ORDER BY total DESC;")
avg_difficulty_call = "SELECT round(avg(multiplier),2) FROM requests WHERE response_ts >= NOW() - INTERVAL 30 MINUTE"
avg_requests_call = ("SELECT date_format(response_ts, '%Y-%m-%d'), count(hash) FROM requests "
                     "WHERE response_ts >= NOW() - INTERVAL 1 MONTH "
                     "GROUP BY date_format(response_ts, '%Y-%m-%d')")
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
pow_minute_total_call = ("SELECT t1.ts, t1.overall, t2.precache, t3.ondemand "
                         "FROM "
                         "(SELECT date_format(response_ts, '%Y-%m-%d %H:%i') as ts, count(work_type) as overall "
                         " FROM requests "
                         " WHERE response_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTE GROUP BY ts) as t1 "
                         "left join "
                         "(SELECT date_format(response_ts, '%Y-%m-%d %H:%i') as ts, count(work_type) as precache "
                         " FROM requests "
                         " WHERE work_type = 'precache' "
                         " AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTE GROUP BY ts) as t2 "
                         " on t1.ts = t2.ts "
                         " left join "
                         " (SELECT date_format(response_ts, '%Y-%m-%d %H:%i') as ts, count(work_type) as ondemand "
                         " FROM requests  "
                         " WHERE work_type = 'ondemand' "
                         " AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 60 MINUTE GROUP BY ts) as t3 "
                         " on t1.ts = t3.ts ORDER BY ts ASC;")
avg_combined_call = ("SELECT t1.ts, t1.overall, t2.precache, t3.ondemand "
                     "FROM "
                     "(SELECT date_format(response_ts, '%Y-%m-%d %H') as ts, avg(response_length) as overall "
                     "FROM requests "
                     "WHERE response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR GROUP BY ts) as t1 "
                     "left join "
                     "(SELECT date_format(response_ts, '%Y-%m-%d %H') as ts, avg(response_length) as precache "
                     "FROM requests "
                     "WHERE work_type = 'precache' "
                     "AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR GROUP BY ts) as t2 "
                     "on t1.ts = t2.ts "
                     "left join "
                     "(SELECT date_format(response_ts, '%Y-%m-%d %H') as ts, avg(response_length) as ondemand "
                     "FROM requests "
                     "WHERE work_type = 'ondemand' "
                     "AND response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR GROUP BY ts) as t3 "
                     "on t1.ts = t3.ts ORDER BY ts ASC;")
avg_overall_call = ("SELECT avg(response_length) FROM requests "
                    "WHERE response_ts >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR")


@app.route("/upcheck")
def upcheck():
    post_url = "https://dpow.nanocenter.org/upcheck"
    response = requests.get(post_url)
    if response.text != 'up':
        return 'Offline'
    return 'Online'


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

    # Get 24hr differences
    services_24hr_data = db.get_db_data(services_24hr_call)
    services_24hr = services_24hr_data[0][0]
    if services_24hr is None:
        services_24hr = 0

    clients_24hr_data = db.get_db_data(clients_24hr_call)
    clients_24hr = clients_24hr_data[0][0]
    if clients_24hr is None:
        clients_24hr = 0

    work_24hr_data = db.get_db_data(work_24hr_call)
    work_24hr = work_24hr_data[0][0]
    diff_24hr_data = db.get_db_data(diff_24hr_call)
    diff_24hr = diff_24hr_data[0][0]

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

    # Get info for POW charts
    day_total = db.get_db_data(pow_day_total_call)
    hour_total = db.get_db_data(pow_hour_total_call)
    minute_total = db.get_db_data(pow_minute_total_call)

    avg_combined_time = db.get_db_data(avg_combined_call)
    avg_overall_data = db.get_db_data(avg_overall_call)
    avg_requests_data = db.get_db_data(avg_requests_call)
    total_requests = 0
    count_requests = 0

    for row in avg_requests_data:
        total_requests += row[1]
        count_requests += 1

    requests_avg = int(total_requests / count_requests)

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
                           listed_services=listed_services, unlisted_services=unlisted_services,
                           services_24hr=services_24hr, clients_24hr=clients_24hr, work_24hr=work_24hr,
                           services_table=services_table, unlisted_count=unlisted_count, unlisted_pow=unlisted_pow,
                           clients_table=clients_table, day_total=day_total, hour_total=hour_total,
                           minute_total=minute_total, avg_overall=avg_overall, avg_combined_time=avg_combined_time,
                           avg_difficulty=avg_difficulty, requests_avg=requests_avg, diff_24hr=diff_24hr)


if __name__ == "__main__":
    app.run(host='0.0.0.0')
