from constructs import Construct
from cdk8s import Chart
from imports import k8s


class KibanaIngress(Chart):
    def __init__(self, scope: Construct, id: str, name_space):
        super().__init__(scope, id, namespace=name_space)

        app_name = 'kibana'
        app_label = {'dev': app_name}
        k8s.KubeIngressV1Beta1(
            self, 'KibanaIngress',
            metadata=k8s.ObjectMeta(
                annotations={
                    'kubernetes.io/ingress.class': 'alb',
                    'alb.ingress.kubernetes.io/group.name': 'dev',
                    'alb.ingress.kubernetes.io/group.order': '7',
                    'alb.ingress.kubernetes.io/healthcheck-path': '/api/status',
                    'alb.ingress.kubernetes.io/backend-protocol': 'HTTP',
                    'alb.ingress.kubernetes.io/listen-ports': '[{"HTTPS":443}]',
                    'alb.ingress.kubernetes.io/certificate-arn':
                        'arn:aws:acm:ap-northeast-2:123456789012:certificate/aaaa-bbbb-cccc-xxxx'
                },
                labels=app_label,
                name=app_name
            ),
            spec=k8s.IngressSpec(
                rules=[
                    k8s.IngressRule(
                        host="kibana.cloudopz.co",
                        http=k8s.HttpIngressRuleValue(
                            paths=[
                                k8s.HttpIngressPath(
                                    backend=k8s.IngressBackend(
                                        service_name='kibana',
                                        service_port=k8s.IntOrString.from_number(5601)
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )
