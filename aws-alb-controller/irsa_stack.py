from constructs import Construct
from aws_cdk.aws_s3_assets import Asset
from aws_cdk import (
    App, Stack, CfnJson,
    aws_iam as iam
)

import re, os


class IamOICProvider(Stack):
    def __init__(f, scope: Construct, construct_id: str, eks_cluster, env, **kwargs) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)

        oidc_url = eks_cluster.cluster_open_id_connect_issuer_url
        iam_oic = iam.OpenIdConnectProvider(
            f, construct_id,
            url=oidc_url,
            client_ids=['sts.amazonaws.com']
        )
        oidc_arn = iam_oic.open_id_connect_provider_arn
        oidc_provider = re.sub("https://", "", oidc_url)

        def string_like(name_space, sa_name):
            string_like = CfnJson(
                f, f'JsonCondition{sa_name}',
                value={
                    f'{oidc_provider}:sub': f'system:serviceaccount:{name_space}:{sa_name}',
                    f'{oidc_provider}:aud': 'sts.amazonaws.com'
                }
            )
            return string_like

        alb_controller_role = iam.Role(
            f, 'AlbControllerRole',
            role_name='eks-aws-load-balancer-controller-sa',
            assumed_by=iam.FederatedPrincipal(
                federated=f'{iam_oic.open_id_connect_provider_arn}',
                conditions={'StringEquals': string_like('kube-system', 'aws-load-balancer-controller')},
                assume_role_action='sts:AssumeRoleWithWebIdentity'
            )
        )
        alb_controller_role.add_managed_policy(
            iam.ManagedPolicy.from_managed_policy_name(f, "EksAWSLoadBalancerController",
                                                       managed_policy_name='EksAWSLoadBalancerController')
        )
        alb_controller_role.add_managed_policy(
            iam.ManagedPolicy.from_managed_policy_name(f, "EksAWSLoadBalancerControllerAdditional",
                                                       managed_policy_name='EksAWSLoadBalancerControllerAdditional')
        )
