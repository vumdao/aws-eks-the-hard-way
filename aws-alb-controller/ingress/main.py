#!/usr/bin/env python
from constructs import Construct
from cdk8s import Chart, App
from imports import k8s

from akhqig import AkhqIngress
from appig import AppIngress
from argocdig import ArgoCdIngress
from backendig import BackendIngress
from frontendig import FrontendIngress
from grafanaig import GrafanaIngress
from kibanaig import KibanaIngress


class AwsIngressAlb(Chart):
    def __init__(self, scope: Construct, id: str, name_space):
        super().__init__(scope, id, namespace=name_space)

        """ Create default rule and redirect HTTP to HTTPS """
        app_name = 'dev-alb'
        app_label = {'dev': app_name}
        k8s.KubeIngressV1Beta1(
            self, 'AppIngress',
            metadata=k8s.ObjectMeta(
                annotations={
                    'kubernetes.io/ingress.class': 'alb',
                    'alb.ingress.kubernetes.io/scheme': 'internet-facing',
                    'alb.ingress.kubernetes.io/target-type': 'instance',
                    'alb.ingress.kubernetes.io/group.name': f"{name_space}",
                    'alb.ingress.kubernetes.io/ip-address-type': 'ipv4',
                    'alb.ingress.kubernetes.io/backend-protocol': 'HTTP',
                    'alb.ingress.kubernetes.io/backend-protocol-version': 'HTTP2',
                    'alb.ingress.kubernetes.io/listen-ports': '[{"HTTPS":443}, {"HTTP":80}]',
                    'alb.ingress.kubernetes.io/actions.ssl-redirect':
                        '{"Type": "redirect", "RedirectConfig": { "Protocol": "HTTPS", "Port": "443", "StatusCode": "HTTP_301"}}',
                    'alb.ingress.kubernetes.io/certificate-arn':
                        'arn:aws:acm:ap-northeast-2:123456789012:certificate/aaaa-bbbb-cccc-xxxx'
                },
                labels=app_label,
                name=app_name
            ),
            spec=k8s.IngressSpec(
                rules=[
                    k8s.IngressRule(
                        http=k8s.HttpIngressRuleValue(
                            paths=[
                                k8s.HttpIngressPath(
                                    backend=k8s.IngressBackend(
                                        service_name='ssl-redirect',
                                        service_port=k8s.IntOrString.from_string('use-annotation')
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )


app = App()
name_space = 'dev'
AwsIngressAlb(app, "AlbIngressInit", name_space=name_space)
AkhqIngress(app, "AkhqIngress", name_space=name_space)
AppIngress(app, "AppIngress", name_space=name_space)
BackendIngress(app, "BackendIngress", name_space=name_space)
FrontendIngress(app, "FrontendIngress", name_space=name_space)
ArgoCdIngress(app, "ArgoCdIngress", name_space="argocd")
GrafanaIngress(app, "GrafanaIngress", name_space="grafana")
KibanaIngress(app, 'KibanaIngress', name_space='logging')
app.synth()
