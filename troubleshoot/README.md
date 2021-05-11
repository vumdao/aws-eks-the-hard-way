<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Add Taints To AWS EKS Cluster And Trouble Shooting" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/troubleshoot/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>Add Taints To AWS EKS Cluster And Trouble Shooting</b></div>
</h1>

### **Taints and Tolerations is used to ensure the node should not accept any pods that do not tolerate the taints. How to add taints to AWS EKS node group? This blog will show you how and the way of trouble shooting**

---

## What’s In This Document
- [How to taint eks node group](#-How-to-taint-eks-node-group)
- [Understand kubelet systemd service in the eks node](#-Understand-kubelet-systemd-service-in-the-eks-node)
- [Facing some issues](#-Facing-some-issues)
- [Conclusion](#-Conclusion)

---

### 🚀 **[How to taint eks node group](#-How-to-taint-eks-node-group)**
- Use `BootstrapArguments` in `Parameters` of cloudformation to input to `kubelet` arguments
![Alt-Text](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/troubleshoot/img/cfn.png?raw=true)

### 🚀 **[Understand kubelet systemd service in the eks node](#-Understand-kubelet-systemd-service-in-the-eks-node)**
- Enter to the worker and Check kubelet status. We see that kubelet service is started with option `--register-with-taints=dedicated=test:NoSchedule` which is input from `/etc/systemd/system/kubelet.service.d/30-kubelet-extra-args.conf`.

```
[root@ip-17-1-5-1 ec2-user]# systemctl status kubelet -l
● kubelet.service - Kubernetes Kubelet
   Loaded: loaded (/etc/systemd/system/kubelet.service; enabled; vendor preset: disabled)
  Drop-In: /etc/systemd/system/kubelet.service.d
           └─10-kubelet-args.conf, 30-kubelet-extra-args.conf
   Active: active (running) since Tue 2021-05-11 07:20:42 UTC; 1h 2min ago
     Docs: https://github.com/kubernetes/kubernetes
  Process: 4128 ExecStartPre=/sbin/iptables -P FORWARD ACCEPT -w 5 (code=exited, status=0/SUCCESS)
 Main PID: 4139 (kubelet)
    Tasks: 16
   Memory: 141.5M
   CGroup: /system.slice/kubelet.service
           └─4139 /usr/bin/kubelet --cloud-provider aws --config /etc/kubernetes/kubelet/kubelet-config.json --kubeconfig /var/lib/kubelet/kubeconfig --container-runtime docker --network-plugin cni --node-ip=17.1.5.1 --pod-infra-container-image=0123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/eks/pause:3.1-eksbuild.1 --node-labels=role=test --register-with-taints=dedicated=test:NoSchedule
```

```
[root@ip-17-1-5-1 ec2-user]# cat /etc/systemd/system/kubelet.service.d/30-kubelet-extra-args.conf
[Service]
Environment='KUBELET_EXTRA_ARGS=--node-labels=role=test --register-with-taints=dedicated=test:NoSchedule'
```

- The `30-kubelet-extra-args.conf` file is created by `/etc/eks/bootstrap.sh`

```
if [[ -n "$KUBELET_EXTRA_ARGS" ]]; then
    cat <<EOF > /etc/systemd/system/kubelet.service.d/30-kubelet-extra-args.conf
[Service]
Environment='KUBELET_EXTRA_ARGS=$KUBELET_EXTRA_ARGS'
EOF
fi
```

- Check the `/var/log/messages` to understand how systemD start the `kubelet` service.

```
May 11 07:20:40 ip-17-1-5-1 systemd: Started Apply the settings specified in cloud-config.
May 11 07:20:40 ip-17-1-5-1 systemd: Starting Execute cloud user/final scripts...
May 11 07:20:40 ip-17-1-5-1 cloud-init: Cloud-init v. 19.3-3.amzn2 running 'modules:final' at Tue, 11 May 2021 07:20:40 +0000. Up 28.99 seconds.
May 11 07:20:40 ip-17-1-5-1 cloud-init: + /etc/eks/bootstrap.sh eks-cluster --kubelet-extra-args '--node-labels=role=test --register-with-taints=dedicated=test:NoSchedule'
May 11 07:20:40 ip-17-1-5-1 cloud-init: % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
May 11 07:20:40 ip-17-1-5-1 cloud-init: Dload  Upload   Total   Spent    Left  Speed
May 11 07:20:40 ip-17-1-5-1 cloud-init: 0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0#015100    56  100    56    0     0   5600      0 --:--:-- --:--:-- --:--:--  5600
May 11 07:20:41 ip-17-1-5-1 dhclient[2969]: XMT: Solicit on eth0, interval 15840ms.
May 11 07:20:42 ip-17-1-5-1 systemd: Reloading.
May 11 07:20:42 ip-17-1-5-1 systemd: Reloading.
May 11 07:20:42 ip-17-1-5-1 cloud-init: Created symlink from /etc/systemd/system/multi-user.target.wants/kubelet.service to /etc/systemd/system/kubelet.service.
May 11 07:20:42 ip-17-1-5-1 systemd: Starting Kubernetes Kubelet...
May 11 07:20:42 ip-17-1-5-1 systemd: Started Kubernetes Kubelet.
May 11 07:20:42 ip-17-1-5-1 cloud-init: + /opt/aws/bin/cfn-signal --exit-code 0 --stack eks-cluster-test --resource NodeGroup --region ap-northeast-1
May 11 07:20:42 ip-17-1-5-1 systemd: Started Kubernetes systemd probe.
May 11 07:20:42 ip-17-1-5-1 systemd: Starting Kubernetes systemd probe.
May 11 07:20:42 ip-17-1-5-1 kubelet: I0511 07:20:42.909859    4139 server.go:417] Version: v1.18.8-eks-7c9bda
May 11 07:20:42 ip-17-1-5-1 kubelet: W0511 07:20:42.910542    4139 plugins.go:115] WARNING: aws built-in cloud provider is now deprecated. The AWS provider is deprecated and will be removed in a future release
May 11 07:20:42 ip-17-1-5-1 kubelet: I0511 07:20:42.914985    4139 aws.go:1241] Zone not specified in configuration file; querying AWS metadata service
May 11 07:20:42 ip-17-1-5-1 kubelet: I0511 07:20:42.919112    4139 aws.go:1281] Building AWS cloudprovider
```

- `kubelet` has dependency on `cloud-init` service which run `/etc/eks/bootstrap.sh` with args from cloudformation parameters.

### 🚀 **[Facing some issues](#-Facing-some-issues)**
- When apply taint for the eks node I met two issues: typo and missing double `'`

**1. Typo which caused the bash script failed**
![Alt-Text](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/troubleshoot/img/typo.png?raw=true)

```
May 11 04:38:50 ip-172-10-21-203 cloud-init: Cloud-init v. 19.3-3.amzn2 running 'modules:final' at Tue, 11 May 2021 04:38:50 +0000. Up 43.12 seconds.
May 11 04:38:50 ip-172-10-21-203 cloud-init: /var/lib/cloud/instance/scripts/part-001: line 3: unexpected EOF while looking for matching `''
May 11 04:38:50 ip-172-10-21-203 cloud-init: /var/lib/cloud/instance/scripts/part-001: line 8: syntax error: unexpected end of file
May 11 04:38:50 ip-172-10-21-203 cloud-init: May 11 04:38:50 cloud-init[4080]: util.py[WARNING]: Failed running /var/lib/cloud/instance/scripts/part-001 [2]
```

**2. Missing double `'`**
- The `bootstrap.sh` get `KUBELET_EXTRA_ARGS` as second argument so for more than one option, all must ne in double `'`

```
        --kubelet-extra-args)
            KUBELET_EXTRA_ARGS=$2
```

### 🚀 **[Conclusion](#-Conclusion)**
- Use combine  of`node affinity`, `taints` and `toleration` to ensure the pod of specific service stays in correct node and prevent others.
- When starting an EKS node (worker), it uses cloud-init service to run eks bootstrap script which helps to config the extra arguments of kubelet service to startup.
- Using systemD services ensure the order of depenent services.

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