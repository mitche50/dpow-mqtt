#!/home/dpow/dpow-mqtt/venv/bin/python3

import configparser
import os
import simplejson as json
import redis
import modules.db as db

from datetime import datetime

# Read config and parse constants
config = configparser.ConfigParser()
config.read('{}/config.ini'.format(os.getcwd()))

REDIS_HOST = config.get('redis', 'host')
REDIS_PORT = int(config.get('redis', 'port'))
REDIS_DB = int(config.get('redis', 'db'))
REDIS_PW = config.get('redis','pw')

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PW)

def init():
    # Initialize the last hours / minutes that were updated
    # We will reference these to prevent any unnecessary updates
    if r.get("last_day") is None:
        r.set("last_day", datetime.now().day)
    if r.get("last_hour") is None:
        r.set("last_hour", datetime.now().hour)
    if r.get("last_minute") is None:
        r.set("last_minute", datetime.now().minute)

    # Check to make sure that the lists have been populated
    if r.llen("minute_data") < 60:
        print("minute list too short, initializing")
        min_data = db.get_minute_list()
        populate_chart(min_data, "minute")
    if r.llen("day_data") < 30:
        print("day list too short, initializing")
        day_data = db.get_day_list()
        populate_chart(day_data, "day")
    if r.llen("hour_data") < 24:
        print("hour list too short, initializing")
        hour_data = db.get_hour_list()
        populate_chart(hour_data, "hour")
    if r.llen("avg_data") < 24:
        print("avg list too short, initializing")
        avg_data = db.get_avg()
        populate_chart(avg_data, "avg")

def populate_chart(data_dict, chart_name):
    print("populating {} data".format(chart_name))
    r.delete("{}_data".format(chart_name))
    r.delete("{}_precache".format(chart_name))
    r.delete("{}_ondemand".format(chart_name))
    for data in data_dict:
        r.lpush("{}_data".format(chart_name), json.dumps({"x": data[0], "y": data[1]}))
        if data[2] is not None:
            r.lpush("{}_precache".format(chart_name), json.dumps({"x": data[0], "y": data[2]}))
        else:
            r.lpush("{}_precache".format(chart_name), json.dumps({"x": data[0], "y": 0}))
        if data[3] is not None:
            r.lpush("{}_ondemand".format(chart_name), json.dumps({"x": data[0], "y": data[3]}))
        else:
            r.lpush("{}_ondemand".format(chart_name), json.dumps({"x": data[0], "y": 0}))
        

if __name__ == "__main__":
    init()

    hour_difference = int(r.get("last_hour")) - datetime.now().hour
    print(hour_difference)
    if hour_difference <= 1:
        print("Hour difference greater than 1, setting data")
        hour_data = db.get_hour_list()
        populate_chart(hour_data, "hour")
        avg_data = db.get_avg()
        populate_chart(avg_data, "avg")
    day_difference = int(r.get("last_day")) - datetime.now().day
    print(day_difference)
    if day_difference >= 1:
        print("Day difference greater than 1, setting data")
        day_data = db.get_day_list()
        populate_chart(day_data, "day")
    minute_difference = int(r.get("last_minute")) - datetime.now().minute
    print(minute_difference)
    if minute_difference >= 1:
        print("Minute difference greater than 1, setting data")
        minute_data = db.get_minute_list()
        populate_chart(minute_data, "minute")    
    
