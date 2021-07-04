<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Argo Workflow v3.1 On EKS With AWS ALB Controller" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/argo-workflow/img/cover.jpg?raw=true" width="700" />
  </a>
</p>
<h1 align="center">
  <div><b>Argo Workflow v3.1 On EKS With AWS ALB Controller</b></div>
</h1>

## Table Of Contents
 * [What is Argo Workflows?](#What-is-Argo-Workflows?)
 * [Install argo CLI](#Install-argo-CLI)
 * [Deploy Argo Controller](#Deploy-Argo-Controller)
 * [Configure Artifact Repository](#Configure-Artifact-Repository)
 * [Ingress Configuration Using AWS ALB Controller](#Ingress-Configuration-Using-AWS-ALB-Controller)
 * [Create access token from admin role](#Create-access-token-from-admin-role)
 * [Advanced Batch Workflow](#Advanced-Batch-Workflow)
 * [Conclusion](#-Conclusion)

---

## 🚀 **What is Argo Workflows?** <a name="What-is-Argo-Workflows?"></a>
<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="What is Argo Workflows?" src="https://github.com/vumdao/aws-eks-the-hard-way/blob/master/argo-workflow/img/argo.jpg?raw=true" width="700" />
  </a>
</p>

[Argo Workflows](https://argoproj.github.io/projects/argo/) is an open source container-native workflow engine for orchestrating parallel jobs on Kubernetes. Argo Workflows is implemented as a Kubernetes CRD.

## 🚀 **Install argo CLI** <a name="Install-argo-CLI"></a>
```
# Download the binary
curl -sLO https://github.com/argoproj/argo-workflows/releases/download/v3.1.1/argo-linux-amd64.gz

# Unzip
gunzip argo-linux-amd64.gz

# Make binary executable
chmod +x argo-linux-amd64

# Move binary to path
mv ./argo-linux-amd64 /usr/local/bin/argo

# Test installation
argo version --short
argo: v3.1.1
```

## 🚀 **Deploy Argo Controller** <a name="Deploy-Argo-Controller"></a>
- Install argo workflow controller and server
```
kubectl create namespace argo
kubectl apply -n argo -f https://github.com/argoproj/argo-workflows/releases/download/v3.1.1/install.yaml
```

- Update argo-server service to use `NodePort` type if we want to use AWS ALB controller
```
kubectl -n argo patch svc argo-server -p '{"spec": {"type": "NodePort"}}'
```

## 🚀 **Configure Artifact Repository** <a name="Configure-Artifact-Repository"></a>
- Argo uses an artifact repository to pass data between jobs in a workflow, known as artifacts. Amazon S3 can be used as an artifact repository.

- Create S3 bucket
```
aws s3 mb s3://eksworkshop-batch-artifact-repository-argo-workflow --region ap-northeast-2
```

- Update the S3 bucket to `workflow-controller-configmap`
```
cat <<EOF > argo-patch.yaml
data:
  config: |
    artifactRepository:
      s3:
        bucket: eksworkshop-batch-artifact-repository-argo-workflow
        endpoint: s3.amazonaws.com
EOF

kubectl -n argo patch configmap/workflow-controller-configmap --patch "$(cat argo-patch.yaml)"
```

## 🚀 **Ingress Configuration Using AWS ALB Controller**  <a name="Ingress-Configuration-Using-AWS-ALB-Controller"></a>
- **IMPORTANT** note: Since v3.0 the Argo Server listens for HTTPS requests, rather than HTTP so we have to set `alb.ingress.kubernetes.io/backend-protocol` to `HTTPS`

- Simple yaml but I would like to introduce using `cdk8s`. Go to [cdk8s example](https://dev.to/vumdao/cdk8s-example-2glk) to know more
{% details argowfig.py %}
```
from constructs import Construct
from cdk8s import Chart, App
from imports import k8s


class ArgoWfIngress(Chart):
    def __init__(self, scope: Construct, id: str, name_space):
        super().__init__(scope, id, namespace=name_space)

        app_name = 'argowf'
        app_label = {'dev': app_name}
        k8s.KubeIngressV1Beta1(
            self, 'ArgoWfIngress',
            metadata=k8s.ObjectMeta(
                annotations={
                    'kubernetes.io/ingress.class': 'alb',
                    'alb.ingress.kubernetes.io/group.name': 'dev',
                    'alb.ingress.kubernetes.io/group.order': '8',
                    'alb.ingress.kubernetes.io/backend-protocol': 'HTTPS',
                    'alb.ingress.kubernetes.io/listen-ports': '[{"HTTPS":443}]',
                    'alb.ingress.kubernetes.io/certificate-arn':
                        'arn:aws:acm:ap-northeast-2:123456789012:certificate/aaaaaaaa-bbbb-4f69-a696-f1d839xxxxxx'
                },
                labels=app_label,
                name=app_name
            ),
            spec=k8s.IngressSpec(
                rules=[
                    k8s.IngressRule(
                        host="argowf.cloudopz.co",
                        http=k8s.HttpIngressRuleValue(
                            paths=[
                                k8s.HttpIngressPath(
                                    backend=k8s.IngressBackend(
                                        service_name='argo-server',
                                        service_port=k8s.IntOrString.from_number(2746)
                                    )
                                )
                            ]
                        )
                    )
                ]
            )
        )


app = App()
ArgoWfIngress(app, 'ArgoWfIngress', name_space='argo')
app.synth()
```
{% enddetails %}

- Apply the ingress and check the ALB rule
![Alt-Text](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/argo-workflow/img/ingress_target.png?raw=true)

- We now have the URL `argowf.cloudopz.co` but need to create method to login here we use access token

## 🚀 **Create access token from admin role** <a name="Create-access-token-from-admin-role"></a>
- If you want to automate tasks with the Argo Server API or CLI, you will need an access token. Here I use this token to login in the UI either

- It's for demo so we create an access token from admin role which have full permissions to `argoproj.io` api group, workflow resources, verbs and k8s pods.

- Create `default-admin` rolebinding which is referenced to cluster admin role and serviceaccount `argo` in namespace `argo`. We can create another role such `jenkins` with proper permission like `--verb=list,update`
```
kubectl create rolebinding default-admin --clusterrole=admin --serviceaccount=argo:argo -n argo
```

- Get access token
```
SECRET=$(kubectl get sa argo -n argo -o=jsonpath='{.secrets[0].name}')
ARGO_TOKEN="Bearer $(kubectl get secret -n argo $SECRET -o=jsonpath='{.data.token}' | base64 --decode)"
echo $ARGO_TOKEN
Bearer eyJhbGciOiJ...
```

- Now we can goto the UI and let's submit a workflow
![Alt-Text](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/argo-workflow/img/login_token.png?raw=true)

## 🚀 **Advanced Batch Workflow** <a name="Advanced-Batch-Workflow"></a>
- Create the manifest [teardrop.yaml](https://www.eksworkshop.com/advanced/410_batch/workflow-advanced/)

{% details teardrop.yaml %}
```
cat <<EoF > teardrop.yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: teardrop-
spec:
  entrypoint: teardrop
  templates:
  - name: create-chain
    container:
      image: alpine:latest
      command: ["sh", "-c"]
      args: ["echo '' >> /tmp/message"]
    outputs:
      artifacts:
      - name: chain
        path: /tmp/message
  - name: whalesay
    inputs:
      parameters:
      - name: message
      artifacts:
      - name: chain
        path: /tmp/message
    container:
      image: docker/whalesay
      command: ["sh", "-c"]
      args: ["echo Chain: ; cat /tmp/message* | sort | uniq | tee /tmp/message; cowsay This is Job {{inputs.parameters.message}}! ; echo {{inputs.parameters.message}} >> /tmp/message"]
    outputs:
      artifacts:
      - name: chain
        path: /tmp/message
  - name: whalesay-reduce
    inputs:
      parameters:
      - name: message
      artifacts:
      - name: chain-0
        path: /tmp/message.0
      - name: chain-1
        path: /tmp/message.1
    container:
      image: docker/whalesay
      command: ["sh", "-c"]
      args: ["echo Chain: ; cat /tmp/message* | sort | uniq | tee /tmp/message; cowsay This is Job {{inputs.parameters.message}}! ; echo {{inputs.parameters.message}} >> /tmp/message"]
    outputs:
      artifacts:
      - name: chain
        path: /tmp/message
  - name: teardrop
    dag:
      tasks:
      - name: create-chain
        template: create-chain
      - name: Alpha
        dependencies: [create-chain]
        template: whalesay
        arguments:
          parameters: [{name: message, value: Alpha}]
          artifacts:
            - name: chain
              from: "{{tasks.create-chain.outputs.artifacts.chain}}"
      - name: Bravo
        dependencies: [Alpha]
        template: whalesay
        arguments:
          parameters: [{name: message, value: Bravo}]
          artifacts:
            - name: chain
              from: "{{tasks.Alpha.outputs.artifacts.chain}}"
      - name: Charlie
        dependencies: [Alpha]
        template: whalesay
        arguments:
          parameters: [{name: message, value: Charlie}]
          artifacts:
            - name: chain
              from: "{{tasks.Alpha.outputs.artifacts.chain}}"
      - name: Delta
        dependencies: [Bravo]
        template: whalesay
        arguments:
          parameters: [{name: message, value: Delta}]
          artifacts:
            - name: chain
              from: "{{tasks.Bravo.outputs.artifacts.chain}}"
      - name: Echo
        dependencies: [Bravo, Charlie]
        template: whalesay-reduce
        arguments:
          parameters: [{name: message, value: Echo}]
          artifacts:
            - name: chain-0
              from: "{{tasks.Bravo.outputs.artifacts.chain}}"
            - name: chain-1
              from: "{{tasks.Charlie.outputs.artifacts.chain}}"
      - name: Foxtrot
        dependencies: [Charlie]
        template: whalesay
        arguments:
          parameters: [{name: message, value: Foxtrot}]
          artifacts:
            - name: chain
              from: "{{tasks.create-chain.outputs.artifacts.chain}}"
      - name: Golf
        dependencies: [Delta, Echo]
        template: whalesay-reduce
        arguments:
          parameters: [{name: message, value: Golf}]
          artifacts:
            - name: chain-0
              from: "{{tasks.Delta.outputs.artifacts.chain}}"
            - name: chain-1
              from: "{{tasks.Echo.outputs.artifacts.chain}}"
      - name: Hotel
        dependencies: [Echo, Foxtrot]
        template: whalesay-reduce
        arguments:
          parameters: [{name: message, value: Hotel}]
          artifacts:
            - name: chain-0
              from: "{{tasks.Echo.outputs.artifacts.chain}}"
            - name: chain-1
              from: "{{tasks.Foxtrot.outputs.artifacts.chain}}"
EoF
```
{% enddetails %}

- Now deploy the workflow using the argo CLI.
```
argo -n argo submit --watch teardrop.yaml
```

- Go to UI and check result

![demo1](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/argo-workflow/img/demo1.png?raw=true)

![demo2](https://github.com/vumdao/aws-eks-the-hard-way/blob/master/argo-workflow/img/demo2.png?raw=true)

## 🚀 **Conclusion** <a name="Conclusion"></a>
- Keywords: argo-workflow, cdk8s, aws alb controller
- Advanced things are from [Argo Workflows - The workflow engine for Kubernetes](https://argoproj.github.io/argo-workflows/)