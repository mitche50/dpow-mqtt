# Nano Distributed POW Dashboard  
The purpose of this dashboard is to show the health of the distributed proof of work 
network and provide some key performance indicators for reference.  The dashboard runs 
on a flask server which requires configuration through a reverse proxy and connects to the 
DPoW Network using MQTT.

## Setup  
Requirements for this setup:

`sudo apt update`

`sudo apt install python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools python3-venv nginx redis-server`

It's recommended to use a virtual environment to handle the python requirements.

Steps:
1. Activate the redis server: `sudo systemctl enable redis-server.service`
2. Navigate to the dpow-mqtt directory
3. Activate your virtual environment: `virtualenv venv`
4. `source venv/bin/activate`
5. run: `pip install -r requirements.txt`
6. Copy the example services to the systemd directory:   
`sudo cp exampleflaskservice.service /etc/systemd/system/dpowdash.service`  
`sudo cp exampleservice.service /etc/systemd/system/dpowmqtt.service`
7. Update services with proper information:  
`sudo vim /etc/systemd/system/dpowdash.service`  
`sudo vim /etc/systemd/system/dpowmqtt.service`
8. Copy the exampleconfig.ini: `cp exampleconfig.ini config.ini`
9. Update the config.ini with appropriate values: `sudo vim config.ini`
10. Ensure dpow.py is executable: `sudo chmod -x mqtt.py`
11. Modify the shebang at the top of mqtt.py to the correct path.  Example: `/home/{YOUR_USER}/dpow-mqtt/venv/bin/python3`
12. `sudo systemctl start dpowdash` `sudo systemctl start dpowmqtt` - start the dashboard & mqtt client
13. `sudo systemctl enable dpowdash` `sudo systemctl enable dpowmqtt` - start the services on boot

After the service is running, you must configure Nginx to proxy requests
1. `sudo vim /etc/nginx/sites-available/dpowdash`
2. Update the file as below:  
```
server {
    listen 80;
    server_name {YOUR_DOMAIN} www.{YOUR_DOMAIN};

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/{YOUR_USER}/dpow-mqtt/dpowdash.sock;
    }
}
```

&nbsp;&nbsp;3\. Create a link to the enabled sites directory: `sudo ln -s /etc/nginx/sites-available/dpowdash /etc/nginx/sites-enabled`<br/>
&nbsp;&nbsp;4\. Test for syntax errors: `sudo nginx -t`<br/>
&nbsp;&nbsp;5\. If no errors: `sudo systemctl restart nginx`<br/>
&nbsp;&nbsp;6\. Ensure that Nginx is allowed: `sudo ufw allow 'Nginx Full'`

The final step is to set up a cron job to run the log updates every 24 hours.  This gives 
the client_log and service_log their information to generate the change over 24 hours.
1. Ensure the log_update.sh file is executable: `sudo chmod +x log_update.sh`
2. Run `sudo crontab -e` and select whatever editor you're comfortable with.
3. Insert the following line at the end of the file: `0 2 * * * {YOUR_USERNAME} /path/to/dpow-mqtt/log_update.sh`
4. Update log_update.sh to direct to the correct path of config.ini: `/path/to/dpow-mqtt/config.ini`

You should now be able to navigate to `http://{YOUR_DOMAIN}` to access the dashboard.
HTTPS is recommended, but not required.  For more information, google Certbot to easily generate a 
certificate and enable HTTPS.

## Troubleshooting
If you notice that you're not able to reach via your registered domain, check permissions for the folders.  
Standards suggest to set the owner and group to root:www-data so nginx has access.