from kubernetes import client
from kubernetes.client.exceptions import ApiException

v1 = None

def create_namespace(team_id):
    namespace_name = f"team-{team_id}"

    namespace = client.V1Namespace(
        metadata=client.V1ObjectMeta(name=namespace_name)
    )
    v1.create_namespace(namespace)

    create_challenge_service_account(namespace_name)

    return namespace

def create_challenge_service_account(namespace):
    service_acc = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name="challenge-runner"
        )
    )

    v1.create_namespaced_service_account(
        namespace=namespace,
        body=service_acc
    )