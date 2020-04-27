import re
import time
import json
import docker
import argparse
import requests
from shutil import rmtree, copyfile
from os import path, mkdir


# Load config
config = json.load(open("./config/config.json"))

# Set arguments
parser=argparse.ArgumentParser()
parser.add_argument('--start', help='Start new monitoring environment', action='store_true')
parser.add_argument('--stop', help='Stop monitoring environment', action='store_true')
parser.add_argument('--prometheus', help='Enter Prometheus version(latest by default)', default='latest')
parser.add_argument('--prometheus-retention', help='Enter Prometheus retention time(1d, 1m...)', default='1d')
parser.add_argument('--node-exporter', help='Enter node-exporter version(latest by default)', default='latest')
parser.add_argument('--grafana', help='Enter grafana version(latest by default)', default='latest')
args=parser.parse_args()


# Start monitoring
def start_monitor():
  # Create conf dir
  if not path.exists(config['ENV']['CONF_PATH']):
      mkdir(config['ENV']['CONF_PATH'])

  # Copy conf files to root fs
  copyfile(config['ENV']['LOCAL_CONF_PATH'] + config['PROMETHEUS']['YML'], config['ENV']['CONF_PATH'] + config['PROMETHEUS']['YML'])
  copyfile(config['ENV']['LOCAL_CONF_PATH'] + config['GRAFANA']['INI'], config['ENV']['CONF_PATH'] + config['GRAFANA']['INI'])

  # init docker client obj
  client = docker.from_env()

  # Create new docker netwok bridge
  netwok_bridge = client.networks.create(config['NETWORK']['BRIDGE_NAME'], driver="bridge", check_duplicate=True)

  # Validate Prometheus version(This action command is different between 1.x.x and 2.x.x versions)
  if args.prometheus is not 'latest':
    prom_version = args.prometheus[re.search(r"\d", args.prometheus).start()]
  
    if prom_version is '2':
      set_retention_time_command = '--storage.tsdb.retention.time='
    elif prom_version is '1':
      set_retention_time_command = '-storage.local.retention='
  else:
    set_retention_time_command = '--storage.tsdb.retention.time='

  # Run Prometheus docker container
  prometheus_container = client.containers.run(config['PROMETHEUS']['DOCKERHUB'] + args.prometheus,
                                              detach=True,
                                              ports={str(config['PROMETHEUS']['PORT']) + '/tcp': config['PROMETHEUS']['PORT']},
                                              volumes={config['ENV']['CONF_PATH'] + config['PROMETHEUS']['YML']: {'bind': '/etc/prometheus/' + config['PROMETHEUS']['YML'], 'mode': 'ro'}},
                                              command=['--config.file=/etc/prometheus/prometheus.yml', set_retention_time_command + args.prometheus_retention],
                                              name=config['PROMETHEUS']['CONTAINER_NAME'],
                                              network=config['NETWORK']['BRIDGE_NAME'])

  # Run node_exporter docker container
  node_exporter_container = client.containers.run(config['NODE_EXPORTER']['DOCKERHUB'] + args.node_exporter,
                                                  detach=True, ports={str(config['NODE_EXPORTER']['PORT']) + '/tcp': config['NODE_EXPORTER']['PORT']},
                                                  volumes={'/': {'bind': '/host', 'mode': 'ro,rslave'}},
                                                  name=config['NODE_EXPORTER']['CONTAINER_NAME'],
                                                  network=config['NETWORK']['BRIDGE_NAME'])

  # Run Grafana docker container
  grafana_container = client.containers.run(config['GRAFANA']['DOCKERHUB'] + args.grafana,
                                              detach=True,
                                              ports={str(config['GRAFANA']['PORT']) + '/tcp': config['GRAFANA']['PORT']},
                                              volumes={config['ENV']['CONF_PATH'] + 'grafana.ini': {'bind': '/etc/grafana/' + config['GRAFANA']['INI'], 'mode': 'ro'}},
                                              name=config['GRAFANA']['CONTAINER_NAME'],
                                              network=config['NETWORK']['BRIDGE_NAME'])

  ### Retreiving Grafana API token
  # Wait somehow for Grafana docker to start
  is_grafana_up = False

  while not is_grafana_up:
    try:
      res = json.loads(requests.get('http://localhost:3000/api/health', headers={"Accept": "application/json"}).text)['database']

      if res == 'ok':
        is_grafana_up = True
    except:
      continue

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
    'name': 'Prometheus_ds',
    'type': 'prometheus',
    'url': 'http://'+ config['PROMETHEUS']['CONTAINER_NAME'] +':' + str(config['PROMETHEUS']['PORT']),
    'access': 'proxy',
    'basicAuth': False
  })

  # Send the request
  requests.post(url=grafana_post_datasource_url, data=grafana_post_datasource_data, headers=grafana_post_headers)

  # Publish dashboard
  grafana_post_dashboard_url = "http://localhost:3000/api/dashboards/db"
  grafana_post_dashboard_data = json.dumps(json.load(open(config['ENV']['LOCAL_CONF_PATH'] + config['GRAFANA']['DASHBOAD_FILENAME'], 'r', encoding='utf-8')))

  # Send the request
  requests.post(url=grafana_post_dashboard_url, headers=grafana_post_headers, data=grafana_post_dashboard_data).text

  print('All set! you can access the dashboards here: http://localhost:3000 (username: admin, password: admin)')
  print('To stop monitoring enter command: `./mon_env.py --stop`')


# Stop monitoring 
def stop_monitor():
  # Delete conf dir
  if path.exists(config['ENV']['CONF_PATH']):
    rmtree(config['ENV']['CONF_PATH'])

  # Init docker client obj
  client = docker.from_env()

  # Remove containers
  for container in config['CONTAINERS_LIST']:
      this_container_obj = client.containers.get(container)
      this_container_obj.stop()
      this_container_obj.remove()

  # Remove network bridge
  netwok_bridge = client.networks.get(network_id=config['NETWORK']['BRIDGE_NAME'])
  netwok_bridge.remove()


########### Main ###########
if args.start:
  start_monitor()
else:
  stop_monitor()
