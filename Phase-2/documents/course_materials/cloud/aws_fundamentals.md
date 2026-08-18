# AWS Fundamentals

## Course Overview

Amazon Web Services (AWS) is one of the largest cloud providers, offering hundreds of services. This material focuses on three of the most foundational: EC2, S3, and IAM.

## EC2 (Elastic Compute Cloud)

EC2 provides virtual servers, called **instances**, that you can rent and configure with a chosen amount of CPU, memory, and storage. You choose an instance type based on your workload (e.g., a small instance for a simple web app, a larger one for heavy computation), and AWS handles the underlying physical hardware.

Key EC2 concepts:

- **AMI (Amazon Machine Image)**: a template defining the operating system and pre-installed software an instance starts with
- **Instance type**: determines the hardware resources (CPU, memory) allocated to the instance
- **Security group**: a virtual firewall controlling what network traffic can reach the instance

## S3 (Simple Storage Service)

S3 is an object storage service used to store and retrieve files — images, backups, logs, static website assets — of virtually any size. Data is organized into **buckets** (containers) and identified by a unique key (like a file path) within each bucket.

```
bucket: brightpeak-course-assets
key: course_materials/python/basics.md
```

S3 is designed for high durability and is commonly used both as a backend for applications and for hosting static files.

## IAM (Identity and Access Management)

IAM controls **who** can access AWS resources and **what** they're allowed to do. It's built around a few core concepts:

- **Users**: individual identities (people or applications) that can sign in or make API calls
- **Roles**: a set of permissions that can be assumed temporarily, often by AWS services themselves
- **Policies**: documents that define exactly which actions are allowed or denied on which resources

Following the principle of least privilege — granting only the permissions actually needed — is a core best practice when configuring IAM.

## Putting Them Together

A common pattern is an EC2 instance (running your application) that reads and writes files to an S3 bucket, with an IAM role attached to the instance that grants it just enough permission to access that specific bucket and nothing more.
