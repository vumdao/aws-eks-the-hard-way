from constructs import Construct
from cdk8s import Chart
from imports import k8s


class FrontendIngress(Chart):
    def __init__(self, scope: Construct, id: str, name_space):
        super().__init__(scope, id)

        app_name = 'frontend'
        app_label = {'dev': app_name}
        k8s.KubeIngressV1Beta1(
            self, 'FrontendIngress',
            metadata=k8s.ObjectMeta(
                annotations={
                    'kubernetes.io/ingress.class': 'alb',
                    'alb.ingress.kubernetes.io/group.name': f'{name_space}',
                    'alb.ingress.kubernetes.io/group.order': '100',
                    'alb.ingress.kubernetes.io/healthcheck-path': '/frontend/health-check.do',
                    'alb.ingress.kubernetes.io/actions.frontend-condition': '{"Type":"forward","ForwardConfig":{"TargetGroups":[{"ServiceName":"frontend","ServicePort":"2087","Weight":100}]}}',
                    'alb.ingress.kubernetes.io/conditions.frontend-condition': '[{"field":"path-pattern","pathPatternConfig":{"values":["/frontend/*"]}}]',
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
                        http=k8s.HttpIngressRuleValue(
                            paths=[
                                k8s.HttpIngressPath(
                                    backend=k8s.IngressBackend(
                                        service_name='frontend-condition',
                                        service_port=k8s.IntOrString.from_string('use-annotation')
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )
