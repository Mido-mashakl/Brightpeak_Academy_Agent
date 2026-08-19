# Cloud Computing Basics

## Course Overview

Cloud computing means renting computing resources — servers, storage, databases, and more — from a provider over the internet, instead of buying and maintaining physical hardware. This material introduces the core service models and some well-known cloud providers.

## IaaS, PaaS, and SaaS

Cloud services are typically grouped into three levels, based on how much of the underlying infrastructure the provider manages for you:

- **IaaS (Infrastructure as a Service)**: the provider gives you raw computing resources — virtual servers, storage, and networking — and you manage the operating system, runtime, and application yourself. Example: renting a virtual machine.
- **PaaS (Platform as a Service)**: the provider manages the underlying infrastructure and operating system, and you just deploy your application code. Example: deploying a web app without managing the server it runs on.
- **SaaS (Software as a Service)**: the provider manages everything, including the application itself, and you simply use it through a browser. Example: an email service or a project management tool.

## Why the Distinction Matters

Choosing a service model is a tradeoff between control and convenience. IaaS gives the most flexibility but requires more setup and maintenance. SaaS requires almost no setup but offers the least control. PaaS sits in between, letting developers focus on their application code without worrying about server management.

## Major Cloud Providers

The most widely used cloud providers include:

- **Amazon Web Services (AWS)** — one of the largest and most feature-rich providers
- **Microsoft Azure** — widely used, especially in enterprises already using Microsoft tools
- **Google Cloud Platform (GCP)** — known for its data and machine learning services

Each provider offers services across all three models (IaaS, PaaS, SaaS), and most core concepts — virtual machines, storage buckets, managed databases — transfer between providers even though the exact names and interfaces differ.

## Looking Ahead

Understanding these categories makes it easier to choose the right service when building or deploying an application, which is the focus of the following materials on AWS fundamentals and deployment.
