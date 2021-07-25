FROM python:3.9-alpine

RUN apk --no-cache add yarn npm
RUN yarn global add cdk8s-cli && yarn cache clean
RUN mkdir /deployments && mkdir /build
WORKDIR /deployments
RUN pip install pipenv && \
    cd /build; cdk8s init python-app

ADD entrypoint-python.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh


ENTRYPOINT ["/entrypoint.sh"]
