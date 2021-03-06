<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Understand Pods communication" src="images/cover.jpg" width="800" />
  </a>
</p>
<h1 align="center">
  <div><b>Understand Pods communication</b></div>
</h1>

## Abstract
- When create new Auto scaling group, there were three issues that I faced:
    1. `kubelet` failed to start due to error listing AWS instances from metadata
    2. IPAM failed to start (no secondary IP addresses in the ASG nodes)
    3. Pods were not able to connect public URL although outbound allows all traffic to 0.0.0.0
    4. Outbound is matter for L-IPAMD (IP Address Manager systemD service)

- Let's figure out why

## Table Of Contents
 * [Security groups for your VPC](#Security-groups-for-your-VPC)
 * [Pod networking (CNI)](#Pod-networking-(CNI))
 * [Understand CoreDNS](#Understand-CoreDNS)
 * [EKS kubelet service need outbound rule?](#EKS-kubelet-service-need-outbound-rule?)
 * [Conclusion](#Conclusion)

---

## 🚀 **Security groups for your VPC** <a name="Security-groups-for-your-VPC"></a>
- This is one of important things for Pod communications

- [Security groups for your VPC](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html)

- Security groups are stateful — if you send a request from your instance, the response traffic for that request is allowed to flow in regardless of inbound security group rules. Responses to allowed inbound traffic are allowed to flow out, regardless of outbound rules. 

- **Instances** associated with a security group can't talk to each other unless you add rules allowing the traffic (exception: the default security group has these rules by default).

<img src="images/sg-default.png" width="1100" />

- By default, when you create a network interface, it's associated with the default security group for the VPC, unless you specify a different security group

- When you specify a security group as the source or destination for a rule, the rule affects all instances that are associated with the security group. Incoming traffic is allowed based on the private IP addresses of the instances that are associated with the source security group (and not the public IP or Elastic IP addresses).

- When you specify a security group as the source for a rule, traffic is allowed from the network interfaces that are associated with the source security group for the specified protocol and port. Incoming traffic is allowed based on the private IP addresses of the network interfaces that are associated with the source security group (and not the public IP or Elastic IP addresses).

## 🚀 **Pod networking (CNI)** <a name="Security-groups-for-your-VPC"></a>
- [Pod networking (CNI)](https://docs.aws.amazon.com/eks/latest/userguide/pod-networking.html)
- Amazon EKS supports native VPC networking with the Amazon VPC Container Network Interface (CNI) plugin for Kubernetes. This plugin assigns an IP address from your VPC to each pod.
- When you create an Amazon EKS node, it has one network interface. All Amazon EC2 instance types support more than one network interface. The network interface attached to the instance when the instance is created is called the primary network interface. Any additional network interface attached to the instance is called a secondary network interface. Each network interface can be assigned multiple private IP addresses. One of the private IP addresses is the primary IP address, whereas all other addresses assigned to the network interface are secondary IP addresses.

- The Amazon VPC Container Network Interface (CNI) plugin for Kubernetes is deployed with each of your Amazon EC2 nodes in a Daemonset with the name aws-node. The plugin consists of two primary components:
    - [L-IPAM](https://github.com/aws/amazon-vpc-cni-k8s/blob/master/docs/cni-proposal.md#local-ip-address-manager-l-ipam) daemon
        - When a worker node first joins the cluster, there is only 1 ENI along with all of its addresses in the ENI. Without any configuration, ipamd always try to keep one extra ENI.
        - L-IPAM is responsible for creating network interfaces and attaching the network interfaces to Amazon EC2 instances, assigning secondary IP addresses to network interfaces, and maintaining a warm pool of IP addresses on each node for assignment to Kubernetes pods when they are scheduled. When the number of pods running on the node exceeds the number of addresses that can be assigned to a single network interface, the plugin starts allocating a new network interface, as long as the maximum number of network interfaces for the instance aren't already attached.
        - L-IPAM requires the IAM policy which is AWS managed policy [AmazonEKS_CNI_Policy](https://console.aws.amazon.com/iam/home#/policies/arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy%24jsonEditor)
        - Each pod that you deploy is assigned one secondary private IP address from one of the network interfaces attached to the instance

    - CNI plugin – Responsible for wiring the host network (for example, configuring the network interfaces and virtual Ethernet pairs) and adding the correct network interface to the pod namespace.


- Check inside a host
```
[root@ip-172-10-12-55 ec2-user]# ip route show
default via 172.10.12.1 dev eth0
169.254.169.254 dev eth0
172.10.12.0/24 dev eth0 proto kernel scope link src 172.10.12.55
172.10.12.17 dev enib6ba4ad7e6d scope link
172.10.12.175 dev eni65cfa2c6d07 scope link
172.10.12.227 dev enib1effc0b0ce scope link
172.10.12.247 dev eni7b8c0d17d54 scope link
```

- Starting IPAM daemon
    - IPAM failed to start
        ```
        root@ctl:/var/snap/amazon-ssm-agent/4047# kubectl logs -f -n kube-system aws-node-m9jg6
        Copying portmap binary ... Starting IPAM daemon in the background ... ok.
        Checking for IPAM connectivity ...  failed.
        Timed out waiting for IPAM daemon to start:
        ```

    - IPAM started successfully
        ```
        root@ctl:/var/snap/amazon-ssm-agent/4047# kf logs -n kube-system aws-node-x2dh4
        {"level":"info","ts":"2021-10-12T17:00:51.749Z","caller":"entrypoint.sh","msg":"Install CNI binary.."}
        {"level":"info","ts":"2021-10-12T17:00:51.772Z","caller":"entrypoint.sh","msg":"Starting IPAM daemon in the background ... "}
        {"level":"info","ts":"2021-10-12T17:00:51.773Z","caller":"entrypoint.sh","msg":"Checking for IPAM connectivity ... "}
        {"level":"info","ts":"2021-10-12T17:00:53.814Z","caller":"entrypoint.sh","msg":"Copying config file ... "}
        {"level":"info","ts":"2021-10-12T17:00:53.819Z","caller":"entrypoint.sh","msg":"Successfully copied CNI plugin binary and config file."}
        {"level":"info","ts":"2021-10-12T17:00:53.823Z","caller":"entrypoint.sh","msg":"Foregrounding IPAM daemon ..."}
        ```

- Inter-process communication between CNI-plugin and L-IPAM

<img src="images/ipam.png" width="1100"/>

## 🚀 **Understand CoreDNS** <a name="Understand-CoreDNS"></a>
- How Pod resolve service DNS and resolve pubilic domains?

- [CoreDNS](https://coredns.io/) is a flexible, extensible DNS server that can serve as the Kubernetes cluster DNS.

- In large scale Kubernetes clusters, CoreDNS’s memory usage is predominantly affected by the number of Pods and Services in the cluster. Other factors include the size of the filled DNS answer cache, and the rate of queries received (QPS) per CoreDNS instance.

- There are two different ports: 5300 and 53. Internally, each of these ports will result in a dnsserver.Server

<img src="images/coredns-query.png" width="1100"/>

- Create pod to test coredns
    <details>
    <summary>dnsutil.yaml</summary>

    ```
    apiVersion: v1
    kind: Pod
    metadata:
    name: dnsutils
    namespace: airflow
    spec:
    containers:
    - name: dnsutils
        image: gcr.io/kubernetes-e2e-test-images/dnsutils:1.3
        command:
        - sleep
        - "3600"
        imagePullPolicy: IfNotPresent
    restartPolicy: Always
    affinity:
        nodeAffinity:
            requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
                - matchExpressions:
                - key: type
                    operator: In
                    values:
                    - airflow-stateless
    tolerations:
        - key: 'dedicated'
            operator: 'Equal'
            value: 'airflow'
            effect: 'NoSchedule'
    ```

    </details>

    - Access pod and run host
        ```
        root@ctl:/tmp/airflow# kf exec -it dnsutils -- sh
        / # # Before allow traffic of this node to other ones (especially the ones host coredns pod) 
        / # host airflow-web
        ;; connection timed out; no servers could be reached

        /# # After allow traffic
        / # host airflow-web
        airflow-web.airflow.svc.cluster.local has address 172.20.21.163
        ```
    
    - Further failed to resolve DNS if the pod is not allowed traffic to coredns
        ```
        root@us-prod-ctl:/tmp/airflow# kf logs -f airflow-scheduler-858854c8b8-6vdb4 dags-git-clone
        INFO: detected pid 1, running init handler
        I1013 17:30:23.795367      13 main.go:430]  "level"=0 "msg"="starting up"  "args"=["/git-sync"] "pid"=13
        I1013 17:30:23.795483      13 main.go:694]  "level"=0 "msg"="cloning repo"  "origin"="https://gitlab.cloudopz.co/airflow.git" "path"="/dags"
        E1013 17:30:43.866130      13 main.go:455]  "msg"="too many failures, aborting" "error"="Run(git clone --no-checkout -b us-master --depth 1 https://gitlab.cloudopz.co/airflow.git /dags): exit status 128:
        { stdout: \"\", stderr: \"Cloning into '/dags'...\\nfatal: unable to access 'https://gitlab.cloudopz.co/airflow.git/': Could not resolve host: gitlab.cloudopz.co\\n\" }"  "failCount"=0
        ```

    - CoreDNS `i/o timeout`
        ```
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.us-prod.zone. A: read udp 10.0.9.179:51594->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:48875->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.us-prod.zone. A: read udp 10.0.9.179:60062->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:59339->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:57500->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.us-prod.zone. A: read udp 10.0.9.179:33370->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:60125->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. A: read udp 10.0.9.179:46843->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:58067->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. A: read udp 10.0.9.179:44265->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.ec2.internal. A: read udp 10.0.9.179:47068->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.us-prod.zone. A: read udp 10.0.9.179:39342->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. A: read udp 10.0.9.179:59117->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:55960->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. CNAME: read udp 10.0.9.179:50490->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.ec2.internal. A: read udp 10.0.9.179:50588->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.us-prod.zone. A: read udp 10.0.9.179:53165->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 sqs.us-east-1.amazonaws.com.us-prod.zone. A: read udp 10.0.9.179:40751->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.ec2.internal. A: read udp 10.0.9.179:55001->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.ec2.internal. CNAME: read udp 10.0.9.179:50504->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 dynamodb.ap-southeast-1.amazonaws.com. A: read udp 10.0.9.179:53393->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis. A: read udp 10.0.9.179:46872->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:45351->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. A: read udp 10.0.9.179:58471->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis. CNAME: read udp 10.0.9.179:60881->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 airflow-pgbouncer.airflow.svc.cluster.local.ec2.internal. A: read udp 10.0.9.179:57814->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. AAAA: read udp 10.0.9.179:58696->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 redis.us-prod.zone. A: read udp 10.0.9.179:53841->10.0.0.2:53: i/o timeout
        [ERROR] plugin/errors: 2 kafka32.default.svc.cluster.local.us-prod.zone. A: read udp 10.0.9.179:33357->10.0.0.2:53: i/o timeout
        ```

        - Common issues:
            - CoreDNS not being able to query kubernetes apiserver to resolve internal names
            - CoreDNS not being able to forward the queries to internal DNS (10.0.0.2:53: i/o timeout)

## 🚀 **EKS kubelet service need outbound rule?** <a name="EKS-kubelet-service-need-outbound-rule?"></a>
- The EC2 `outbound` rule is often open all traffics to `0.0.0.0/0`, but in some cases, it is not.

- `kubelet` with `aws` provider will try to get instance metadata at first start by using the URL `https://ec2.us-east-1.amazonaws.com` (base on the region)
- Let see if we not open outbound to port `443`, `kubelet` failed to start
    ```
    Oct 15 15:40:52 ip-10-0-13-157 systemd: Started Kubernetes systemd probe.
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: I1015 15:40:52.645085    3111 mount_linux.go:178] Detected OS with systemd
    Oct 15 15:40:52 ip-10-0-13-157 systemd: Started Kubernetes systemd probe.
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: I1015 15:40:52.651960    3111 subpath_mount_linux.go:157] Detected OS with systemd
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: I1015 15:40:52.653042    3111 server.go:418] Version: v1.18.20-eks-c9f1ce
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: I1015 15:40:52.653137    3111 feature_gate.go:243] feature gates: &{map[RotateKubeletServerCertificate:true]}
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: I1015 15:40:52.653214    3111 feature_gate.go:243] feature gates: &{map[RotateKubeletServerCertificate:true]}
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: W1015 15:40:52.655057    3111 plugins.go:115] WARNING: aws built-in cloud provider is now deprecated. The AWS provider is deprecated and will be removed in a future release
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: I1015 15:40:52.692989    3111 aws.go:1249] Zone not specified in configuration file; querying AWS metadata service
    Oct 15 15:40:52 ip-10-0-13-157 kubelet: I1015 15:40:52.746474    3111 aws.go:1289] Building AWS cloudprovider
    Oct 15 15:44:58 ip-10-0-13-157 kubelet: F1015 15:44:58.742363    3378 server.go:274] failed to run Kubelet: could not init cloud provider "aws": error finding instance i-0f4d8d3be0bc8bb79: "error listing AWS instances: \"RequestError: send request failed\\ncaused by: Post https://ec2.us-east-1.amazonaws.com/: dial tcp 52.46.150.88:443: i/o timeout\""
    Oct 15 15:44:58 ip-10-0-13-157 systemd: kubelet.service: main process exited, code=exited, status=255/n/a
    Oct 15 15:44:58 ip-10-0-13-157 systemd: Unit kubelet.service entered failed state.
    Oct 15 15:44:58 ip-10-0-13-157 systemd: kubelet.service failed.
    Oct 15 15:45:03 ip-10-0-13-157 systemd: kubelet.service holdoff time over, scheduling restart.
    Oct 15 15:45:03 ip-10-0-13-157 systemd: Stopped Kubernetes Kubelet.
    ```

- The suceess
    ```
    Oct 15 15:55:32 ip-10-0-13-157 systemd: Starting Kubernetes Kubelet...
    Oct 15 15:55:32 ip-10-0-13-157 systemd: Started Kubernetes Kubelet.
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.459182    3953 server.go:418] Version: v1.18.20-eks-c9f1ce
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.459263    3953 feature_gate.go:243] feature gates: &{map[RotateKubeletServerCertificate:true]}
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.459371    3953 feature_gate.go:243] feature gates: &{map[RotateKubeletServerCertificate:true]}
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: W1015 15:55:32.459526    3953 plugins.go:115] WARNING: aws built-in cloud provider is now deprecated. The AWS provider is deprecated and will be removed in a future release
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.459943    3953 aws.go:1249] Zone not specified in configuration file; querying AWS metadata service
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.461821    3953 aws.go:1289] Building AWS cloudprovider
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.698313    3953 tags.go:79] AWS cloud filtering on ClusterID: us-p2
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.698356    3953 server.go:540] Successfully initialized cloud provider: "aws" from the config file: ""
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.698366    3953 server.go:964] cloud provider determined current node name to be ip-10-0-13-157.ec2.internal
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.721413    3953 dynamic_cafile_content.go:129] Loaded a new CA Bundle and Verifier for "client-ca-bundle::/etc/kubernetes/pki/ca.crt"
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.721533    3953 dynamic_cafile_content.go:167] Starting client-ca-bundle::/etc/kubernetes/pki/ca.crt
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.723631    3953 manager.go:146] cAdvisor running in container: "/sys/fs/cgroup/cpu,cpuacct/system.slice/kubelet.service"
    Oct 15 15:55:32 ip-10-0-13-157 kubelet: I1015 15:55:32.808649    3953 fs.go:125] Filesystem UUIDs: map[a2d6f56b-f4f4-4d1a-8df1-9b20ffb3be14:/dev/nvme0n1p1]
    ```

## 🚀 **Conclusion** <a name="Conclusion"></a>
- In general, solution from the two original issues are:
    1. IAM Worker role need permission to create ENI, assign IP addresses
    2. Pod between nodes between autoscaling groups need to allow traffics in their network interfaces which are assigned to Auto-scaling groups (ASG) SGs

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