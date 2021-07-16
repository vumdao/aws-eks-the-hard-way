<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="AWS EKS With Amazon EC2 Spot Instances" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/spot-instance/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>AWS EKS With Amazon EC2 Spot Instances</b></div>
</h1>

## Abstract
This post provides an overview of Amazon EC2 Spot Instances, as well as best practices for using them on AWS EKS effectively

## Table Of Contents
 * [What to know about spot instances?](#What-to-know-about-spot-instances?)
 * [How to Launch Spot Instances](#How-to-Launch-Spot-Instances?)
 * [Spot Instance Best Practices](#Spot-Instance-Best-Practices)
 * [Solution](#Solution)
 * [Conclusion](#-Conclusion)

---

## 🚀 **What to know about spot instances?** <a name="What-to-know-about-spot-instances?"></a>
![Alt-Test](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/spot-instance/img/spot_intro.png?raw=true)

## 🚀 **How to Launch Spot Instances** <a name="How-to-Launch-Spot-Instances?"></a>
- The most recommended service for launching Spot Instances is Amazon EC2 Auto Scaling especially Amazon EKS node group

- If you require more flexibility, have built your own instance launch workflows, or want to control individual aspects of the instance launches or the scaling mechanisms, you can use EC2 Fleet in Instant mode.
![Alt-text](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/spot-instance/img/launch_spot.png?raw=true)

## 🚀 **Spot Instance Best Practices** <a name="Spot-Instance-Best-Practices"></a>
- Flexible about instance types, for example, my applications almost run in java and they require much memory so I choose R5 type and its family could be r5.xlarge, r5a.xlarge, etc.
- Flexible of Availability Zone, here I give the case of using EKS node group.
    - Configure multiple node groups, scope each group to a single Availability Zone, and enable the `--balance-similar-node-groups` feature in [cluster autoscaler](https://dev.to/awscommunity-asean/kubernetes-cluster-autoscaler-with-irsa-3bg5) so that we will have at least each node in different zones and guarentee the HA. Especially when the PVC is attached to an AZ, the pod need to be start on a spot instance in same zone.

    eg. Create two node groups in different AZ using AWS cdk

    ```
            self.eks_cluster.add_nodegroup_capacity(
            id="EksNodeGroupStateless",
            capacity_type=eks.CapacityType.SPOT,
            desired_size=1,
            disk_size=20,
            instance_types=[ec2.InstanceType("r5a.xlarge"), ec2.InstanceType("r5.xlarge")],
            labels={'role': 'worker', 'type': 'stateless'},
            max_size=2,
            min_size=1,
            nodegroup_name='eks-node-group',
            node_role=worker_role,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE, availability_zones=['ap-northeast-2a'])
            )

            self.eks_cluster.add_nodegroup_capacity(
            id="EksNodeGroupStateful",
            capacity_type=eks.CapacityType.SPOT,
            desired_size=1,
            disk_size=20,
            instance_types=[ec2.InstanceType("r5a.xlarge"), ec2.InstanceType("r5.xlarge")],
            labels={'role': 'worker', 'type': 'stateful'},
            max_size=2,
            min_size=1,
            nodegroup_name='eks-node-group-stateful',
            node_role=worker_role,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE, availability_zones=['ap-northeast-2b'])
            )
    ```

- Prepare individual instances for interruptions: The best way for you to gracefully handle Spot Instance interruptions is to architect your application to be fault-tolerant, in EKS we can use HPA to ensure the number of available pods if one node down, and use cluster autoscaler to request new node.

- Max price: We recommend that you do not specify a maximum price, but rather let the maximum price default to the On-Demand price. A high maximum price does not increase your chances of launching a Spot Instance. See [EC2 Spot pricing model](https://aws.amazon.com/blogs/compute/new-amazon-ec2-spot-pricing/)
![Spot Instance pricing history](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/spot-instance/img/pricing_history.png?raw=true)

---

Ref:
- https://dev.to/awsmenacommunity/overview-of-amazon-ec2-spot-instances-3kph
- https://instances.vantage.sh/
- https://d1.awsstatic.com/events/reinvent/2019/REPEAT_1_Save_up_to_90_percent_and_run_production_workloads_on_Spot_Instances_CMP331-R1.pdf

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
