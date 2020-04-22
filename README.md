# mon_env
With this tool you can get realtime info about your machine

## How to use
- install requirements file modules
```
usage: mon_env.py [-h] [--start] [--stop] [--prometheus PROMETHEUS]
                  [--prometheus-retention PROMETHEUS_RETENTION]
                  [--node-exporter NODE_EXPORTER] [--grafana GRAFANA]

optional arguments:
  -h, --help            show this help message and exit
  --start               Start new monitoring environment
  --stop                Stop monitoring environment
  --prometheus PROMETHEUS
                        Enter Prometheus version(latest by default)
  --prometheus-retention PROMETHEUS_RETENTION
                        Enter Prometheus retention time(1d, 1m...)
  --node-exporter NODE_EXPORTER
                        Enter node-exporter version(latest by default)
  --grafana GRAFANA     Enter grafana version(latest by default)
```

## Example
- Run `sudo python3 ./mon_env.py --start --prometheus-retention=13h` to run \
monitoring environment with the latest version of Prometheus, Node exporter \
and Grafana, it is optional to specify the tool version.
- To access the dashboard browse `http://localhost:3000`
- Default creds:
```
Username: admin
Password: admin
```
* To stop and remove the monitoring environment just run the following command: `sudo python3 ./mon_env.py --stop`

(Note: the tool must to run with root privileges to work as expected)

