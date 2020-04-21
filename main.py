import time
import json
import docker
import argparse
import requests
from os import path, mkdir
from shutil import copyfile


conf_path = '/etc/mon_env_conf/'
netwok_bridge_name = 'mon_env_conf_bridge'
prometheus_container_name = 'mon_prometheus'
node_exporter_container_name = 'mon_node_exporter'
grafana_container_name = 'mon_grafana'

# Set arguments
parser=argparse.ArgumentParser()
parser.add_argument('--prometheus', help='Enter Prometheus version(latest if not)', default='latest')
parser.add_argument('--prometheus-retention', help='Enter Prometheus retention time(1d, 1m...)', default='1d')
parser.add_argument('--node-exporter', help='Enter node-exporter version(latest if not)', default='latest')
parser.add_argument('--grafana', help='Enter grafana version(latest if not)', default='latest')
args=parser.parse_args()

# Create conf dir
if not path.exists(conf_path):
    mkdir(conf_path)

# Copy conf files to root fs
copyfile('./conf/prometheus.yml', conf_path + 'prometheus.yml')
copyfile('./conf/grafana.ini', conf_path + 'grafana.ini')

# init docker client obj
client = docker.from_env()

# Create new docker netwok bridge
ipam_pool = docker.types.IPAMPool(subnet='172.18.0.0/16', gateway='172.18.0.1')
ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
netwok_bridge = client.networks.create(netwok_bridge_name, driver="bridge", check_duplicate=True, ipam=ipam_config)

# Run Prometheus docker container
prometheus_container = client.containers.create('prom/prometheus:' + args.prometheus,
                                             detach=True,
                                             ports={'9090/tcp': 9090},
                                             volumes={conf_path + 'prometheus.yml': {'bind': '/etc/prometheus/prometheus.yml', 'mode': 'ro'}},
                                             command=['--storage.tsdb.retention.time=' + args.prometheus_retention, '--config.file=/etc/prometheus/prometheus.yml'],
                                             name=prometheus_container_name)

# Run node_exporter docker container
node_exporter_container = client.containers.create('prom/node-exporter:' + args.prometheus,
                                                detach=True, ports={'9100/tcp': 9100},
                                                volumes={'/': {'bind': '/host', 'mode': 'ro,rslave'}},
                                                name=node_exporter_container_name)

# Run Grafana docker container
grafana_container = client.containers.create('grafana/grafana:' + args.prometheus,
                                             detach=True,
                                             ports={'3000/tcp': 3000},
                                             volumes={conf_path + 'grafana.ini': {'bind': '/etc/grafana/grafana.ini', 'mode': 'ro'}},
                                             name=grafana_container_name)

# Connect containers to network bridge
netwok_bridge.connect(container=prometheus_container, ipv4_address='172.18.0.2')
netwok_bridge.connect(container=node_exporter_container, ipv4_address='172.18.0.3')
netwok_bridge.connect(container=grafana_container, ipv4_address='172.18.0.4')

prometheus_container.start()
node_exporter_container.start()
grafana_container.start()


# Retreiving Grafana API token
# TODO: wait somehow for Grafana docker to init
time.sleep(5)

# Switch to new grafana org
res = requests.post(url='http://admin:admin@localhost:3000/api/orgs', headers={"Content-Type": "application/json"}, data='{"name":"mon_env_conf_org"}')
org_info=json.loads(res.text)

requests.post(url='http://admin:admin@localhost:3000/api/user/using/' + str(org_info['orgId']))

# Getting Grafana API token
res = requests.post(url='http://admin:admin@localhost:3000/api/auth/keys', headers={"Content-Type": "application/json"}, data='{"name":"apikeycurl", "role": "Admin"}')
grafana_api_key = json.loads(res.text)['key']




grafana_post_headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer " + str(grafana_api_key)
}

# Publish new data source
grafana_post_datasource_url = "http://localhost:3000/api/datasources"
grafana_post_datasource_data = json.dumps({
  'name': 'Prometheus',
  'type': 'prometheus',
  'url': 'http://172.18.0.2:9090',
  'access': 'proxy',
  'basicAuth': False
})

# Send the request
requests.post(url=grafana_post_datasource_url, data=grafana_post_datasource_data, headers=grafana_post_headers)

# Publish dashboard
grafana_post_dashboard_url = "http://localhost:3000/api/dashboards/db"
grafana_post_dashboard_data = json.dumps({
  'dashboard': {
    'id': None,
    'uid': None,
    'title': 'Production Overview',
    'tags': [ 'templated' ],
    'timezon': 'browser',
    'schemaVersion': 16,
    'version': 0
  },
  'folderId': 0,
  'overwrite': False
})

# Send the request
res = requests.post(url=grafana_post_dashboard_url, headers=grafana_post_headers, data=grafana_post_dashboard_data)
print(res.text)