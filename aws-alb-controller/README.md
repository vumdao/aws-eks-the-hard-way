<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Create AWS Load Balancer Controller Ingress With CDK8S" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/aws-alb-controller/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>Create AWS Load Balancer Controller Ingress With CDK8S</b></div>
</h1>

## Table Of Contents
 * [What is AWS Load Balancer Controller](#What-is-AWS-Load-Balancer-Controller)
 * [Install AWS Load Balancer Controller as the ingress controller](#Install-AWS-Load-Balancer-Controller-as-the-ingress-controller)
 * [Create AWS ALB IAM Role Service Account Using CDK](#Create-AWS-ALB-IAM-Role-Service-Account-Using-CDK)
 * [Create Ingress Using CDK8S](#Create-Ingress-Using-CDK8S)
 * [Apply the ingress yaml files](#Apply-the-ingress-yaml-files)
 * [Create Route53 records for the domains using CDK](#Create-Route53-records-for-the-domains-using-CDK)
 * [Conclusion](#-Conclusion)

---

<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Create AWS Load Balancer Controller Ingress With CDK8S" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/aws-alb-controller/img/flow.png?raw=true"/>
  </a>
</p>

## 🚀 **What is AWS Load Balancer Controller** <a name="What is AWS Load Balancer Controller"></a>
- The [AWS Load Balancer Controller](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html) manages AWS Elastic Load Balancers for a Kubernetes cluster. The controller provisions the following resources.
  - An AWS Application Load Balancer (ALB) when you create a Kubernetes Ingress.
  - An AWS Network Load Balancer (NLB) when you create a Kubernetes Service of type LoadBalancer.


## 🚀 **Install AWS Load Balancer Controller as the ingress controller** <a name="Install AWS Load Balancer Controller as the ingress controller"></a>
- Pre-requiste: EKS cluster

- In order for the Ingress resource to work, the cluster must have an ingress controller running. Unlike other types of controllers which run as part of the kube-controller-manager binary, Ingress controllers are not started automatically with a cluster.

- Using hlem to install

```
[ec2-user@eks-ctl dist]$ helm repo add eks https://aws.github.io/eks-charts
"eks" has been added to your repositories

export VPC_ID=$(aws eks describe-cluster --name eks-dev --query "cluster.resourcesVpcConfig.vpcId" --output text --region ap-northeast-2)

[ec2-user@eks-ctl dist]$ helm repo list
NAME    URL
eks     https://aws.github.io/eks-charts

[ec2-user@eks-ctl dist]$ helm repo update
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "eks" chart repository
Update Complete. ⎈Happy Helming!⎈

helm upgrade -i aws-load-balancer-controller \
    eks/aws-load-balancer-controller \
    -n kube-system \
    --set clusterName=eks-dev \
    --set serviceAccount.create=false \
    --set serviceAccount.name=aws-load-balancer-controller \
    --set image.tag="${LBC_VERSION}" \
    --set region=ap-northeast-2 \
    --set vpcId=${VPC_ID}

Release "aws-load-balancer-controller" does not exist. Installing it now.
NAME: aws-load-balancer-controller
LAST DEPLOYED: Sun Jun  6 10:44:19 2021
NAMESPACE: kube-system
STATUS: deployed
REVISION: 1
TEST SUITE: None
NOTES:
AWS Load Balancer controller installed!

[ec2-user@eks-ctl dist]$ kubectl get deployment -n kube-system aws-load-balancer-controller
NAME                           READY   UP-TO-DATE   AVAILABLE   AGE
aws-load-balancer-controller   0/2     2            0           8s

[ec2-user@eks-ctl dist]$ kubectl get po -n kube-system 
NAME                                            READY   STATUS    RESTARTS   AGE
aws-load-balancer-controller-85847bc9bd-fjdwf   1/1     Running   0          20s
aws-load-balancer-controller-85847bc9bd-gsctk   1/1     Running   0          20s
```

## 🚀 **Create AWS ALB IAM Role Service Account Using CDK** <a name="Create AWS ALB IAM Role Service Account Using CDK"></a>
- Pre-requisite: EKS cluster with OpenID connect, IAM identity provider (Ref to [Using IAM Service Account Instead Of Instance Profile For EKS Pods](https://dev.to/vumdao/using-iam-service-account-instead-of-instance-profile-for-eks-pods-262p) for how to)

- First create the IAM role which is federated by IAM identiy provider and assumed by `sts:AssumeRoleWithWebIdentity`, then attach policy to provide proper permission for the role. Brief of CDK code in python3:
  - `iam_oic` is the stack of creating IAM identity provider which is used OIDC as provider, `open_id_connect_provider_arn` is its ARN attribute from the stack.
  - Policy is created from [iam_policy.json](https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json)

```
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
```

- Annotate the IRSA to aws-load-balancer-controller service account
```
$ kubectl annotate serviceaccount -n kube-system aws-load-balancer-controller eks.amazonaws.com/role-arn=arn:aws:iam::123456789012:role/eks-aws-load-balancer-controller-sa
```

- Double check the IAM role at the `Trust relationships` to ensure correct OIDC url and Condition
```{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.ap-northeast-2.amazonaws.com/id/<OIDC_PROVIDER_ID>"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.ap-northeast-2.amazonaws.com/id/<OIDC_PROVIDER_ID>:sub": "system:serviceaccount:kube-system:aws-load-balancer-controller",
          "oidc.eks.ap-northeast-2.amazonaws.com/id/<OIDC_PROVIDER_ID>:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```   

- Check the SA
```
[ec2-user@eks-ctl ~]$ kubectl describe sa -n kube-system aws-load-balancer-controller 
Name:                aws-load-balancer-controller
Namespace:           kube-system
Labels:              app.kubernetes.io/component=controller
                     app.kubernetes.io/name=aws-load-balancer-controller
Annotations:         eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/eks-aws-load-balancer-controller-sa
                     kubectl.kubernetes.io/last-applied-configuration:
                       {"apiVersion":"v1","kind":"ServiceAccount","metadata":{"annotations":{"eks.amazonaws.com/role-arn":"arn:aws:iam::123456789012:role/eks...
Image pull secrets:  <none>
Mountable secrets:   aws-load-balancer-controller-token-gjsc2
Tokens:              aws-load-balancer-controller-token-gjsc2
Events:              <none>
```

## 🚀 **Create Ingress Using CDK8S** <a name="Create Ingress Using CDK8S"></a>
- Pre-requiste: ACM cert to attach to the ALB
- [cdk8s example](https://dev.to/vumdao/cdk8s-example-2glk)
- Some notes: All ingresses should be in a group so we only need one AWS ALB. Group order shoulb be taken care to prioritize the rule with `host` conditions
- Source: https://github.com/vumdao/aws-eks-the-hard-way/tree/master/aws-alb-controller/ingress

## 🚀 **Apply the ingress yaml files** <a name="Apply the ingress yaml files"></a>
- After applying the yaml files, check all ingress

```
[ec2-user@eks-ctl ~]$ kubectl get ingress -A
NAMESPACE   NAME                     CLASS    HOSTS                       ADDRESS                                                           PORTS   AGE
argocd      argocd                   <none>   argocd.cloudopz.co          k8s-dev-06fc49d1xx-1234567890.ap-northeast-2.elb.amazonaws.com    80      14d
dev         app                      <none>   *                           k8s-dev-06fc49d1xx-1234567890.ap-northeast-2.elb.amazonaws.com    80      18d
dev         backend                  <none>   *                           k8s-dev-06fc49d1xx-1234567890.ap-northeast-2.elb.amazonaws.com    80      8d
dev         frontend                 <none>   *                           k8s-dev-06fc49d1xx-1234567890.ap-northeast-2.elb.amazonaws.com    80      8d
dev         dev-alb                  <none>   *                           k8s-dev-06fc49d1xx-1234567890.ap-northeast-2.elb.amazonaws.com    80      18d
grafana     grafana                  <none>   grafana.cloudopz.co         k8s-dev-06fc49d1xx-1234567890.ap-northeast-2.elb.amazonaws.com    80      7d3h
logging     kibana                   <none>   kibana.cloudopz.co          k8s-dev-06fc49d1xx-1234567890.ap-northeast-2.elb.amazonaws.com    80      25h
```

- Check aws-load-balancer-controller if your ingress does not work
```
kubectl logs -f --tail=100 -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```

## 🚀 **Create Route53 records for the domains using CDK** <a name="Create Route53 records for the domains using CDK"></a>
- In order to automate detect the AWS k8s ALB, we can use `lookup` function and base on the tag the AWS ALB controller created `ingress.k8s.aws/stack: <group>`

```
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
```

## 🚀 **Conclusion** <a name="Conclusion"></a>
- Keywords: IRSA, AWS ALB controller, ingress, cdk and cdk8s
- If we change order of the ingress group, it might make ALB downtime a little bit to re-generate the rules.

---

<h3 align="center">
  <a href="https://dev.to/vumdao">:stars: Blog</a>
  <span> · </span>
  <a href="https://github.com/vumdao/aws-eks-the-hard-way">Github</a>
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
