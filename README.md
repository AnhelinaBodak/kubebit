# Kubebit CTF Management Platform

This repository contains the backend for a Capture The Flag (CTF) platform. 
---

## 🗂 Repository Structure

```
Dockerfile
requirements.txt
k8s/
    deployment.yml
    postgres-service.yml
    postgres-statefulset.yml
    rbac.yml
    secret.yml
    service.yml
src/
    app.py                  # Flask application and HTTP routes
    db.py                   # SQLAlchemy setup
    models.py               # ORM models for users, teams, challenges, categories
    start_stop_challenge.py # helpers to deploy/stop pods & services
    core/                   # core business logic
        challenge.py        # create/list challenges & categories
        runtime.py          # runtime helpers for extracting container data
        team.py             # team-related logic
        user.py             # user-related logic
```

## ✅ Features & Capabilities

- **Category management** - create/list categories via REST API
- **Challenge management** - container-based CTF challenges with metadata stored in Postgres
- **Dynamic deployment** - start/stop challenge instances in Kubernetes namespaces (per-team basis) 
- **Namespace operations** - create and list Kubernetes namespaces for teams
- **Database models** - users, teams, challenges, container/files metadata

Currently only container challenges are exposed via HTTP; static/file challenges exist in model but API endpoints are not yet implemented.

## 📦 Architecture Overview

1. **Flask API** (`src/app.py`) is the entrypoint.
2. **SQLAlchemy** with Flask integration manages persistence in PostgreSQL.
3. **Kubernetes client** used for orchestration:
   - Namespaces are created per team
   - Pods and ClusterIP services are created when a user starts a challenge

## 🧩 Kubernetes Deployment

The `k8s/` directory contains manifests needed to deploy the management application and its database to a Kubernetes cluster.

- `rbac.yml` - service account, cluster role & binding allowing namespace/pod/service manipulation.
- `secret.yml` - Postgres credentials (ensure appropriate credentials usage).
- `postgres-statefulset.yml` & `postgres-service.yml` - stateful Postgres deployment.
- `deployment.yml` & `service.yml` - deployment and service for the Flask app (`k8s-manager`).

To deploy the resources, run:
```bash
kubectl apply -f k8s/
```
Ensure availability of image `k8s-manager`.

## 📬 API Endpoints

| Method | Path                         | Description                                       |
|--------|------------------------------|---------------------------------------------------|
| GET    | `/namespaces`                | List all namespaces                    |
| POST   | `/namespaces/{name}`         | Create a namespace                     |
| POST   | `/challenges/start`          | Start a challenge instance for a user       |
| POST   | `/challenges/stop`           | Stop a running challenge instance                |
| POST   | `/admin/categories`          | Create a new challenge category                  |
| GET    | `/categories`                | List all categories                              |
| POST   | `/admin/challenges/container`| Create a new container-based challenge          |
| GET    | `/challenges`                | List all challenges (metadata only)              |

> 🔒 Administrative routes are prefixed with `/admin` and currently unauthenticated; authentication/authorization is not implemented yet.

### Request payloads

- **Start/stop challenge**
  ```json
  {
    "user_id": 1,
    "challenge_id": 2,
    "team_id": 3
  }
  ```

- **Create category**
  ```json
  {"name": "crypto"}
  ```

- **Create container challenge**
  ```json
  {
    "name": "Web Exploit",
    "base_points": 500,
    "flag": "flag{example}",
    "category_id": 1,
    "docker_image": "myrepo/web-challenge:latest",
    "container_port": 5000
  }
  ```