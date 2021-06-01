#!/usr/bin/env python
import os

from constructs import Construct
from cdk8s import App, Chart
from imports import k8s


class CreateNameSpace(Chart):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)
        k8s.KubeNamespace(
            self, "NameSpace",
            metadata=k8s.ObjectMeta(name='dev')
        )


class ServiceAccount(Chart):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id, namespace='dev')
        k8s.KubeServiceAccount(
            self, "ServiceAccount",
            metadata=k8s.ObjectMeta(
                name='eks-sa',
                annotations={'eks.amazonaws.com/role-arn': 'arn:aws:iam::123456789012:role/eks-oic-dev-sa'}
            )
        )


class Deployment(Chart):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id, namespace='dev')

        app_name = 'aws-test-sa-default'
        app_label = {'app': app_name}
        k8s.KubeDeployment(
            self, f"Aws-TestDeployment-SA-Default",
            metadata=k8s.ObjectMeta(labels=app_label, name=app_name),
            spec=k8s.DeploymentSpec(
                replicas=1,
                selector=k8s.LabelSelector(match_labels=app_label),
                template=k8s.PodTemplateSpec(
                    metadata=k8s.ObjectMeta(labels=app_label),
                    spec=k8s.PodSpec(
                        containers=[
                            k8s.Container(
                                name=app_name,
                                image="mikesir87/aws-cli:v1",
                                command=["sleep 60"]
                            )
                        ]
                    )
                )
            )
        )

        app_name = 'aws-test-iam-sa'
        app_label = {'app': app_name}
        k8s.KubeDeployment(
            self, f"Aws-TestDeployment-IAM-SA",
            metadata=k8s.ObjectMeta(labels=app_label, name=app_name),
            spec=k8s.DeploymentSpec(
                replicas=1,
                selector=k8s.LabelSelector(match_labels=app_label),
                template=k8s.PodTemplateSpec(
                    metadata=k8s.ObjectMeta(labels=app_label),
                    spec=k8s.PodSpec(
                        service_account_name='sel-eks-sa',
                        containers=[
                            k8s.Container(
                                name=app_name,
                                image="mikesir87/aws-cli:v1",
                                command=["sleep 60"]
                            )
                        ]
                    )
                )
            )
        )


app = App()
CreateNameSpace(app, "namespace")
ServiceAccount(app, 'serviceaccount')
Deployment(app, "deployment")

app.synth()

