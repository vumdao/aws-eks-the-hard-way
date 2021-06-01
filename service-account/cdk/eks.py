from constructs import Construct
from aws_cdk import (
    App, Stack, Environment, Tags, CfnJson, CfnOutput,
    aws_eks as eks,
    aws_ec2 as ec2,
    aws_iam as iam
)
import re


class RunAllAtOnce:
    def __init__(self):
        app = App()
        _env = Environment(region="ap-northeast-2", account=account)
        cluster = EksTestStack(app, 'EksClusterStack', env=_env)
        IamOICProvider(app, 'EksOICIdentityProvider', eks_cluster=cluster.eks_cluster, env=_env)

        app.synth()


class EksTestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, env, **kwargs) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)

        self.eks_cluster = None
        self.acc_id = env.account
        statement = EksWorkerRoleStatements(self.acc_id)

        eks_private_vpc = ec2.Vpc(self, "EksPrivateVPC", cidr='10.3.0.0/16', max_azs=2, nat_gateways=1)

        # EKS Admin role
        eks_admin_role = iam.Role(
            self, 'EKSMasterRole', role_name='eks-admin-role', assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )
        eks_admin_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"))
        eks_admin_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("IAMFullAccess"))
        eks_admin_role.add_to_policy(statement.admin_statement())

        # EKS Node Role
        node_role = iam.Role(
            self, "EKSNodeRole", role_name='eks-node-role', assumed_by=iam.ServicePrincipal("eks.amazonaws.com")
        )
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSClusterPolicy"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"))
        node_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSServicePolicy"))

        # Create EKS cluster
        self.eks_cluster = eks.Cluster(
            scope=self, id='EKSDevCluster',
            vpc=eks_private_vpc,
            default_capacity=0,
            cluster_name='eks-dev',
            masters_role=eks_admin_role,
            core_dns_compute_type=eks.CoreDnsComputeType.EC2,
            version=eks.KubernetesVersion.V1_19,
            role=node_role
        )

        # Worker Role
        worker_role = iam.Role(self, "EKSWorkerRole", role_name='eks-worker-role',
                               assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))
        attached_policy = ['AmazonEC2ContainerRegistryReadOnly', 'AmazonEKSWorkerNodePolicy']
        for policy in attached_policy:
            worker_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name(policy))
        worker_role.add_to_policy(statement.eks_cni())

        ssh_worker_sg = ec2.SecurityGroup(
            self, 'EksWorkerSSHSG',
            vpc=eks_private_vpc,
            description='EKS SSH to worker nodes',
            security_group_name='eks-ssh'
        )
        ssh_worker_sg.add_ingress_rule(ec2.Peer.ipv4('10.3.0.0/16'), ec2.Port.tcp(22), "SSH Access")

        self.eks_cluster.add_nodegroup_capacity(
            id="EksNodeGroup",
            desired_size=1,
            disk_size=20,
            instance_types=[ec2.InstanceType("r5a.xlarge")],
            labels={'role': 'worker', 'type': 'stateless'},
            max_size=2,
            min_size=1,
            nodegroup_name='eks-dev-node-group',
            node_role=worker_role,
            remote_access=eks.NodegroupRemoteAccess(ssh_key_name='dev-t', source_security_groups=[ssh_worker_sg]),
            subnets=ec2.Subnetection(subnet_type=ec2.SubnetType.PRIVATE)
        )


class EksWorkerRoleStatements(object):
    def __init__(self, acc_id) -> None:
        self.acc_id = acc_id

    @staticmethod
    def admin_statement():
        policy_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=['*'],
            resources=['*'],
            conditions={'StringEquals': {"aws:RequestedRegion": "ap-northeast-2"}}
        )
        return policy_statement

    @staticmethod
    def eks_cni():
        policy_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:AssignPrivateIpAddresses",
                "ec2:AttachNetworkInterface",
                "ec2:CreateNetworkInterface",
                "ec2:DeleteNetworkInterface",
                "ec2:DescribeInstances",
                "ec2:DescribeTags",
                "ec2:DescribeNetworkInterfaces",
                "ec2:DescribeInstanceTypes",
                "ec2:DetachNetworkInterface",
                "ec2:ModifyNetworkInterfaceAttribute",
                "ec2:UnassignPrivateIpAddresses",
                "ec2:CreateTags"
            ],
            resources=['*'],
            conditions={'StringEquals': {"aws:RequestedRegion": "ap-northeast-2"}}
        )
        return policy_statement


class IamOICProvider(Stack):
    def __init__(self, scope: Construct, construct_id: str, eks_cluster, env, **kwargs) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)

        statement = EksWorkerRoleStatements(env.account)
        oidc_url = eks_cluster.cluster_open_id_connect_issuer_url
        iam_oic = iam.OpenIdConnectProvider(
            self, construct_id,
            url=oidc_url,
            client_ids=['sts.amazonaws.com']
        )
        Tags.of(iam_oic).add(key='cfn.eks-dev.stack', value='iam-pid-stack')

        oidc_provider = re.sub("https://", "", oidc_url)

        def string_like(name_space, sa_name):
            string = CfnJson(
                self, f'JsonCondition{sa_name}',
                value={
                    f'{oidc_provider}:sub': f'system:serviceaccount:{name_space}:{sa_name}',
                    f'{oidc_provider}:aud': 'sts.amazonaws.com'
                }
            )
            return string

        oic_role = iam.Role(
            self, 'EksIAMServiceAccountRole',
            role_name='sel-eks-oic-dev-sa',
            assumed_by=iam.FederatedPrincipal(
                federated=f'arn:aws:iam::{env.account}:oidc-provider/{oidc_provider}',
                conditions={'StringEquals': string_like('dev', 'sel-eks-sa')},
                assume_role_action='sts:AssumeRoleWithWebIdentity'
            )
        )

        oic_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name('AmazonS3ReadOnlyAccess'))

        oic_role.add_to_policy(statement.cognito_power_statement())
        oic_role.add_to_policy(statement.admin_statement())
        oic_role.add_to_policy(statement.ddb_statement())

        daemonset_role = iam.Role(
            self, 'DaemonsetIamRole',
            role_name='sel-eks-oic-daemonset-sa',
            assumed_by=iam.FederatedPrincipal(
                federated=f'arn:aws:iam::{env.account}:oidc-provider/{oidc_provider}',
                conditions={'StringEquals': string_like('kube-system', 'aws-node')},
                assume_role_action='sts:AssumeRoleWithWebIdentity'
            )
        )
        daemonset_role.add_to_policy(statement.eks_cni())
