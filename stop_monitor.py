import docker
from os import path, mkdir
from shutil import rmtree


conf_path = '/etc/mon_env_conf/'
netwok_bridge_name = 'mon_env_conf_bridge'
containers_to_remove = ['mon_prometheus', 'mon_node_exporter', 'mon_grafana']

# Delete conf dir
if path.exists(conf_path):
    rmtree(conf_path)

# init docker client obj
client = docker.from_env()

for container in containers_to_remove:
    this_container_obj = client.containers.get(container)
    this_container_obj.stop()
    this_container_obj.remove()


# Remove network bridge
netwok_bridge = client.networks.get(network_id=netwok_bridge_name)
netwok_bridge.remove()
