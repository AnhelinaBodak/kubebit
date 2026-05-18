import os
from db import db
from flask import Flask, jsonify, request, current_app, send_from_directory, session, redirect, url_for
from kubernetes import client, config
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from start_stop_challenge import deploy_challenge, stop_challenge, set_k8s_client
from core.challenge import create_category, list_categories, create_container_challenge, list_challenges, create_static_challenge
from core.competition import get_competition_settings, start_competition, update_scoring_config
from core.team import create_team, assign_captain, list_teams, list_users_in_team
from core.user import create_user, assign_user_to_team, list_users_with_teams, ensure_initial_admin, initialize_admin_password, admin_password_initialization_required, authenticate_user
from core.submission import submit_flag, list_user_solves, list_team_solves
from models import User

try:
    config.load_incluster_config()
except:
    config.load_kube_config()

v1 = client.CoreV1Api() 
set_k8s_client(v1)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "kubebit-dev-secret")

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
    ensure_initial_admin()
    get_competition_settings()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/ready", methods=["GET"])
def ready():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ready"})
    except Exception:
        return jsonify({"status": "not ready", "database": "unavailable"}), 503

def get_request_data():
    return request.get_json(silent=True) or {}

def user_payload(user):
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "team_id": user.team_id,
        "team_name": user.team.name if user.team else None,
        "points": user.points
    }

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)

def login_required_page(*roles):
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    if roles and user.role.value not in roles:
        return redirect(url_for(page_for_role(user.role.value)))
    return None

def page_for_role(role):
    if role == "admin":
        return "admin_users_page"
    if role == "auditor":
        return "auditor_page"
    return "player_tasks_page"

@app.route("/", methods=["GET"])
@app.route("/login", methods=["GET"])
def login_page():
    user = current_user()
    if user:
        return redirect(url_for(page_for_role(user.role.value)))
    return send_from_directory(app.static_folder, "login.html")

@app.route("/admin", methods=["GET"])
def admin_page():
    denied = login_required_page("admin")
    if denied:
        return denied
    return redirect(url_for("admin_users_page"))

@app.route("/admin/users", methods=["GET"])
def admin_users_page():
    denied = login_required_page("admin")
    if denied:
        return denied
    return send_from_directory(f"{app.static_folder}/admin", "users.html")

@app.route("/admin/teams", methods=["GET"])
def admin_teams_page():
    denied = login_required_page("admin")
    if denied:
        return denied
    return send_from_directory(f"{app.static_folder}/admin", "teams.html")

@app.route("/admin/challenges", methods=["GET"])
def admin_challenges_page():
    denied = login_required_page("admin")
    if denied:
        return denied
    return send_from_directory(f"{app.static_folder}/admin", "challenges.html")

@app.route("/player", methods=["GET"])
@app.route("/tasks", methods=["GET"])
def player_page():
    denied = login_required_page("user")
    if denied:
        return denied
    return redirect(url_for("player_tasks_page"))

@app.route("/player/tasks", methods=["GET"])
def player_tasks_page():
    denied = login_required_page("user")
    if denied:
        return denied
    return send_from_directory(f"{app.static_folder}/users", "tasks.html")

@app.route("/player/profile", methods=["GET"])
def player_profile_page():
    denied = login_required_page("user")
    if denied:
        return denied
    return send_from_directory(f"{app.static_folder}/users", "profile.html")

@app.route("/player/team", methods=["GET"])
def player_team_page():
    denied = login_required_page("user")
    if denied:
        return denied
    return send_from_directory(f"{app.static_folder}/users", "team.html")

@app.route("/auditor", methods=["GET"])
def auditor_page():
    denied = login_required_page("auditor")
    if denied:
        return denied
    return send_from_directory(app.static_folder, "auditor.html")

@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = get_request_data()

    try:
        user = authenticate_user(
            identity=data["identity"],
            password=data["password"]
        )
        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role.value
        return jsonify({
            "user": user_payload(user),
            "redirect_to": url_for(page_for_role(user.role.value))
        })
    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"status": "signed_out"})

@app.route("/auth/me", methods=["GET"])
def auth_me():
    user = current_user()
    if not user:
        return jsonify({"authenticated": False}), 401
    return jsonify({
        "authenticated": True,
        "user": user_payload(user)
    })

@app.route("/me/team", methods=["GET"])
def my_team():
    user = current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    if user.team_id is None:
        return jsonify({
            "team": None,
            "users": []
        })

    return jsonify(list_users_in_team(user.team_id))

@app.route("/me/solves", methods=["GET"])
def my_solves():
    user = current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    return jsonify(list_user_solves(user.id))

@app.route("/me/team/solves", methods=["GET"])
def my_team_solves():
    user = current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    if user.team_id is None:
        return jsonify([])
    return jsonify(list_team_solves(user.team_id))

@app.route("/admin/initialize-password", methods=["POST"])
def initialize_admin_password_route():
    data = get_request_data()

    try:
        password = data["password"]
        password_confirm = data.get("password_confirm")
        if password_confirm is not None and password != password_confirm:
            raise ValueError("Passwords do not match")

        return jsonify(initialize_admin_password(password))
    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("Failed to initialize admin password")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/initialize-password/status", methods=["GET"])
def initialize_admin_password_status():
    return jsonify({
        "required": admin_password_initialization_required()
    })

@app.route("/admin/competition", methods=["GET"])
def get_admin_competition():
    return jsonify(get_competition_settings())

@app.route("/admin/competition/scoring", methods=["POST"])
def update_admin_competition_scoring():
    data = get_request_data()

    try:
        return jsonify(update_scoring_config(data))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("Failed to update competition scoring")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/competition/start", methods=["POST"])
def start_admin_competition():
    try:
        return jsonify(start_competition())
    except SQLAlchemyError:
        current_app.logger.exception("Failed to start competition")
        return jsonify({"error": "Internal server error"}), 500

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
    data = get_request_data()
    if session.get("role") == "user":
        user = current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        if user.team_id is None:
            return jsonify({"error": "User must belong to a team before starting challenges"}), 400
        user_id = user.id
        team_id = user.team_id
    else:
        user_id = data["user_id"]
        team_id = data["team_id"]
    challenge_id = data["challenge_id"]
    namespace = f"team-{team_id}"
    result = deploy_challenge(user_id, challenge_id, namespace)
    return result

@app.route("/challenges/stop", methods=["POST"])
def stop_challenge_route():
    data = get_request_data()
    if session.get("role") == "user":
        user = current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        if user.team_id is None:
            return jsonify({"error": "User must belong to a team before stopping challenges"}), 400
        user_id = user.id
        team_id = user.team_id
    else:
        user_id = data["user_id"]
        team_id = data["team_id"]
    challenge_id = data["challenge_id"]
    namespace = f"team-{team_id}"
    result = stop_challenge(user_id, challenge_id, namespace)
    return result

@app.route("/admin/categories", methods=["POST"])
def add_category():
    data = get_request_data()

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
    data = get_request_data()

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

    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("Failed to create container challenge")
        return jsonify({"error": "Internal server error"}), 500
    except Exception:
        current_app.logger.exception("Unexpected error creating container challenge")
        return jsonify({"error": "Internal server error"}), 500
    
@app.route("/admin/challenges/static", methods=["POST"])
def add_static_challenge():
    data = get_request_data()

    try:
        challenge = create_static_challenge(
            name=data["name"],
            base_points=data["base_points"],
            min_points=data.get("min_points", 0),
            flag=data["flag"],
            category_id=data["category_id"],
            description=data.get("description"),
            max_attempts=data.get("max_attempts"),
            external_url=data.get("external_url")
        )

        return jsonify({
            "id": challenge.id,
            "name": challenge.name,
            "type": challenge.type.value
        }), 201

    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("Failed to create static challenge sql error")
        return jsonify({"error": "Internal server error"}), 500
    except Exception:
        current_app.logger.exception("Unexpected error creating static challenge")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/challenges", methods=["GET"])
def get_all_challenges():
    challenges = list_challenges()

    result = []
    for c in challenges:
        external_url = None
        if c.file_challenge:
            external_url = c.file_challenge.external_url
        elif c.container_file_challenge:
            external_url = c.container_file_challenge.external_url

        result.append({
            "id": c.id,
            "name": c.name,
            "type": c.type.value,
            "description": c.description,
            "base_points": c.base_points,
            "min_points": c.min_points,
            "max_attempts": c.max_attempts,
            "category_name": c.category.name if c.category else None,
            "external_url": external_url
        })

    return jsonify(result)


@app.route("/challenges/<int:challenge_id>/submit", methods=["POST"])
def submit_challenge_flag(challenge_id):
    data = get_request_data()

    try:
        if session.get("role") == "user":
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Authentication required"}), 401
        else:
            user_id = data["user_id"]

        result = submit_flag(
            user_id=user_id,
            challenge_id=challenge_id,
            submitted_flag=data["flag"]
        )
        return jsonify(result)
    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("Failed to submit challenge flag")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/users", methods=["POST"])
def add_user():
    data = get_request_data()

    try:
        user = create_user(
            name=data["name"],
            username=data["username"],
            email=data["email"],
            password=data["password"],
            role=data.get("role", "user")
        )
        return jsonify({
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "team_id": user.team_id
        }), 201
    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/users", methods=["GET"])
def get_all_users():
    return jsonify(list_users_with_teams())

@app.route("/teams", methods=["POST"])
def add_team():
    data = get_request_data()

    try:
        team = create_team(
            name=data["name"],
            captain_user_id=data.get("captain_user_id")
        )
        return jsonify(team), 201
    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/teams", methods=["GET"])
def get_all_teams():
    return jsonify(list_teams())

@app.route("/teams/<int:team_id>/users", methods=["POST"])
def add_user_to_team(team_id):
    data = get_request_data()

    try:
        user = assign_user_to_team(
            user_id=data["user_id"],
            team_id=team_id
        )
        return jsonify({
            "team_id": user.team_id,
            "user_id": user.id
        })
    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e.args[0]}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/teams/<int:team_id>/users", methods=["GET"])
def get_team_users(team_id):
    try:
        return jsonify(list_users_in_team(team_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

@app.route("/teams/<int:team_id>/captain", methods=["POST"])
def set_team_captain(team_id):
    data = get_request_data()

    try:
        captain_user_id = data.get("captain_user_id")
        if captain_user_id is None:
            captain_user_id = data["user_id"]

        result = assign_captain(
            team_id=team_id,
            captain_user_id=captain_user_id
        )
        return jsonify(result)
    except KeyError:
        return jsonify({"error": "Missing required field: captain_user_id"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    debug_mode = True if os.getenv("ENV") == "dev" else False
    app.run (debug=debug_mode, host="0.0.0.0")
