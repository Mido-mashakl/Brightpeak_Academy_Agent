# Deploying Applications to the Cloud

## Course Overview

This material walks through the practical steps of taking an application from a developer's machine and running it on cloud infrastructure, using the concepts from the previous two materials (cloud basics and AWS fundamentals).

## The General Deployment Process

Regardless of the specific cloud provider, deploying an application typically follows the same overall steps:

1. **Package the application** — bundle the code and its dependencies so it can run reliably on another machine (e.g., using a Docker container or a build artifact).
2. **Provision infrastructure** — create the compute resource that will run the app (e.g., an EC2 instance or a managed platform service).
3. **Configure environment and access** — set environment variables, connect to a database, and set up permissions (IAM roles, security groups).
4. **Deploy the code** — transfer the packaged application to the provisioned infrastructure and start it running.
5. **Verify and monitor** — confirm the app is reachable and working, and set up logging or monitoring to catch issues.

## A Simple Example: Deploying to EC2

```bash
# 1. Connect to the instance
ssh ec2-user@your-instance-ip

# 2. Install dependencies
sudo yum install -y nodejs

# 3. Copy application code to the instance (from local machine)
scp -r ./my-app ec2-user@your-instance-ip:/home/ec2-user/

# 4. Start the application
cd my-app
npm install
node server.js
```

In practice, teams often automate these steps rather than running them manually each time, using scripts or CI/CD pipelines that deploy automatically whenever new code is pushed.

## Storing Static Assets

For static files (images, course material files, frontend build output), it's common to upload them to an S3 bucket rather than storing them on the same server running the application code — this keeps the server lightweight and lets static content be served efficiently.

## Why This Matters

Understanding the deployment process — even at a basic level — makes it much easier to reason about why an app is slow, unreachable, or misconfigured, since most issues trace back to one of these steps: packaging, infrastructure, configuration, or deployment itself.
