#!/bin/bash

source <(grep = <(grep -A4 '\[db\]' config.ini | sed 's/ *= */=/g'))

mysql -u $user -p$password -D $schema <<EOF

UPDATE client_log SET client_count = (SELECT client_count FROM (SELECT * FROM client_log) as B WHERE date_desc = 'today') WHERE date_desc = 'yesterday';
UPDATE client_log SET client_count = (SELECT count(client_id) FROM clients) WHERE date_desc = 'today';
UPDATE service_log SET service_count = (SELECT service_count FROM (SELECT * FROM service_log) as B WHERE date_desc = 'today') WHERE date_desc = 'yesterday';
UPDATE service_log SET service_count = (SELECT (SELECT count(service_name) FROM dpow_mqtt.services WHERE service_name != 'private') + (SELECT private_count FROM dpow_mqtt.services WHERE service_name = 'private')) WHERE date_desc = 'today';
DELETE FROM requests WHERE response_ts < CURRENT_TIMESTAMP() - INTERVAL 1 MONTH;
DELETE FROM clients WHERE last_action < CURRENT_TIMESTAMP() - INTERVAL 1 MONTH;

EOF