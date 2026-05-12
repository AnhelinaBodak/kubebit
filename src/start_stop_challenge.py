from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from core.runtime import get_container_data

v1 = None
CHALLENGE_SERVICE_ACCOUNT = "challenge-runner"

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

def ensure_challenge_service_account(namespace: str):
    try:
        v1.read_namespaced_service_account(
            name=CHALLENGE_SERVICE_ACCOUNT,
            namespace=namespace
        )
    except ApiException as e:
        if e.status != 404:
            raise

        service_account = client.V1ServiceAccount(
            metadata=client.V1ObjectMeta(name=CHALLENGE_SERVICE_ACCOUNT)
        )

        try:
            v1.create_namespaced_service_account(
                namespace=namespace,
                body=service_account
            )
        except ApiException as create_error:
            if create_error.status != 409:
                raise

def name_pod(user_id:int, challenge_id:int) -> str:
    return (f"user-{user_id}-challenge-{challenge_id}")

def name_service(user_id: int, challenge_id: int) -> str:
    return f"svc-user-{user_id}-challenge-{challenge_id}"

def build_resource_requirements(cpu_limit: str | None, memory_limit: str | None):
    limits = {}

    if cpu_limit:
        limits["cpu"] = cpu_limit

    if memory_limit:
        limits["memory"] = memory_limit

    if not limits:
        return None

    return client.V1ResourceRequirements(limits=limits)

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

    try:
        ensure_challenge_service_account(namespace)
    except ApiException as e:
        return {"error": e.reason, "details": e.body}, e.status
    
    pod_name = name_pod(user_id, challenge_id)

    try:
        v1.read_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as e:
        if e.status != 404:
            raise

    container_data = get_container_data(challenge_id)
    image = container_data.docker_image
    container_port = container_data.container_port
    resource_requirements = build_resource_requirements(
        container_data.cpu_limit,
        container_data.memory_limit
    )

    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(
            name = pod_name,
            labels = {
                "user-id": str(user_id),
                "challenge-id": str(challenge_id)
            }
        ),
        spec = client.V1PodSpec(
            service_account_name=CHALLENGE_SERVICE_ACCOUNT,
            automount_service_account_token=False,
            containers = [
                client.V1Container(
                    name = f"challenge-{challenge_id}",
                    image = image,
                    ports = [client.V1ContainerPort(container_port=container_port)],
                    resources=resource_requirements,
                    security_context = client.V1SecurityContext(
                        privileged=False,
                        allow_privilege_escalation=True,
                        capabilities=client.V1Capabilities(
                            drop=["ALL"]
                        )
                    )
                )
            ]
        )
    )

    try:
        v1.create_namespaced_pod(namespace=namespace, body=pod)
    except ApiException as e:
        return {"error": e.reason, "details": e.body}, e.status

    svc_name = create_service(user_id, challenge_id, namespace, port=80, target_port=container_port)

    return {"status": "started", "pod_name": pod_name, "svc_name": svc_name}

def stop_challenge(user_id: int, challenge_id:int, namespace: str):
    ok, err = ensure_namespace(namespace)
    if not ok:
        return err, 404
    
    pod_name = name_pod(user_id, challenge_id)
    svc_name = name_service(user_id, challenge_id)
    resources = {
        "pod": {"name": pod_name, "status": "deleted"},
        "service": {"name": svc_name, "status": "deleted"},
    }
    errors = []

    try:
        v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            resources["pod"]["status"] = "not_found"
        else:
            resources["pod"]["status"] = "error"
            errors.append({
                "resource": "pod",
                "error": e.reason,
                "details": e.body,
                "status": e.status
            })

    try:
        v1.delete_namespaced_service(name=svc_name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            resources["service"]["status"] = "not_found"
        else:
            resources["service"]["status"] = "error"
            errors.append({
                "resource": "service",
                "error": e.reason,
                "details": e.body,
                "status": e.status
            })

    if errors:
        return {
            "status": "partial_error",
            "pod_name": pod_name,
            "svc_name": svc_name,
            "resources": resources,
            "errors": errors
        }, errors[0]["status"]

    return {
        "status": "stopped",
        "pod_name": pod_name,
        "svc_name": svc_name,
        "resources": resources
    }
