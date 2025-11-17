# COSC 3P95 Assignment 2
## Running the assignment
You must first run server.py.
```
$ python (or python3) server.py
```
Then run up to 5 instances of client.py in separate terminals.
```
$ python client.py
```
By default, tracing is enabled and ALWAYS_ON sampling is used.

You can run server.py and client.py with different values for tracing (true/false) and sampling rate (0-1.0)
```
$ TRACING_ENABLED=true/false SAMPLING_RATE=(0.0-1.0) python3 server/client.py
```
## Set up Docker 
In the assignment directory, use the following command to create Docker containers
```
$ docker-compose up -d
```
To view Jaeger data, go to http://localhost:16686/

To view Prometheus data, go to http://localhost:9090/

## Get JSON files
Either download the results while in Jaeger or use the following commands

Export client traces
```
$ curl "http://localhost:16686/api/traces?service=file-transfer-client&limit=100" > client_traces.json

```
Export server traces
```
$ curl "http://localhost:16686/api/traces?service=file-transfer-server&limit=100" > server_traces.json

```

## Statistical Debugging
In the GitHub repository, switch to the statistical-debugging branch to view the version of the assignment with buggy code (30% chance of using wrong compression for large files, which can lead to data corruption) 

## Tests
If you want to reproduce how data was gathered, simply run
```
$ python test.py
```
Within test.py, modify this line if you only want to focus on one config at a time
```
configs = [
    {"name": "No Tracing", "tracing": "false", "sampling": "1.0", "runs": 5},
    {"name": "Full Tracing", "tracing": "true", "sampling": "1.0", "runs": 5},
    {"name": "25% Sampling", "tracing": "true", "sampling": "0.25", "runs": 20},
]
```
Each branch (main and statistical-debugging) has its own version of analyze_traces.py. 
### Main
analyze_traces.py analyzes one of or both of client_traces.json and server_traces.json using the following command:
```
$ python analyze_traces.py client_traces.json
 ```
 You can compare the two using:
 ```
 $ python analyze_traces.py client_traces.json server_traces.json
 ```
 If you want to compare different sampling configurations
 ```
$ python analyze_traces.py -- compare configuration1.json configuration2.json "config1" "config2"
 ```

 ### Statistical Debugging
 analyze_traces.py analyzes predicate correlations for Statistical Debugging, finding which predicates correlate with failures, and printing predicate rankings

 Simply call
 ``` 
 $ python analyze_traces.py file.json
 ```

