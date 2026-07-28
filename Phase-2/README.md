# Brightpeak Academic Management Assistant

An AI Assistant for **Brightpeak Academy** that helps students, instructors, and administrators access academic data securely and in an organized way, built using the **Model Context Protocol (MCP)**.

---

## 🎯 Project Idea

The LLM (Gemini) **does not connect to the database directly**. Instead, every request flows through an MCP Server, which handles authorization, tool execution, resource access, and input validation.

```
User
  │
  ▼
Gemini (LLM)
  │
  ▼
MCP Server
  │
  ▼
Database
```

### MCP Server Responsibilities

- Access control / authorization
- Executing tools
- Reading resources
- Validating inputs
- Protecting the database

---

## 🗄️ Database

The project uses **SQLite**, with the following tables:

- Students
- Courses
- Instructors
- Enrollments
- Assignments
- Grades
- Attendance
- Policies

Along with:

- `ERD.png` — entity relationship diagram
- `schema.sql` — table definitions
- `seed.sql` — sample/test data

---

## 📂 Project Structure

```
Brightpeak-MCP/
│
├── README.md
│
├── db/
│   ├── schema.sql
│   ├── seed.sql
│   ├── brightpeak.db
│   └── ERD.png
│
├── mcp_server/
│   ├── server.py
│   ├── tools.py
│   ├── resources.py
│   ├── prompts.py
│   ├── notifications.py
│   ├── auth.py
│   └── validation.py
│
├── agent/
│   ├── client.py
│   ├── agent.py
│   └── demo.py
│
├── tests/
│
├── .env
└── requirements.txt
```

---

## ✅ Required MCP Features

| # | Feature | Description |
|---|---------|--------------|
| 1 | **Capability Negotiation** | On connection, the server announces its capabilities and the client verifies them |
| 2 | **Notifications** | When a user's role changes (Student → Instructor → Admin), available tools update without reconnecting |
| 3 | **Elicitation** | Sensitive operations (e.g., deleting a student's enrollment) pause and require user confirmation before executing |
| 4 | **Resources** | Static files such as the Attendance Policy, Scholarship Policy, and Academic Rules are exposed as Resources, not Tools |
| 5 | **Prompts** | Ready-made templates such as "Generate Student Report" and "Draft Warning Email" |
| 6 | **Progress Tracking** | Long-running operations (e.g., generating a report for all students) show progress (10% → 50% → 100%) |
| 7 | **Defensive Tool Design** | Every tool has a JSON Schema, validation, and authorization, preventing invalid input |
| 8 | **Transport** | stdio during development, with optional support for Streamable HTTP |

---

## 👥 Team Split

### Ahmed — Database
- ERD design
- Writing `schema.sql`
- Writing `seed.sql`
- Setting up SQLite
- Preparing test data

### Omar — MCP Server
- Server implementation
- Tools
- Notifications
- Resources
- Prompts
- Authorization
- Validation
- Progress Tracking

### Farida — Agent
- Gemini Client
- Handshake
- Tool Discovery
- Tool Calls
- Demo
- Final README

---

## 📝 Suggested GitHub Issues

- [ ] Design Database
- [ ] Create ERD
- [ ] Build MCP Server
- [ ] Implement Notifications
- [ ] Implement Resources
- [ ] Build Agent
- [ ] Demo
- [ ] README

---

## 🎥 Demo Requirements

The demo must show:

1. Handshake
2. Tool Call
3. Notification
4. Resource
5. Prompt
6. Elicitation
7. Progress Tracking
8. Final Result
---

## 🧭 Project Summary

We are building an AI assistant for Brightpeak Academy powered by Gemini. Instead of accessing the database directly, it goes through an MCP Server that provides secure, organized data access, supporting all required MCP features such as Notifications, Resources, Elicitation, Progress Tracking, and Authorization.

---
