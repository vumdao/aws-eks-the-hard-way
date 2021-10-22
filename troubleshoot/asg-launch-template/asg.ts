import { Stack, App, Tags, StackProps} from '@aws-cdk/core';
import { Cluster, Nodegroup, CapacityType, TaintEffect } from '@aws-cdk/aws-eks'
import { Role, ServicePrincipal, ManagedPolicy, PolicyStatement, Effect, IRole } from '@aws-cdk/aws-iam';
import * as ec2 from '@aws-cdk/aws-ec2';


export class AsgStack extends Stack {
    public eks_cluster: any;
    public worker_role: any;
    public SG: any;
    public eksCluserName: string;
    public launchTemplate: any;
    public vpcSg: any;
    public vpc: ec2.IVpc;

    constructor(public scope: App, id: string, props?: StackProps) {
        super(scope, id, props);

        this.vpcSg = ec2.SecurityGroup.fromLookup(this, 'VPCSG', 'sg-0c8461ab50fd7bf54');

        this.vpc = ec2.Vpc.fromLookup(this, 'EfsVPC', {
            isDefault: false,
            vpcId: 'vpc-ecb25394'
        });

        this.eksCluserName = 'us-eks'

        // EKS cluster
        this.eks_cluster = Cluster.fromClusterAttributes(
            this, 'EksCluster', {
                this.vpc,
                clusterName: this.eksCluserName
            }
        );

        this.launchTemplate = this.createLaunchTemplate();

        // SG to workers
        this.SG = this.createSG();

        this.worker_role = this.createWorkerRole();

        this.createAsgPet();
    };

    createWorkerRole(): IRole {
        // IAM worker role
        const worker_role = new Role(
            this, 'IamRole', {
                assumedBy: new ServicePrincipal('ec2.amazonaws.com'),
                roleName: `${this.eksCluserName}-role`
            }
        );
        const attachPolicies = ['AmazonEC2ContainerRegistryReadOnly', 'AmazonEKSWorkerNodePolicy', 'AmazonS3ReadOnlyAccess', 'AmazonEKS_CNI_Policy'];
        for (var policy of attachPolicies) {
            worker_role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName(policy))
        }
        Tags.of(worker_role).add('Name', `${this.eksCluserName}`)
        Tags.of(worker_role).add('env', 'us-prod')

        const autoscalingStatement = new PolicyStatement({
            sid: 'AutoScalingGroup',
            actions: [
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "autoscaling:DescribeLaunchConfigurations",
                "autoscaling:DescribeTags",
                "autoscaling:CreateOrUpdateTags",
                "autoscaling:UpdateAutoScalingGroup",
                "autoscaling:TerminateInstanceInAutoScalingGroup",
                "ec2:DescribeLaunchTemplateVersions",
                "elasticfilesystem:*",
                "tag:GetResources",
            ],
            effect: Effect.ALLOW,
            resources: ['*'],
            conditions: {
                'StringEquals': {"aws:RequestedRegion": 'us-east-1'}
            }
        });

        worker_role.addToPolicy(autoscalingStatement);

        return worker_role;
    };

    createSG(): any {
        /**
         *  security group
         */
        const asgSG = new ec2.SecurityGroup(this, 'SG', {
            vpc: this.vpc,
            securityGroupName: 'priv-sg',
            description: 'Security group to access to worker in private vpc',
            allowAllOutbound: true
        });
        asgSG.connections.allowFrom(asgSG, ec2.Port.allTcp(), 'Allow node to communicate with each other');
        asgSG.connections.allowFrom(this.vpcSg, ec2.Port.allTcp(), 'Allow nodes in another ASG communicate to nodes');
        asgSG.connections.allowFrom(this.eks_cluster.connections, ec2.Port.allTcp(), 'Allow EKS Control Plane to to access Node');

        Tags.of(asgSG).add('Name', 'priv');
        Tags.of(asgSG).add('env', 'us-prod');

        return asgSG;
    };

    createLaunchTemplate(): any {
        /**
         * More about launch-templates: https://github.com/awsdocs/amazon-eks-user-guide/blob/master/doc_source/launch-templates.md
         * Notes:
         * - Nodegroup auto-generates role if not specify
         * - Launch template node group automatically add the worker role to aws-auth configmap
        */
        const LaunchTemplate = new ec2.LaunchTemplate(this, 'LaunchTemplate-lt', {
            launchTemplateName: 'asg-lt',
            securityGroup: this.SG,
            blockDevices: [{
                deviceName: '/dev/xvda',
                volume: ec2.BlockDeviceVolume.ebs(20)
            }],
            keyName: 'us-pem'
        });
        Tags.of(LaunchTemplate).add('Name', 'asg-lt');
        Tags.of(LaunchTemplate).add('env', 'us-prod');

        return LaunchTemplate;
    }

    createAsgPet() {
        /**
         * ASG Pet is used to assign deployments. Due to using spot instances so recommendation min size 2
         */
        const asgPet = new Nodegroup(this, 'PetAsg', {
            nodegroupName: 'eks-nodegroup-pet',
            subnets: this.eks_cluster.vpc.selectSubnets({subnetType: ec2.SubnetType.PRIVATE}),
            cluster: this.eks_cluster,
            capacityType: CapacityType.SPOT,
            nodeRole: this.worker_role,
            instanceTypes: [
                new ec2.InstanceType('c5a.xlarge'),
                new ec2.InstanceType('c5.xlarge')
            ],
            minSize: 1,
            maxSize: 2,
            labels: {
                'role': 'pet',
                'type': 'stateless',
                'lifecycle': 'spot'
            },
            taints: [
                {
                    effect: TaintEffect.NO_SCHEDULE,
                    key: 'dedicated',
                    value: 'pet'
                }
            ],
            tags: {
                'Name': 'eks-nodegroup-pet',
            },
            launchTemplateSpec: {
                id: this.launchTemplate.launchTemplateId!
            }
        });
    };
}

const coreEnv = {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
};
  
const app = new App();
  
new AsgStack(app, 'eks-asg-lab', { env: coreEnv });

app.synth();