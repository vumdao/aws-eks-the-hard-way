from constructs import Construct
from cdk8s import Chart
from imports import k8s


class AkhqIngress(Chart):
    def __init__(self, scope: Construct, id: str, name_space):
        super().__init__(scope, id)

        app_name = 'akhq'
        app_label = {'dev': app_name}
        k8s.KubeIngressV1Beta1(
            self, 'AkhqIngress',
            metadata=k8s.ObjectMeta(
                annotations={
                    'kubernetes.io/ingress.class': 'alb',
                    'alb.ingress.kubernetes.io/group.name': f'{name_space}',
                    'alb.ingress.kubernetes.io/group.order': '3',
                    'alb.ingress.kubernetes.io/healthcheck-path': '/health',
                    'alb.ingress.kubernetes.io/actions.akhq-condition':
                        '{"Type":"forward","ForwardConfig":{"TargetGroups":[{"ServiceName":"akhq","ServicePort":"8080","Weight":100}]}}',
                    'alb.ingress.kubernetes.io/conditions.akhq-condition':
                        '[{"Field":"source-ip","SourceIpConfig":{"Values":["42.116.129.230/32"]}}]',
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
                        host=f"{name_space}-akhq.cloudopz.co",
                        http=k8s.HttpIngressRuleValue(
                            paths=[
                                k8s.HttpIngressPath(
                                    backend=k8s.IngressBackend(
                                        service_name='akhq-condition',
                                        service_port=k8s.IntOrString.from_string('use-annotation')
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )
