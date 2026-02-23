from flask import Flask, jsonify, request
from kubernetes import client, config
from start_stop_challenge import deploy_challenge, stop_challenge, set_k8s_client
import os

try:
    config.load_incluster_config()
except:
    config.load_kube_config()

v1 = client.CoreV1Api() 
set_k8s_client(v1)

app = Flask(__name__)

@app.route("/namespaces", methods=["GET"])
def list_namespaces():
    v1 = client.CoreV1Api()
    namespaces = v1.list_namespace()
    names = [ns.metadata.name for ns in namespaces.items]
    return jsonify({"namespaces": names})

@app.route("/namespaces/<name>", methods=["POST"])
def create_namespace(name):
    v1 = client.CoreV1Api()
    namespace = client.V1Namespace(
        metadata=client.V1ObjectMeta(name=name)
    )
    v1.create_namespace(namespace)
    return jsonify({"created": name}), 201

@app.route("/challenges/start", methods=["POST"])
def start_challenge_route():
    data = request.get_json()
    user_id = data["user_id"]
    challenge_id = data["challenge_id"]
    team_id = data["team_id"]
    namespace = f"team-{team_id}"
    result = deploy_challenge(user_id, challenge_id, namespace)
    return result

@app.route("/challenges/stop", methods=["POST"])
def stop_challenge_route():
    data = request.get_json()
    user_id = data["user_id"]
    challenge_id = data["challenge_id"]
    team_id = data["team_id"]
    namespace = f"team-{team_id}"
    result = stop_challenge(user_id, challenge_id, namespace)
    return result

if __name__ == "__main__":
    debug_mode = True if os.getenv("ENV") == "dev" else False
    app.run (debug=debug_mode, host="0.0.0.0")
