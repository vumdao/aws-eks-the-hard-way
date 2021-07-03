import re
import os
from constructs import Construct
import boto3
from aws_cdk import (
    App, Stack, Environment, Tags, CfnTag, Duration,
    aws_elasticloadbalancingv2 as elbv2,
    aws_route53 as _route53,
)


class Route53Stack(Stack):

    def __init__(self, scope: Construct, id: str, env, **kwargs) -> None:
        super().__init__(scope, id, env=env, **kwargs)

        def cname_record(record_name, hosted_zone):
            _route53.CnameRecord(
                self, 'Route53Cname',
                domain_name=alb_dns,
                record_name=record_name,
                zone=hosted_zone,
                ttl=Duration.minutes(1)
            )

        alb = elbv2.ApplicationLoadBalancer.from_lookup(
            self, "AlbIngress",
            load_balancer_tags={'ingress.k8s.aws/stack': 'dev'}
        )
        alb_dns = alb.load_balancer_dns_name

        dev_hosted_zone = 'Z88PZ8J8P8RXXX'

        hz = _route53.HostedZone.from_hosted_zone_attributes(
            self, id="HostedZone", hosted_zone_id=dev_hosted_zone, zone_name='cloudopz.co')

        records = ['dev.cloudopz.co', 'akhq.cloudopz.co', 'argocd.cloudopz.co',
                   'grafana.cloudopz.co', 'kibana.cloudopz.co']
        for record in records:
            cname_record(record, hz)
