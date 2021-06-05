<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="IAM service account for aws-node DaemonSet" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/sa-daemonset-node/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>IAM service account for aws-node DaemonSet</b></div>
</h1>

## **In another words, this post is about Configuring the Amazon VPC CNI plugin to use IAM roles for service accounts**
- The Amazon VPC CNI plugin for Kubernetes is the networking plugin for pod networking in Amazon EKS clusters. The plugin is responsible for allocating VPC IP addresses to Kubernetes nodes and configuring the necessary networking for pods on each node. The plugin:
    - Requires IAM permissions, provided by the AWS managed policy AmazonEKS_CNI_Policy, to make calls to AWS APIs on your behalf.
    - Creates and is configured to use a service account named `aws-node` when it's deployed. The service account is bound to a Kubernetes `clusterrole` named `aws-node`, which is assigned the required Kubernetes permissions.

<br>

## **Why do we need service account seperated for aws-node daemonset?**
- The aws-node daemonset is configured to use a role assigned to the EC2 instances to assign IPs to pods. This role includes several AWS managed policies, e.g. AmazonEKS_CNI_Policy and EC2ContainerRegistryReadOnly that effectly allow all pods running on a node to attach/detach ENIs, assign/unassign IP addresses, or pull images from ECR. Since this presents a risk to your cluster, it is recommended that you update the aws-node daemonset to use IRSA.

---

## What’s In This Document
- [Create IRSA and attach proper policy](#-Create-IRSA-and-attach-proper-policy)
- [Annotate the IRSA to aws-node service account](#-Annotate-the-IRSA-to-aws-node-service-account)
- [Restart the aws-node daemonset to take effect](#-Restart-the-aws-node-daemonset-to-take-effect)
- [Conclusion](#-Conclusion)

---

### 🚀 **[Create IRSA and attach proper policy](#-Create-IRSA-and-attach-proper-policy)**
- Pre-requisite: EKS cluster with OpenID connect, IAM identity provider (Ref to [Using IAM Service Account Instead Of Instance Profile For EKS Pods
](https://dev.to/vumdao/using-iam-service-account-instead-of-instance-profile-for-eks-pods-262p) for how to)

- First create the IAM role which is federated by IAM identiy provider and assumed by `sts:AssumeRoleWithWebIdentity`, then attach policy to provide proper permission for the role. Brief of CDK code in python3:
  - `iam_oic` is the stack of creating IAM identity provider which is used OIDC as provider, `open_id_connect_provider_arn` is its ARN attribute from the stack.


```
        eks_cni_statement = iam.PolicyStatement(
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

        daemonset_role = iam.Role(
            self, 'DaemonsetIamRole',
            role_name='sel-eks-oic-daemonset-sa',
            assumed_by=iam.FederatedPrincipal(
                federated=f'arn:aws:iam::{env.account}:oidc-provider/{oidc_provider}',
                conditions={'StringEquals': string_like('kube-system', 'aws-node')},
                assume_role_action='sts:AssumeRoleWithWebIdentity'
            )
        )

        daemonset_role.add_to_policy(eks_cni_statement)
```

### 🚀 **[Annotate the IRSA to aws-node service account](#-Annotate-the-IRSA-to-aws-node-service-account)**

- Note: If you're using the Amazon EKS add-on with a 1.18 or later Amazon EKS cluster, we just need to add the Amazon VPC CNI Amazon EKS add-on with the role we select or default `aws-node`

- Important note; VPC CNI is also provided as a managed add-on, however I am not a big fan of this particular component to be managed by AWS. I would suggest you simply deploy your own configuration of VPC CNI (YAML format) using Flux. That way you will stay in control of what is actually being deployed. There were many issues with it and I won’t recommend moving this to be a managed add-on. So Manually Configuring the Amazon VPC CNI plugin to use IAM roles for service accounts

- If CNI version is later than 1.6 you can skip next step of applying CNI v1.7
```
kubectl describe daemonset aws-node --namespace kube-system | grep Image | cut -d "/" -f 2
```

- Download `aws-k8s-cni.yaml` to custom IAM role (optional) and then apply it
```
kubectl apply -f https://raw.githubusercontent.com/aws/amazon-vpc-cni-k8s/release-1.7/config/v1.7/aws-k8s-cni.yaml
```

- Annotate the IRSA to aws-node service account
```
$ kubectl annotate serviceaccount -n kube-system aws-node eks.amazonaws.com/role-arn=arn:aws:iam::123456789012:role/sel-eks-oic-daemonset-sa

$ kubectl exec aws-node-qct7x -n kube-system -- env |grep "AWS_ROLE\|AWS_REG"
AWS_REGION=ap-northeast-2
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/sel-eks-oic-daemonset-sa

$ kubectl get pod -A | grep aws-node
kube-system   aws-node-qct7x             1/1     Running   0          2m45s
```

