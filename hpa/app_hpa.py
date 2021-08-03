from constructs import Construct
from cdk8s import Chart
from imports import k8s
from cdk8s import Chart, App


class AppHpa(Chart):
    def __init__(self, scope: Construct, id: str, name_space):
        super().__init__(scope, id, namespace=name_space)

        app_name = 'app'
        app_label = {'dev': app_name}
        k8s.KubeHorizontalPodAutoscalerV2Beta2(
            self, 'AppHpa',
            metadata=k8s.ObjectMeta(labels=app_label, name=app_name),
            spec=k8s.HorizontalPodAutoscalerSpec(
                max_replicas=2,
                min_replicas=1,
                scale_target_ref=k8s.CrossVersionObjectReference(
                    kind="Deployment",
                    name=app_name,
                    api_version='apps/v1'
                ),
                metrics=[
                    k8s.MetricSpec(
                        type='Resource',
                        resource=k8s.ResourceMetricSource(
                            name='cpu',
                            target=k8s.MetricTarget(type='Utilization', average_utilization=85)
                        )
                    )
                ]
            )
        )


app = App()
AppHpa(app, "app-hpa")
app.synth()
