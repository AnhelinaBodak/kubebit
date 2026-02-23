from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

v1 = None

def set_k8s_client(client_instance):
    global v1
    v1 = client_instance

def ensure_namespace(namespace):
    try:
        v1.read_namespace(name=namespace)
        return True, None
    except ApiException as e:
        if e.status==404: return False, {"message": "Team doesn't exist"}
        raise

def name_pod(user_id:int, challenge_id:int) -> str:
    return (f"user-{user_id}-challenge-{challenge_id}")

def name_service(user_id: int, challenge_id: int) -> str:
    return f"svc-user-{user_id}-challenge-{challenge_id}"

def create_service(user_id: int, challenge_id: int, namespace: str, port: int = 80, target_port: int = 5000):
    svc_name = name_service(user_id, challenge_id)
    
    svc = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=svc_name,
            labels={
                "user-id": str(user_id),
                "challenge-id": str(challenge_id),
            },
        ),
        spec=client.V1ServiceSpec(
            type="ClusterIP",
            selector={
                "user-id": str(user_id),
                "challenge-id": str(challenge_id),
            },
            ports=[
                client.V1ServicePort(
                    port=port,
                    target_port=target_port,
                )
            ],
        ),
    )

    try:
        v1.create_namespaced_service(namespace=namespace, body=svc)
        return svc_name
    except ApiException as e:
        if e.status == 409: return svc_name
        raise

def deploy_challenge(user_id: int, challenge_id:int, namespace: str):
    ok, err = ensure_namespace(namespace)
    if not ok:
        return err, 404
    
    pod_name = name_pod(user_id, challenge_id)

    try:
        v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as e:
        if e.status != 404:
            raise

    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(
            name = pod_name,
            labels = {
                "user-id": str(user_id),
                "challenge-id": str(challenge_id)
            }
        ),
        spec = client.V1PodSpec(
            containers = [
                client.V1Container(
                    name = f"challenge-{challenge_id}",
                    image = "angelu/challenge_1:v1",
                    ports = [client.V1ContainerPort(container_port=5000)]
                )
            ]
        )
    )

    try:
        v1.create_namespaced_pod(namespace=namespace, body=pod)
    except ApiException as e:
        return {"error": e.reason, "details": e.body}, e.status

    svc_name = create_service(user_id, challenge_id, namespace, port=80, target_port=5000)

    return {"status": "started", "pod_name": pod_name, "svc_name": svc_name}

def stop_challenge(user_id: int, challenge_id:int, namespace: str):
    ok, err = ensure_namespace(namespace)
    if not ok:
        return err, 404
    
    pod_name = name_pod(user_id, challenge_id)
    svc_name = name_service(user_id, challenge_id)

    try:
        v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as e:
        if e.status == 404: return {"message": "Pod doesn't exist"}, 404
        return {"error": e.reason, "details": e.body}, e.status

    try:
        v1.delete_namespaced_service(name=svc_name, namespace=namespace)
    except ApiException as e:
        if e.status != 404:
            raise

    return {"status": "stopped", "pod_name": pod_name, "svc_name": svc_name}

    
