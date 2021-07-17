<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="AWS EKS With EFS CSI Driver And IRSA Using CDK" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/efs-csi/img/cover.jpg?raw=true" width="800" />
  </a>
</p>
<h1 align="center">
  <div><b>AWS EKS With EFS CSI Driver And IRSA Using CDK</b></div>
</h1>

## Abstract
- For multiple pods which need to read/write same data, Amazon Elastic File System (EFS) is the best choice. This post guieds you the new way to create and setup EFS on EKS with IAM role for service account using IaC AWS CDK v2

## Table Of Contents
 * [What is Amazon Elastic File System?](#What-is-Amazon-Elastic-File-System?)
 * [EFS provisioner Architecture](#EFS-provisioner-Architecture)
 * [What is Amazon EFS CSI driver?](#What-is-Amazon-EFS-CSI-driver?)
 * [Amazon EFS Access Points](#Amazon-EFS-Access-Points)
 * [Create EFS Using CDK](#Create-EFS-Using-CDK)
 * [Create IAM role for service account for CSI](#-Create-IAM-role-for-service-account-for-CSI)
 * [Install EFS CSI using helm](#-Install-EFS-CSI-using-helm)
 * [Create storageclass, pv and pvc - Dynamic Provisioning](#-Create-storageclass,-pv-and-pvc---Dynamic-Provisioning)
 * [Create storageclass, pv and pvc - EFS Access Points](#-Create-storageclass,-pv-and-pvc---EFS-Access-Points)
 * [How to troubleshoot](#-How-to-troubleshoot)

---

## 🚀 **What is Amazon Elastic File System?** <a name="What-is-Amazon-Elastic-File-System?"></a>
- [Amazon Elastic File System (Amazon EFS)](https://www.youtube.com/watch?v=AvgAozsfCrY) provides a simple, scalable, fully managed elastic NFS file system for use with AWS Cloud services and on-premises resources.

## 🚀 **EFS provisioner Architecture** <a name="EFS-provisioner-Architecture"></a>
<p align="center">
  <a href="https://dev.to/vumdao">
    </br>
    <img alt="EFS provisioner Architecture" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/efs-csi/img/efs-provisioner-arch.png?raw=true" width="700"/>
  </a>
</p>

- The EFS volume at the top of the figure is an AWS-provisioned EFS volume, therefore managed by AWS, separately from Kubernetes. As most of AWS resources are, It will be attached to a VPC, Availability zones and subnets. And it will be protected by security groups.

- This volume can basically be mounted anywhere you can mount volumes using the NFS protocol. So you can mount it on your laptop (considering you configured AWS security groups accordingly), which can be very useful for test or debug purposes. Or you can mount it in Kubernetes. And that’s what will do both the EFS-provisioner (in order to configure sub-volumes inside the EFS volume) and your pods (in order to access the sub-volumes).

- When the EFS provisioner is deployed in Kubernetes, a new StorageClass “efs” is available and managed by this provisioner. You can then create a PVC that references this StorageClass. By doing so, the EFS provisioner will see your PVC and begin to take care of it, by doing the following:

    - Create a subdir in the EFS volume, dedicated to this PVC
    - Create a PV with the URI of this subdir (Address of the EFS volume + subdir path) and related info that will enable pods to use this subdir as a storage location using NFS protocol
    - Bind this PV to the PVC

- Now when a pod is designed to use PVC, it will use the PV’s info in order to connect directly to the EFS volume and use the subdir.

- Ref: https://www.padok.fr/en/blog/efs-provisioner-kubernetes

- Previously, I wrote a post introduce EFS provisoner using `quay.io/external_storage/efs-provisioner:latest` (an OpenShift Container Platform pod that mounts the EFS volume as an NFS share), [read more](https://dev.to/vumdao/eks-persistent-storage-with-efs-amazon-service-14ei).

- In this post, I introduce CSI Driver provisioner

## 🚀 **What is CSI driver?** <a name="What-is-CSI-driver?"></a>
- A [CSI driver](https://kubernetes-csi.github.io/docs/deploying.html) is typically deployed in Kubernetes as two components: a controller component and a per-node component.

- Controller Plugin

![controller](https://kubernetes-csi.github.io/docs/images/sidecar-container.png)

- Node plugin

![node](https://kubernetes-csi.github.io/docs/images/kubelet.png)

- How the two components works?

![flow](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/efs-csi/img/csi-flow.png?raw=true)

## 🚀 **What is Amazon EFS CSI driver?** <a name="What-is-Amazon-EFS-CSI-driver?"></a>
- The [Amazon EFS Container Storage Interface (CSI) driver](https://github.com/kubernetes-sigs/aws-efs-csi-driver) provides a CSI interface that allows Kubernetes clusters running on AWS to manage the lifecycle of Amazon EFS file systems.

- EFS CSI driver supports dynamic provisioning and static provisioning. Currently Dynamic Provisioning creates an access point for each PV. This mean an AWS EFS file system has to be created manually on AWS first and should be provided as an input to the storage class parameter. For static provisioning, AWS EFS file system needs to be created manually on AWS first. After that it can be mounted inside a container as a volume using the driver.

- What is the benefit of using EFS CSI Driver? - [Introducing Amazon EFS CSI dynamic provisioning](https://aws.amazon.com/blogs/containers/introducing-efs-csi-dynamic-provisioning/)

## 🚀 **Amazon EFS Access Points** <a name="Amazon-EFS-Access-Points"></a>
- [Amazon EFS access points](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html) are application-specific entry points into an EFS file system that make it easier to manage application access to shared datasets. Access points can enforce a user identity, including the user's POSIX groups, for all file system requests that are made through the access point. Access points can also enforce a different root directory for the file system so that clients can only access data in the specified directory or its subdirectories.

- You can use AWS Identity and Access Management (IAM) policies to enforce that specific applications use a specific access point. By combining IAM policies with access points, you can easily provide secure access to specific datasets for your applications.

---

## We go through the introductions from above, now going to setup.
</br>

## 🚀 **Create EFS Using CDK** <a name="Create-EFS-Using-CDK"></a>
- Note: We need tag `{key='efs.csi.aws.com/cluster', value='true'}` so that later we restrict the IAM permission within this EFS only

```
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
```


## 🚀 **Create IAM role for service account for CSI** <a name="Create-IAM-role-for-service-account-for-CSI"></a>

```
...
    @staticmethod
    def efs_csi_statement():
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

        return [policy_statement_1, policy_statement_2]
```

```
...
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
        for stm in statement.efs_csi_statement():
            efs_csi_role.add_to_policy(stm)
        Tags.of(efs_csi_role).add(key='cfn.eks-dev.stack', value='role-stack')
```


## 🚀 **Install EFS CSI using helm** <a name="Install-EFS-CSI-using-helm"></a>
- Use the above service account as external parameter

```
helm repo add aws-efs-csi-driver https://kubernetes-sigs.github.io/aws-efs-csi-driver/
helm repo update
helm upgrade -i aws-efs-csi-driver aws-efs-csi-driver/aws-efs-csi-driver \
  --namespace kube-system \
  --set serviceAccount.controller.create=false \
  --set serviceAccount.controller.name=efs-csi-controller-sa
```

- Annotate IRSA and then rollout restart controllers
```
$ kubectl annotate serviceaccount -n kube-system efs-csi-controller-sa eks.amazonaws.com/role-arn=arn:aws:iam::123456789012:role/eks-efs-csi-sa                                        
serviceaccount/efs-csi-controller-sa annotated

$ kubectl rollout restart deployment -n kube-system efs-csi-controller                                                                                                                     
deployment.apps/efs-csi-controller restarted

# Check IRSA work
$ kubectl exec -n kube-system efs-csi-controller-6b44dc5977-2w2d6 -- env |grep AWS
AWS_ROLE_ARN=arn:aws:iam::123456789012:role/eks-efs-csi-sa
AWS_WEB_IDENTITY_TOKEN_FILE=/var/run/secrets/eks.amazonaws.com/serviceaccount/token
AWS_DEFAULT_REGION=ap-northeast-2
AWS_REGION=ap-northeast-2
```

- Check CSI
```
[ec2-user@eks-ctl ~]$ kubectl get pod -n kube-system |grep csi
efs-csi-controller-6b44dc5977-2w2d6             3/3     Running   0          18h
efs-csi-controller-6b44dc5977-qtcc6             3/3     Running   0          159m
efs-csi-node-4rn69                              3/3     Running   0          17h
efs-csi-node-6zdwg                              3/3     Running   0          161m
```

- For understanding IAM Role for service account, [Go to](https://dev.to/vumdao/using-iam-service-account-instead-of-instance-profile-for-eks-pods-262p)

## 🚀 **Create storageclass, pv and pvc - Dynamic Provisioning** <a name="Create-storageclass,-pv-and-pvc---Dynamic-Provisioning"></a>

{% details - storageclass.yaml %}
```
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-92107410
  directoryPerms: "700"
  gidRangeStart: "1000"
  gidRangeEnd: "2000"
  basePath: "/data"
```

- provisioningMode - The type of volume to be provisioned by efs. Currently, only access point based provisioning is supported efs-ap.
- fileSystemId - The file system under which Access Point is created.
- directoryPerms - Directory Permissions of the root directory created by Access Point.
- gidRangeStart (Optional) - Starting range of Posix Group ID to be applied onto the root directory of the access point. Default value is 50000.
- gidRangeEnd (Optional) - Ending range of Posix Group ID. Default value is 7000000.
- basePath (Optional) - Path on the file system under which access point root directory is created. If path is not provided, access points root directory are created under the root of the file system.

```
apiVersion: v1
kind: Namespace
metadata:
  name: storage
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: efs-claim
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: efs-writer
  namespace: storage
spec:
  containers:
    - name: efs-writer
      image: centos
      command: ["/bin/sh"]
      args: ["-c", "while true; do echo $(date -u) >> /data/out; sleep 5; done"]
      volumeMounts:
        - name: persistent-storage
          mountPath: /data
  volumes:
    - name: persistent-storage
      persistentVolumeClaim:
        claimName: efs-claim
---
apiVersion: v1
kind: Pod
metadata:
  name: efs-reader
  namespace: storage
spec:
  containers:
  - name: efs-reader
    image: busybox
    command: ["/bin/sh"]
    args: ["-c", "while true; do sleep 5; done"]
    volumeMounts:
    - name: efs-pvc
      mountPath: /data
  volumes:
  - name: efs-pvc
    persistentVolumeClaim:
      claimName: efs-claim
```
{% enddetails %}

- Apply and check
```
$ kubectl get sc efs-sc
NAME     PROVISIONER       RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
efs-sc   efs.csi.aws.com   Delete          Immediate           false                  2m54s

$ kubectl get pvc
NAME        STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
efs-claim   Bound    pvc-2a7e818f-c513-4b79-a47e-5b9c1a7d26a9   1Gi        RWX            efs-sc         2m32s
```

- Dynamic Access point is created
![Dynamic](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/efs-csi/img/dynamic.png?raw=true)

- Check read/write pod and ensure pods are located to different nodes to demonstrate EFS strongly
```
$ kubectl get pod -n storage -owide
NAME         READY   STATUS    RESTARTS   AGE    IP            NODE                                              NOMINATED NODE   READINESS GATES
efs-reader   1/1     Running   0          14s    10.3.147.2    ip-10-3-141-203.ap-northeast-2.compute.internal   <none>           <none>
efs-writer   1/1     Running   0          116s   10.3.235.47   ip-10-3-254-49.ap-northeast-2.compute.internal    <none>           <none>

$ kubectl exec efs-reader -n storage -- cat /data/out | head -n 2
Fri Jul 16 03:54:49 UTC 2021
Fri Jul 16 03:54:54 UTC 2021

$ kubectl exec efs-writer -n storage -- cat /data/out | head -n 2
Fri Jul 16 03:54:49 UTC 2021
Fri Jul 16 03:54:54 UTC 2021
```

- Ref: https://github.com/kubernetes-sigs/aws-efs-csi-driver/blob/master/examples/kubernetes/dynamic_provisioning/README.md

## 🚀 **Create storageclass, pv and pvc - EFS Access Points** <a name="Create-storageclass,-pv-and-pvc---EFS-Access-Points"></a>

- First create access point using AWS CLI or AWS console, and then get the Access point ID and EFS ID to pass to `volumeHandle: fs-a13cb9c1::fsap-0f9e7568af65cc5bd`
![Access point](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/efs-csi/img/access-point.png?raw=true)

{% details efs-ap.yaml %}
```
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
---
apiVersion: v1
kind: Namespace
metadata:
  name: storage
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: efs-pv
spec:
  capacity:
    storage: 1Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: efs-sc
  csi:
    driver: efs.csi.aws.com
    volumeHandle: fs-a13cb9c1::fsap-0f9e7568af65cc5bd
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: efs-claim
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: efs-writer
  namespace: storage
spec:
  containers:
    - name: efs-writer
      image: centos
      command: ["/bin/sh"]
      args: ["-c", "while true; do echo $(date -u) >> /data/out; sleep 5; done"]
      volumeMounts:
        - name: persistent-storage
          mountPath: /data
  volumes:
    - name: persistent-storage
      persistentVolumeClaim:
        claimName: efs-claim
---
apiVersion: v1
kind: Pod
metadata:
  name: efs-reader
  namespace: storage
spec:
  containers:
  - name: efs-reader
    image: busybox
    command: ["/bin/sh"]
    args: ["-c", "while true; do sleep 5; done"]
    volumeMounts:
    - name: efs-pvc
      mountPath: /data
  volumes:
  - name: efs-pvc
    persistentVolumeClaim:
      claimName: efs-claim
```
{% enddetails %}

- Apply the yaml file
```
$ kubectl get pvc
NAME        STATUS   VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   AGE
efs-claim   Bound    efs-pv   1Gi        RWX            efs-sc         12h

$ kubectl get pv
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                                   STORAGECLASS   REASON   AGE
efs-pv                                     1Gi        RWX            Retain           Bound    storage/efs-claim                       efs-sc                  12h

$ kubectl get pod
NAME         READY   STATUS    RESTARTS   AGE
efs-reader   1/1     Running   0          104s
efs-writer   1/1     Running   0          104s

$ kubectl exec efs-reader -- cat /data/out
Tue Jul 13 05:33:43 UTC 2021
Tue Jul 13 05:33:48 UTC 2021
```

## 🚀 **How to troubleshoot** <a name="How-to-troubleshoot"></a>
- Failed case if we input wrong EFS ID
```
$ kubectl logs -n kube-system -f --tail=100 efs-csi-controller-6b44dc5977-2w2d6 csi-provisioner
E0713 05:50:20.080089       1 event.go:264] Server rejected event '&v1.Event{TypeMeta:v1.TypeMeta{Kind:"", APIVersion:""}, ObjectMeta:v1.ObjectMeta{Name:"efs-claim.1691439f81a95683", GenerateName:"", Namespace:"storage", SelfLink:"", UID:"", ResourceVersion:"19553746", Generation:0, CreationTimestamp:v1.Time{Time:time.Time{wall:0x0, ext:0, loc:(*time.Location)(nil)}}, DeletionTimestamp:(*v1.Time)(nil), DeletionGracePeriodSeconds:(*int64)(nil), Labels:map[string]string(nil), Annotations:map[string]string(nil), OwnerReferences:[]v1.OwnerReference(nil), Finalizers:[]string(nil), ClusterName:"", ManagedFields:[]v1.ManagedFieldsEntry(nil)}, InvolvedObject:v1.ObjectReference{Kind:"PersistentVolumeClaim", Namespace:"storage", Name:"efs-claim", UID:"4c51f212-c828-4a66-a297-31f8d9ebe255", APIVersion:"v1", ResourceVersion:"19553744", FieldPath:""}, Reason:"Provisioning", Message:"External provisioner is provisioning volume for claim \"storage/efs-claim\"", Source:v1.EventSource{Component:"efs.csi.aws.com_ip-10-3-179-184.ap-northeast-2.compute.internal_f7376ef0-1668-4be9-90b5-d18298dc677e", Host:""}, FirstTimestamp:v1.Time{Time:time.Time{wall:0x0, ext:63761752092, loc:(*time.Location)(0x26270e0)}}, LastTimestamp:v1.Time{Time:time.Time{wall:0xc033684704a729f2, ext:68986915168904, loc:(*time.Location)(0x26270e0)}}, Count:8, Type:"Normal", EventTime:v1.MicroTime{Time:time.Time{wall:0x0, ext:0, loc:(*time.Location)(nil)}}, Series:(*v1.EventSeries)(nil), Action:"", Related:(*v1.ObjectReference)(nil), ReportingController:"", ReportingInstance:""}': 'events "efs-claim.1691439f81a95683" is forbidden: User "system:serviceaccount:kube-system:efs-csi-controller-sa" cannot patch resource "events" in API group "" in the namespace "storage"' (will not retry!)
I0713 05:50:20.111457       1 controller.go:1099] Final error received, removing PVC 4c51f212-c828-4a66-a297-31f8d9ebe255 from claims in progress
W0713 05:50:20.111494       1 controller.go:958] Retrying syncing claim "4c51f212-c828-4a66-a297-31f8d9ebe255", failure 7
E0713 05:50:20.111512       1 controller.go:981] error syncing claim "4c51f212-c828-4a66-a297-31f8d9ebe255": failed to provision volume with StorageClass "efs-sc": rpc error: code = InvalidArgument desc = File System does not exist: Resource was not found
I0713 05:50:20.111582       1 event.go:282] Event(v1.ObjectReference{Kind:"PersistentVolumeClaim", Namespace:"storage", Name:"efs-claim", UID:"4c51f212-c828-4a66-a297-31f8d9ebe255", APIVersion:"v1", ResourceVersion:"19553744", FieldPath:""}): type: 'Warning' reason: 'ProvisioningFailed' failed to provision volume with StorageClass "efs-sc": rpc error: code = InvalidArgument desc = File System does not exist: Resource was not found
```

- Success
```
$ kubectl logs -n kube-system -f --tail=100 efs-csi-controller-6b44dc5977-2w2d6 csi-provisioner
I0713 05:53:59.261135       1 controller.go:1332] provision "storage/efs-claim" class "efs-sc": started
I0713 05:53:59.261719       1 event.go:282] Event(v1.ObjectReference{Kind:"PersistentVolumeClaim", Namespace:"storage", Name:"efs-claim", UID:"2a7e818f-c513-4b79-a47e-5b9c1a7d26a9", APIVersion:"v1", ResourceVersion:"19555274", FieldPath:""}): type: 'Normal' reason: 'Provisioning' External provisioner is provisioning volume for claim "storage/efs-claim"
I0713 05:53:59.385168       1 controller.go:838] successfully created PV pvc-2a7e818f-c513-4b79-a47e-5b9c1a7d26a9 for PVC efs-claim and csi volume name fs-a13cb9c1::fsap-0b047e3528a6856ca
I0713 05:53:59.385219       1 controller.go:1439] provision "storage/efs-claim" class "efs-sc": volume "pvc-2a7e818f-c513-4b79-a47e-5b9c1a7d26a9" provisioned
I0713 05:53:59.385244       1 controller.go:1456] provision "storage/efs-claim" class "efs-sc": succeeded
I0713 05:53:59.393941       1 event.go:282] Event(v1.ObjectReference{Kind:"PersistentVolumeClaim", Namespace:"storage", Name:"efs-claim", UID:"2a7e818f-c513-4b79-a47e-5b9c1a7d26a9", APIVersion:"v1", ResourceVersion:"19555274", FieldPath:""}): type: 'Normal' reason: 'ProvisioningSucceeded' Successfully provisioned volume pvc-2a7e818f-c513-4b79-a47e-5b9c1a7d26a9
```

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
