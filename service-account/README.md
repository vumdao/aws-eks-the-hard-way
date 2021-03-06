<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Using IAM Service Account Instead Of Instance Profile For EKS Pods" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/service-account/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>Using IAM Service Account Instead Of Instance Profile For EKS Pods</b></div>
</h1>

### **- With IAM identity-based policies, you can specify allowed or denied actions and resources as well as the conditions under which actions are allowed or denied.**
### **- For multiple services in K8S how can we control the permission of using AWS resouce within the pod. The easiest way is to use instance profile which attached to the EKS node but trade-off with high risk of security. Let's go through this post to know more**

---

**TL,DR**

## What’s In This Document
- [Kubernetes Service Accounts](#-Kubernetes-Service-Accounts)
- [Verify the default service account in the eks cluster](#-Verify-the-default-service-account-in-the-eks-cluster)
- [IAM Roles for Service Accounts (IRSA)](#-IAM-Roles-for-Service-Accounts-(IRSA))
- [How to assign IAM roles to service account](#-How-to-assign-IAM-roles-to-service-account)
- [Create EKS cluster using AWS CDK](#-Create-EKS-cluster-using-AWS-CDK)
- [Create IAM identity provider - Type OpenID Connect](Create-IAM-identity-provider---Type-OpenID-Connect)
- [Create IAM Service Account Role bind with OIDC provider](Create-IAM-Service-Account-Role-bind-with-OIDC-provider)
- [Conclusion](#-Conclusion)

---

### 🚀 **[Kubernetes Service Accounts](#-Kubernetes-Service-Accounts)**
- A service account is a special type of object that allows you to assign a Kubernetes RBAC role to a pod. A default service account is created automatically for each Namespace within a cluster. When you deploy a pod into a Namespace without referencing a specific service account, the default service account for that Namespace will automatically get assigned to the Pod and the Secret, i.e. the service account (JWT) token for that service account, will get mounted to the pod as a volume at /var/run/secrets/kubernetes.io/serviceaccount.**

### 🚀 **[Verify the default service account in the eks cluster](#-Verify-the-default-service-account-in-the-eks-cluster)**

- Create Pod deployment without service account, here we use `aws-cli` image to test `s3` permission and then apply

```
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: aws-test
  name: aws-test
  namespace: dev
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aws-test
  template:
    metadata:
      labels:
        app: aws-test
    spec:
      containers:
        - image: mikesir87/aws-cli:v1
          name: aws-test
          command: ['sleep', '60']
```

- Get pod's ENV, expect there's no `AWS_ROLE_ARN` and `AWS_WEB_IDENTITY_TOKEN_FILE`

```
$ kubectl exec aws-test-854c4fb8c-9lpsv -- env |grep AWS
```

- Get the default token in `/var/run/secrets/kubernetes.io/serviceaccount/token`. Decoding the service account token in that directory will reveal the following metadata:

```
kubectl exec aws-test-854c4fb8c-9lpsv -- cat /var/run/secrets/kubernetes.io/serviceaccount/token
```

```
{
  "iss": "kubernetes/serviceaccount",
  "kubernetes.io/serviceaccount/namespace": "dev",
  "kubernetes.io/serviceaccount/secret.name": "default-token-qvr29",
  "kubernetes.io/serviceaccount/service-account.name": "default",
  "kubernetes.io/serviceaccount/service-account.uid": "d9378593-295f-4be0-a918",
  "sub": "system:serviceaccount:dev:default"
}
```

- The default service account has the following permissions to the Kubernetes API.
```
$ kubectl describe clusterrole system:discovery
Name:         system:discovery
Labels:       kubernetes.io/bootstrapping=rbac-defaults
Annotations:  rbac.authorization.kubernetes.io/autoupdate: true
PolicyRule:
  Resources  Non-Resource URLs  Resource Names  Verbs
  ---------  -----------------  --------------  -----
             [/api/*]           []              [get]
             [/api]             []              [get]
             [/apis/*]          []              [get]
             [/apis]            []              [get]
             [/healthz]         []              [get]
             [/livez]           []              [get]
             [/openapi/*]       []              [get]
             [/openapi]         []              [get]
             [/readyz]          []              [get]
             [/version/]        []              [get]
             [/version]         []              [get]
```

- The pod does not have any permissions in AWS services instead it might inherrit from instance profile if we do not block access to instance metadata.
- Next step we will create an IAM role service account which is fedderated by OpenID connector and assumed by `AssumeRoleWithWebIdentity`. Sound strange right? let's discover moore.

### 🚀 **[IAM Roles for Service Accounts (IRSA)](#-IAM-Roles-for-Service-Accounts-(IRSA))**

- IRSA is a feature that allows you to assign an IAM role to a Kubernetes service account. It works by leveraging a Kubernetes feature known as Service Account Token Volume Projection. Pods with service accounts that reference an IAM Role call a public OIDC discovery endpoint for AWS IAM upon startup.

- When an AWS API is invoked, the AWS SDKs calls `sts:AssumeRoleWithWebIdentity` and automatically exchanges the Kubernetes issued token for a AWS role credential.

- EKS Pod Identity Webhook mutates pods with a ServiceAccount with an `eks.amazonaws.com/role-arn` annotation by adding a ServiceAccount projected token volume and adding environment variables that configure the AWS SDKs to automatically assume the specified role. In order to work, an OIDC provider is configured in AWS IAM to trust the ServiceAccount tokens. The mutating webhook that runs as part of the EKS control plane injects the AWS Role ARN and the path to a web identity token file into the Pod as environment variables. These values can also be supplied manually.

```
AWS_ROLE_ARN=arn:aws:iam::AWS_ACCOUNT_ID:role/IAM_ROLE_NAME
AWS_WEB_IDENTITY_TOKEN_FILE=/var/run/secrets/eks.amazonaws.com/serviceaccount/token
```

- The kubelet will automatically rotate the projected token when it is older than 80% of its total TTL, or after 24 hours. The AWS SDKs are responsible for reloading the token when it rotates.**

![Alt-Text](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/service-account/img/flow.png?raw=true)

### 🚀 **[How to assign IAM roles to service account](#-How-to-assign-IAM-roles-to-service-account)**
- First you need EKS cluster to get OpenId connect (OIDC) URL. What is OIDC? OpenID Connect is a simple identity layer on top of the OAuth 2.0 protocol. It allows Clients to verify the identity of the End-User based on the authentication performed by an Authorization Server, as well as to obtain basic profile information about the End-User in an interoperable and REST-like manner.)

- Create IAM identity provider. IAM identity providers (IdPs) manage user identities outside of AWS. You can establish a trust relationship with an IdP to give external user identities permissions to use AWS resources in your account.

- Collect IAM open id connect provider arn and then create an IAM role and set Trust Relationship with Policy Document (limited by condition):

```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "<open_id_connect_provider_arn>"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.ap-northeast-2.amazonaws.com/id/<OIDC_PROVIDER_ID>:aud": "sts.amazonaws.com",
          "oidc.eks.ap-northeast-2.amazonaws.com/id/<OIDC_PROVIDER_ID>:sub": "system:serviceaccount:dev:sel-eks-sa"
        }
      }
    }
  ]
}
```

- Attach necessary policies/ managed policies for the role

---

<p align="center">
  <a href="https://dev.to/vumdao">
    <img src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/service-account/img/too_much.jpg?raw=true" width="500" />
  </a>
</p>

<h1 align="center">
  <div><b>NO, the most interesting parts waiting for you - Using AWS CDK to create all of the above and CDK8S to create your yaml files</b></div>
</h1>

### 🚀 **[Create EKS cluster using AWS CDK](#-Create-EKS-cluster-using-AWS-CDK)**

- The post is long enough to share EKS CDK code here but the IAM role service account, IAM identiy provider and OIDC need to be in same stack of EKS
- Usind `AWS CDK 2.0` to create EKS cluster, EKS admin role, EKS node role both principal is `eks.amazonaws.com`, EKS node group, IAM instace profile, OIDC provider, IAM identity provider, IAM service account role for projected service and `aws-node` DaemonSet

<p align="center">
  <a href="https://dev.to/vumdao">
    <img src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/service-account/img/eks_cdk.jpg?raw=true" width="300" />
  </a>
</p>

```
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
```

### 🚀 **[Create IAM Service Account Role bind with OIDC provider](Create-IAM-Service-Account-Role-bind-with-OIDC-provider)**

<p align="center">
  <a href="https://dev.to/vumdao">
    <img src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/service-account/img/oidc.jpg?raw=true" width="300" />
  </a>
</p>


- Create Service account using `CDK8S`

```
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
                name='sel-eks-sa',
                annotations={'eks.amazonaws.com/role-arn': 'arn:aws:iam::123456789012:role/sel-eks-oic-dev-sa'}
            )
        )

app = App()
CreateNameSpace(app, "namespace")
ServiceAccount(app, 'serviceaccount')
```

- Test: Use image `aws-cli` to test the S3 permission as we attached `AmazonS3ReadOnlyAccess` to the IRSA

```
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: aws-test
  name: aws-test
  namespace: dev
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aws-test
  template:
    metadata:
      labels:
        app: aws-test
    spec:
      containers:
        - image: mikesir87/aws-cli:v1
          name: aws-test
          command: ['sleep', '60']
      serviceAccountName: sel-eks-sa
```

```
$ kubectl exec aws-test-7d5c5b6b95-csphv -- env | grep AWS
AWS_DEFAULT_REGION=ap-northeast-2
AWS_REGION=ap-northeast-2
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/eks-oic-dev-sa
AWS_WEB_IDENTITY_TOKEN_FILE=/var/run/secrets/eks.amazonaws.com/serviceaccount/token
```

```
$ kubectl exec aws-test-7d5c5b6b95-csphv -- aws s3 ls | wc -l
76
```

### 🚀 **[Conclusion](#-Conclusion)**
- Why using IAM service account instead of instance profile?
  - There's no global/admin-level role in the cluster that can assume any other role used by apps in the cluster! As such, you never have to worry about a misconfiguration in your cluster granting elevated access to pods.

  - The IAM roles for service accounts feature provides the following benefits:
    - Least privilege — By using the IAM roles for service accounts feature, you no longer need to provide extended permissions to the node IAM role so that pods on that node can call AWS APIs. You can scope IAM permissions to a service account, and only pods that use that service account have access to those permissions. This feature also eliminates the need for third-party solutions such as kiam or kube2iam.
    - Credential isolation — A container can only retrieve credentials for the IAM role that is associated with the service account to which it belongs. A container never has access to credentials that are intended for another container that belongs to another pod.
    - Auditability — Access and event logging is available through CloudTrail to help ensure retrospective auditing.

- Finally you get the end but we can now sperate the roles for applications and the eks nodes, and later for more such autoscaler group service and daemonSet node.

<br/>

**Reference:**
- https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts-technical-overview.html
- https://aws.github.io/aws-eks-best-practices/security/docs/iam/
- https://docs.aws.amazon.com/eks/latest/userguide/cni-iam-role.html
- https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html#updating-vpc-cni-eks-add-on
- https://blog.mikesir87.io/2020/09/eks-pod-identity-webhook-deep-dive/
- https://openid.net/connect/

---


<h3 align="center">
  <a href="https://dev.to/vumdao">:stars: Blog</a>
  <span> · </span>
  <a href="https://github.com/vumdao/cdk8s-example">Github</a>
  <span> · </span>
  <a href="https://stackoverflow.com/users/11430272/vumdao">stackoverflow</a>
  <span> · </span>
  <a href="https://www.linkedin.com/in/vu-dao-9280ab43/">Linkedin</a>
  <span> · </span>
  <a href="https://www.linkedin.com/groups/12488649/">Group</a>
  <span> · </span>
  <a href="https://www.facebook.com/CloudOpz-104917804863956">Page</a>
  <span> · </span>
  <a href="https://twitter.com/VuDao81124667">Twitter :stars:</a>
</h3>
