<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="EKS Cluster CONSOLE CREDENTIALS" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/eks-console-ctl/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>EKS Cluster CONSOLE CREDENTIALS</b></div>
</h1>

## **OOPS!!! `"error: You must be logged in to the server (Unauthorized)"`** - If you get this error when trying to run `kubectl` commands, Read more ⤵️⤵️⤵️

<br>

**- When an Amazon EKS cluster is created, the IAM entity (user or role) that creates the cluster is added to the Kubernetes RBAC authorization table as the administrator (with `system:masters` permissions). Initially, only that IAM user can make calls to the Kubernetes API server using kubectl. So ensure that your console such as EC2 instance attached that user/role credential for further steps, otherwise, no way to use the `kubectl`.**
</br>

**-In this tutorial, we will introduce how to create an IAM entity that having the `system:master` permissions on the existing EKS cluster, attaching this role to an EC2 instance and accessing to EKS cluster via kubectl installed on this instance.**

<br>

<h1 align="center">
  <img src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/eks-console-ctl/img/flow.png?raw=true" width="700"/>
</h1>

## What’s In This Document
- [Authentication and authorization in Amazon EKS](#-Authentication-and-authorization-in-Amazon-EKS)
- [Check aws-auth ConfigMap to see which role is bind with the cluster](#-Check-aws-auth-ConfigMap-to-see-which-role-is-bind-with-the-cluster)
- [Check the AWS credentials for an IAM role that's attached to an instance](#-Check-the-AWS-credentials-for-an-IAM-role-that's-attached-to-an-instance)
- [Create kubeconfig file to access EKS cluster](#-Create-kubeconfig-file-to-access-EKS-cluster)
- [Allowing a user/role or instance profile call API to EKS cluster](#-Allowing-a-user/role-or-instance-profile-call-API-to-EKS-cluster)
- [Conclusion](#-Conclusion)

---

## Pre-Requisite:
- EKS cluster
- IAM fully access

---

### 🚀 **[Authentication and authorization in Amazon EKS](#-Authentication-and-authorization-in-Amazon-EKS)**
- Explain in simple way, when you make an API call to EKS cluster through `kubectl`, a token is generated using the IAM credentials that are returned with the `aws sts get-caller-identity` command
- Amazon EKS uses that token authentication webhook to authenticate the request but it still relies on native Kubernetes RBAC for authorization.
- The crux of this integration between IAM and RBAC is the `aws-auth` ConfigMap applied to the Amazon EKS cluster that provides the mappings between IAM principals (roles/users) and Kubernetes Subjects (Users/Groups).
- Ref: https://aws.amazon.com/blogs/containers/kubernetes-rbac-and-iam-integration-in-amazon-eks-using-a-java-based-kubernetes-operator/

<h1 align="center">
  <img src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/eks-console-ctl/img/RBAC-IAM.png?raw=true" width="700"/>
</h1>

### 🚀 **[Check aws-auth ConfigMap to see which role is bind with the cluster](#-Check-aws-auth-ConfigMap-to-see-which-role-is-bind-with-the-cluster)**

<br/>

- Following command will show that the role `role/eks-admin-role` with proper IAM permissions is added to the Kubernetes RBAC authorization table as the administrator (with `system:masters` permissions).

```
[ec2-user@eks-ctl ~]$ kubectl describe configmap -n kube-system aws-auth
Name:         aws-auth
Namespace:    kube-system
Labels:       aws.cdk.eks/prune-c8c49db9cb02222a1111111db00d4db8236bxxxxxx=
Annotations:  kubectl.kubernetes.io/last-applied-configuration:
                {"apiVersion":"v1","data":{"mapAccounts":"[]","mapRoles":"[{\"rolearn\":\"arn:aws:iam::123456789012:role/eks-admin-role\",\"username\":\"

Data
====
mapAccounts:
----
[]
mapRoles:
----
[{"rolearn":"arn:aws:iam::123456789012:role/eks-admin-role","username":"arn:aws:iam::123456789012:role/eks-admin-role","groups":["system:masters"]},{"rolearn":"arn:aws:iam::123456789012:role/eks-worker-role","username":"system:node:{{EC2PrivateDNSName}}","groups":["system:bootstrappers","system:nodes"]}]
mapUsers:
----
[]
Events:  <none>
```

- Now, if you have permission to attach that role to the EC2 instance or AWS cloud9, move to next step to create kubeConfig file

### 🚀 **[Create kubeconfig file to access EKS cluster](#-Create-kubeconfig-file-to-access-EKS-cluster)**

<br/>

- What is Kubeconfig File - A kubeconfig file is a file used to configure access to Kubernetes when used in conjunction with the kubectl commandline tool (or other clients).
- How to generate kubeconfig file?

```
[ec2-user@eks-ctl ~]$ aws eks update-kubeconfig --name eks-cluster --region ap-northeast-2
Added new context arn:aws:eks:ap-northeast-2:123456789012:cluster/eks-cluster to /home/ec2-user/.kube/config
```

- Check content of the file `/home/ec2-user/.kube/config` (or use command `kubectl config view --minify`) and notice at the `exec args`. When you use `kubectl` to interact with Amazon EKS under the hood it uses the `aws eks get-token` command to fetch an authentication token, which is passed along in the Authorization header of an HTTP request sent to the Kubernetes API server.

```
[ec2-user@eks-ctl ~]$ kubectl config view --minify
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: DATA+OMITTED
    server: <API server endpoint>
  name: arn:aws:eks:ap-northeast-2:123456789012:cluster/eks-cluster
contexts:
- context:
    cluster: arn:aws:eks:ap-northeast-2:123456789012:cluster/eks-cluster
    user: arn:aws:eks:ap-northeast-2:123456789012:cluster/eks-cluster
  name: arn:aws:eks:ap-northeast-2:123456789012:cluster/eks-cluster
current-context: arn:aws:eks:ap-northeast-2:123456789012:cluster/eks-cluster
kind: Config
preferences: {}
users:
- name: arn:aws:eks:ap-northeast-2:123456789012:cluster/eks-cluster
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1alpha1
      args:
      - --region
      - ap-northeast-2
      - eks
      - get-token
      - --cluster-name
      - eks-cluster
      command: aws
      env: null
```

### 🚀 **[Allowing a user/role or instance profile call API to EKS cluster](#-Allowing-a-user/role-or-instance-profile-call-API-to-EKS-cluster)**

<br/>

**- To check the AWS credentials for an IAM role that's attached to an instance, run following command**

```
[ec2-user@eks-ctl ~]$ curl http://169.254.169.254/latest/meta-data/iam/security-credentials/eks-admin-role
{
  "Code" : "Success",
  "LastUpdated" : "2021-06-12T06:23:32Z",
  "Type" : "AWS-HMAC",
  "AccessKeyId" : "<AWS_ACCESS_KEY>",
  "SecretAccessKey" : "<AWS_SECRET_KEY>",
  "Token" : "<THE_TOKEN",
  "Expiration" : "2021-06-12T12:38:22Z"
}
```

- **Note:** If running the preceding curl command returns a 404 error, check the following:

```
$ export NO_PROXY=169.254.169.254
```

**- If you have full IAM access you can add more usre/role to access the EKS cluster by update the `aws-auth` ConfigMap**
- Run `kubectl edit configmap aws-auth -n kube-system`
  - Add the IAM user to mapUsers here is `eks-test` user (no need to add any permission for this user)

  ```
  mapUsers: |
    - userarn: arn:aws:iam::123456789012:user/eks-test
      username: eks-test
      groups:
        - system:masters
  ```

  - Add the IAM role to mapRoles

  ```
  mapRoles: |
    - rolearn: arn:aws:iam::123456789012:role/testrole
      username: testrole
      groups:
        - system:masters
  ```

**- Then update kubeConfig file again with that role or user**
  - For adding role
  
    ```
    aws eks update-kubeconfig --name eks-cluster-name --region aws-region --role-arn arn:aws:iam::123456789012:role/testrole
    ```

  - For adding user, no more option but need to update kubeConfile for using `--profile eks-test` (you need to create this profile with AWS key and credential of that user)

    ```
    aws eks update-kubeconfig --name eks-cluster-name --region aws-region
    ```

    ```
    user:
      exec:
        apiVersion: client.authentication.k8s.io/v1alpha1
        args:
        - --region
        - ap-northeast-2
        - eks
        - get-token
        - --cluster-name
        - eks-cluster
        - --profile
        - eks-test
        command: aws
    ```

**- Verify**
```
 $ kubectl get node
NAME                                          STATUS   ROLES    AGE     VERSION
ip-10-0-0-0.ap-northeast-2.compute.internal   Ready    <none>   2d22h   v1.19.6-eks-49a6c0
```

### 🚀 **[Conclusion](#-Conclusion)**

<br/>

- Setting up the console credential to control EKS cluster using cloud9 or EC2 (directly) is optional since mostly use CLI-driven
- But, if you’d like full access to your EKS cluster in the EKS console it is recommended.

---

<h3 align="center">
  <a href="https://dev.to/vumdao">:stars: Blog</a>
  <span> · </span>
  <a href="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/eks-console-ctl">Github</a>
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
