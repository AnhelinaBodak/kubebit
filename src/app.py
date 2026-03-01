import os
from db import db
from flask import Flask, jsonify, request
from kubernetes import client, config
from start_stop_challenge import deploy_challenge, stop_challenge, set_k8s_client
from core.challenge import create_category, list_categories, create_container_challenge, list_challenges

try:
    config.load_incluster_config()
except:
    config.load_kube_config()

v1 = client.CoreV1Api() 
set_k8s_client(v1)

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = (
f"postgresql+psycopg2://"
f"{os.getenv('DB_USER')}:"
f"{os.getenv('DB_PASSWORD')}@"
f"{os.getenv('DB_HOST')}:"
f"{os.getenv('DB_PORT')}/"
f"{os.getenv('DB_NAME')}"
)

db.init_app(app)
with app.app_context():
    db.create_all()

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

@app.route("/admin/categories", methods=["POST"])
def add_category():
    data = request.get_json()

    try:
        category = create_category(data["name"])
        return jsonify({
            "id": category.id,
            "name": category.name
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
@app.route("/categories", methods=["GET"])
def get_all_categories():
    categories = list_categories()
    return jsonify([
        {"id": c.id, "name": c.name}
        for c in categories
    ])
    
@app.route("/admin/challenges/container", methods=["POST"])
def add_container_challenge():
    data = request.get_json()

    try:
        challenge = create_container_challenge(
            name=data["name"],
            base_points=data["base_points"],
            min_points=data.get("min_points", 0),
            flag=data["flag"],
            category_id=data["category_id"],
            docker_image=data["docker_image"],
            container_port=data["container_port"],
            description=data.get("description"),
            max_attempts=data.get("max_attempts"),
            cpu_limit=data.get("cpu_limit"),
            memory_limit=data.get("memory_limit"),
        )

        return jsonify({
            "id": challenge.id,
            "name": challenge.name,
            "type": challenge.type.value
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Internal server error"}), 500
    
@app.route("/challenges", methods=["GET"])
def get_all_challenges():
    challenges = list_challenges()

    result = []
    for c in challenges:
        result.append({
            "id": c.id,
            "name": c.name,
            "type": c.type.value,
            "base_points": c.base_points,
            "category_id": c.category_id
        })

    return jsonify(result)


if __name__ == "__main__":
    debug_mode = True if os.getenv("ENV") == "dev" else False
    app.run (debug=debug_mode, host="0.0.0.0")
