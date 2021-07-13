from constructs import Construct
from eks_statements import EksWorkerRoleStatements
from aws_cdk import (
    Stack, Tags, RemovalPolicy,
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_efs as efs
)


class EksEfsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env, vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)

        efs_sg = ec2.SecurityGroup(
            self, 'EfsSG',
            vpc=vpc,
            description='EKS EFS SG',
            security_group_name='eks-efs'
        )
        efs_sg.add_ingress_rule(ec2.Peer.ipv4('10.3.0.0/16'), ec2.Port.all_traffic(), "EFS VPC access")
        Tags.of(efs_sg).add(key='cfn.eks-dev.stack', value='sg-stack')
        Tags.of(efs_sg).add(key='Name', value='eks-efs')
        Tags.of(efs_sg).add(key='env', value='dev')

        file_system = efs.FileSystem(
            self, construct_id,
            vpc=vpc,
            file_system_name='eks-efs',
            lifecycle_policy=efs.LifecyclePolicy.AFTER_14_DAYS,
            removal_policy=RemovalPolicy.DESTROY,
            security_group=efs_sg
        )

        Tags.of(file_system).add(key='cfn.eks-dev.stack', value='efs-stack')
        Tags.of(file_system).add(key='efs.csi.aws.com/cluster', value='true')
        Tags.of(file_system).add(key='Name', value='eks-efs')
        Tags.of(file_system).add(key='env', value='dev')

        policy_statement_1 = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "elasticfilesystem:DescribeAccessPoints",
                "elasticfilesystem:DescribeFileSystems"
            ],
            resources=['*'],
            conditions={'StringEquals': {"aws:RequestedRegion": "ap-northeast-2"}}
        )
        policy_statement_2 = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "elasticfilesystem:CreateAccessPoint",
                "elasticfilesystem:DeleteAccessPoint"
            ],
            resources=['*'],
            conditions={'StringEquals': {"aws:ResourceTag/efs.csi.aws.com/cluster": "true"}}
        )

        # EFS CSI SA
        efs_csi_role = iam.Role(
            self, 'EfsCSIRole',
            role_name='eks-efs-csi-sa',
            assumed_by=iam.FederatedPrincipal(
                federated=oidc_arn,
                assume_role_action='sts:AssumeRoleWithWebIdentity',
                conditions={'StringEquals': string_like('kube-system', 'efs-csi-controller-sa')},
            )
        )

        for stm in [policy_statement_1, policy_statement_2]:
            efs_csi_role.add_to_policy(stm)

        Tags.of(efs_csi_role).add(key='cfn.eks-dev.stack', value='role-stack')
