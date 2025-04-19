#!/bin/env python3

import json
import math
import mmh3
import os
import requests
import socket
from flask import Flask, request, abort

# -------------------------------------------------------------------------
HEADLESS_SERVICE_NAME = os.environ.get("HEADLESS_SERVICE_NAME", "key-value-svc")
REPLICAS = int(os.environ.get("REPLICAS", 4)) 
NAMESPACE_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
DB_DIR = "/db"
DB_FILE = os.path.join(DB_DIR, "a.json")


def get_namespace():
    """Return to the namespace in which the server instance is running."""
    try:
        with open(NAMESPACE_PATH, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: Namespace file not found at {NAMESPACE_PATH}. Falling back to 'default'.")
        return os.environ.get("POD_NAMESPACE", "default") 

NAMESPACE = get_namespace()

def own_name():
    """Return the name of the pod in which the server instance is running."""
    return socket.gethostname()

def pod_names():
    """Return pod names of the deployment based on StatefulSet naming convention."""
    statefulset_name = HEADLESS_SERVICE_NAME
    names = [f"{statefulset_name}-{i}" for i in range(REPLICAS)]
    return names

def remote_addr(pod_name):
    """
    Return the fully qualified domain name (FQDN) of POD_NAME.
    POD_NAME is a member of the list returned by pod_names().
    The FQDN is resolvable within the Kubernetes cluster thanks to the headless service.
    """
    return f"{pod_name}.{HEADLESS_SERVICE_NAME}.{NAMESPACE}.svc.cluster.local"

def load_db():
    """Load the database (a dict object) from the persistent volume."""
    try:
        os.makedirs(DB_DIR, exist_ok=True) 
        with open(DB_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Database file {DB_FILE} not found, starting with empty DB.")
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {DB_FILE}, starting with empty DB.") 
        return {}
    
def save_db(db):
    """Save the database (a dict object) to the persistent volume."""
    os.makedirs(DB_DIR, exist_ok=True)
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(db, f, indent=4)
    except IOError as e:
        print(f"Error saving database to {DB_FILE}: {e}")


# -------------------------------------------------------------------------
# Do not modify anything below this line

# These functions are based on the code of
# https://en.wikipedia.org/wiki/Rendezvous_hashing

def hash_to_unit_interval(s):
    """Hashes a string onto the unit interval (0, 1]"""
    return (mmh3.hash128(s) + 1) / 2**128

def compute_score(node_name, key):
    score = hash_to_unit_interval(f"{node_name}: {key}")
    log_score = 1.0 / -math.log(score)
    return log_score

def determine_responsible_node(nodes, key):
    """Determines which node of a set of NODES is responsible for KEY."""
    return max(
        nodes, key=lambda node: compute_score(node, key), default=None)

# -------------------------------------------------------------------------
def get_location(key):
    return determine_responsible_node(pod_names(), key)

def get_object_value(key):
    loc = get_location(key)
    if loc == own_name():
        db = load_db()
        print(db)
        val = db.get(key)
        if val is None:
            abort(404)
        return val
    else:
        addr  = remote_addr(loc)
        url = f"http://{addr}:5000/obj/{key}"
        ret = requests.get(url)
        if ret.status_code != 200:
            abort(ret.status_code)
        return ret.text

def set_object_value(key, value):
    loc = get_location(key)
    if loc == own_name():
        db = load_db()
        db[key] = value
        save_db(db)
        return ''
    else:
        addr = remote_addr(loc)
        url = f"http://{addr}:5000/obj/{key}/{value}"
        ret = requests.get(url)
        if ret.status_code != 200:
            abort(ret.status_code)
        return ret.text

# -------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/obj/<key>")
def get_object(key=None):
    return get_object_value(key)

@app.route("/obj/<key>/<val>")
def set_object(key=None, val=None):
    return set_object_value(key, val)

@app.get("/location/<key>")
def location(key=None):
    return get_location(key)

@app.route("/name")
def name():
    return own_name()

@app.route("/pod-names")
def names():
    return pod_names()

@app.route("/hello")
def hello_world():
    return "<p>Hello, World!</p>"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
