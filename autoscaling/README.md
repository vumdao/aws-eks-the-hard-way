<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Kubernetes Cluster Autoscaler With IRSA" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/autoscaling/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>Kubernetes Cluster Autoscaler With IRSA</b></div>
</h1>

## **IRSA is IAM Role for service account. This post shows you how to deploy Cluster Autoscaler as a deployment and assign IRSA for it to provide proper permission.**

<br>

## **Why do we need The Kubernetes Cluster Autoscaler?**
**The Kubernetes Cluster Autoscaler is a popular Cluster Autoscaling solution maintained by SIG Autoscaling. It is responsible for ensuring that your cluster has enough nodes to schedule your pods without wasting resources. It watches for pods that fail to schedule and for nodes that are underutilized. It then simulates the addition or removal of nodes before applying the change to your cluster. The AWS Cloud Provider implementation within Cluster Autoscaler controls the .DesiredReplicas field of your EC2 Auto Scaling Groups.**
<h1 align="center">
  <img src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/autoscaling/img/architecture.png?raw=true"/>
</h1>

## What’s In This Document
- [Apply cluster autoscaler deployment in kube-system](#-Apply-cluster-autoscaler-deployment-in-kube-system)
- [Create IAM role for service account](#-Create-IAM-role-for-service-account)
- [Annotate the EKS service account)](#-Annotate-the-EKS-service-account)
- [Restart the cluster autoscaler pod to take effect](#-Restart-the-cluster-autoscaler-pod-to-take-effect)
- [Undestand some Parameters in Autoscaler](#-Undestand-some-Parameters-in-Autoscaler)
- [Conclusion](#-Conclusion)

---

### 🚀 **[Apply cluster autoscaler deployment in kube-system](#-Apply-cluster-autoscaler-deployment-in-kube-system)**
- Download `cluster-autoscaler-autodiscover.yaml` file to update the command point to your EKS cluster and customize expected parameters such as Optimizing for Cost and Availability, Prevent Scale Down Eviction, 
```
wget https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml
```

- Edit the cluster-autoscaler container command to replace <YOUR CLUSTER NAME> (including <>) with your cluster's name, and add the following options.
```
--balance-similar-node-groups
--skip-nodes-with-system-pods=false
```

- Check the files at some important fields
  1. ServiceAccount
  2. Version of cluster autoscaler: `cluster-autoscaler:v1.17.3`
  3. Command
  ```
            command:
            - ./cluster-autoscaler
            - --v=4
            - --stderrthreshold=info
            - --cloud-provider=aws
            - --skip-nodes-with-local-storage=false
            - --expander=least-waste
            - --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/sel-eks-dev
            - --balance-similar-node-groups
            - --skip-nodes-with-system-pods=false
  ```

- Then we apply the yaml file and move to next step to create IRSA (IAM Role for service account) for the autoscaler deployment
```
$ kubectl get pod -n kube-system |grep autoscaler
cluster-autoscaler-68857f6759-cwd8b   1/1     Running   0          2d10h
```

### 🚀 **[Create IAM role for service account](#-Create-IAM-role-for-service-account)**

- Pre-requisite: EKS cluster with OpenID connect, IAM identity provider (Ref to [Using IAM Service Account Instead Of Instance Profile For EKS Pods
](https://dev.to/vumdao/using-iam-service-account-instead-of-instance-profile-for-eks-pods-262p) for how to)

- First create the IAM role which is federated by IAM identiy provider and assumed by `sts:AssumeRoleWithWebIdentity`, then attach policy to provide permission of autoscaling group for the role. Brief of CDK code in python3:
  - `iam_oic` is the stack of creating IAM identity provider which is used OIDC as provider, `open_id_connect_provider_arn` is its attribute from the stack.
```
        autoscaler_role = iam.Role(
            self, 'AutoScalerRole',
            role_name='sel-eks-oic-autoscaler-sa',
            assumed_by=iam.FederatedPrincipal(
                federated=f'{iam_oic.open_id_connect_provider_arn}',
                conditions={'StringEquals': string_like('kube-system', 'cluster-autoscaler')},
                assume_role_action='sts:AssumeRoleWithWebIdentity'
            )
        )

        asg_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "autoscaling:DescribeLaunchConfigurations",
                "autoscaling:DescribeTags",
                "autoscaling:SetDesiredCapacity",
                "autoscaling:TerminateInstanceInAutoScalingGroup",
                "ec2:DescribeLaunchTemplateVersions"
            ],
            resources=['*'],
            conditions={'StringEquals': {"aws:RequestedRegion": "ap-northeast-2"}}
        )

        autoscaler_role.add_to_policy(asg_statement)
```

- Trust relationships looks like:

```
{
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
          "oidc.eks.ap-northeast-2.amazonaws.com/id/<OIDC_PROVIDER_ID>:sub": "system:serviceaccount:kube-system:cluster-autoscaler",
          "oidc.eks.ap-northeast-2.amazonaws.com/id/<OIDC_PROVIDER_ID>:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

- Next step we annotate the EKS service account `cluster-autoscaler` with this role

### 🚀 **[Annotate the EKS service account](#-Annotate-the-EKS-service-account)**
- Run the `kubectl` command

```
kubectl annotate serviceaccounts -n kube-system cluster-autoscaler eks.amazonaws.com/role-arn=<IAM_role_arn_which_created_above>
```

- Check the SA
```
$ kubectl describe sa cluster-autoscaler -n kube-system
Name:                cluster-autoscaler
Namespace:           kube-system
Labels:              k8s-addon=cluster-autoscaler.addons.k8s.io
                     k8s-app=cluster-autoscaler
Annotations:         eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/sel-eks-oic-autoscaler-sa
                     kubectl.kubernetes.io/last-applied-configuration:
                       {"apiVersion":"v1","kind":"ServiceAccount","metadata":{"annotations":{},"labels":{"k8s-addon":"cluster-autoscaler.addons.k8s.io","k8s-app"...
Image pull secrets:  <none>
Mountable secrets:   cluster-autoscaler-token-xxxxx
Tokens:              cluster-autoscaler-token-xxxxx
Events:              <none>
```

### 🚀 **[Restart the cluster autoscaler pod to take effect](#-Restart-the-cluster-autoscaler-pod-to-take-effect)**

```
$ kubectl rollout restart deploy cluster-autoscaler -n kube-system
deployment.apps/cluster-autoscaler restarted
```
---
### We've done setting up the cluster autoscaler but we need to understand some parameters in autoscaler for better choices of Scalability, performance, availability and cost optimization.

### 🚀 **[Undestand some Parameters in Autoscaler](#-Undestand-some-Parameters-in-Autoscaler)**
**1. Spot instance:**
  - Save up to 90% off the on-demand price, with the trade-off the Spot Instances can be interrupted at any time when EC2 needs the capacity back.
  - To solve that we should select as many instance families as possible eg. M4, M5, M5a, and M5n instances all have similar amounts of CPU and Memory.
  - The strategy --expander=least-waste is a good general purpose default, and if you're going to use multiple node groups for Spot Instance diversification (Read more [Expanders](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md#what-are-expanders))

<p align="center">
  <img src="https://aws.github.io/aws-eks-best-practices/cluster-autoscaling/spot_mix_instance_policy.jpg" />
</p>

**2. Prevent Scale Down Eviction:**
- Some workloads are expensive to evict such as schedule running reports, cronjob to clear caches or doing backup. The Cluster Autoscaler will attempt to scale down any node under the scale-down-utilization-threshold, which will interrupt any remaining pods on the node. This can be prevented by ensuring that pods that are expensive to evict are protected by a label recognized by the Cluster Autoscaler.
- Ensure that: Expensive to evict pods have the annotation `cluster-autoscaler.kubernetes.io/safe-to-evict=false`

**3. EBS Volumes:**
- stateful applications such as database or cache which need high availability if sharded across multiple AZs using a separate EBS Volume for each AZ.
- Ensure that:
  - Node group balancing is enabled by setting balance-similar-node-groups=true.
  - Node Groups are configured with identical settings except for different availability zones and EBS Volumes.

---

### 🚀 **[Conclusion](#-Conclusion)**
- Using Cluster Autoscaler is the best practice in your EKS cluster, one of the most benifit is COST.

<p align="center">
  <img src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/autoscaling/img/reduce_bill.jpg?raw=true" />
</p>

**- Refs:**
  - https://docs.aws.amazon.com/eks/latest/userguide/cluster-autoscaler.html
  - https://aws.github.io/aws-eks-best-practices/cluster-autoscaling/cluster-autoscaling/

---


<h3 align="center">
  <a href="https://dev.to/vumdao">:stars: Blog</a>
  <span> · </span>
  <a href="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/autoscaling">Github</a>
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
