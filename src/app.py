from flask import Flask, jsonify
from kubernetes import client, config

try:
    config.load_incluster_config()
except:
    config.load_kube_config()

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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
