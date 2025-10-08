# LendX: Decentralised Micro-Lending Platform (FTC 2025)

Welcome to **LendX**, the foundation for our ECO5037S (FTC) class project. This repository will evolve into a proof-of-concept platform that explores how decentralised infrastructure and alternative data can unlock affordable credit for South Africans who are underserved by traditional credit systems.

> **Project Vision:** Build an end-to-end lending experience that connects thin-file borrowers and community lenders through open banking data, a Python-based credit scoring engine, smart escrow contracts on the XRPL EVM sidechain, and user-friendly touchpoints such as a Telegram bot and web portal.

---

## 🧭 Project Roadmap

The project brief highlights the following goals:

1. **Data-Driven Creditworthiness**
   - Collect user-permissioned banking data via an Absa-inspired Open Banking API.
   - Generate alternative credit scores for thin-file clients using a transparent Python scoring engine.
2. **Decentralised Lending Mechanics**
   - Deploy smart contracts on the XRPL EVM sidechain to escrow funds, issue loans, manage repayments, and mint non-transferable **CreditTrust Tokens** that reflect repayment behaviour.
   - Explore cross-chain bridges (Axelar, Squid Router) where relevant for liquidity routing.
3. **User-Facing Experiences**
   - **Telegram Bot:** Facilitate borrower and lender onboarding, loan requests, approvals, and repayment notifications.
   - **Web Platform:** Surface smart contract activity, portfolio analytics, and provide a portal for technically savvy lenders to supply liquidity.

Throughout the semester we will iterate on architecture, smart contract design, UI flows, and operational processes. Expect substantial changes as we validate assumptions and integrate feedback from the product and management teams.

---

## 📁 Repository Overview

```
ftc-lendx/
├── backend/            # Django project that currently houses core services
├── compose/            # Docker Compose definitions for local environments
├── deploy/             # Container and server deployment assets
├── docs/               # Assignment brief, research notes, and specifications
├── scripts/            # Helper scripts for setup and automation
├── tests/              # Automated tests (to be expanded)
├── manage.py           # Django management entry point
└── README.md           # You're here!
```

This structure will grow to include:
- A modular credit scoring engine
- Smart contract packages and deployment scripts
- Front-end/web application code
- Telegram bot integrations
- Documentation on architecture, APIs, and operations

---

## 🚀 Getting Started (Current State)

We are beginning with the existing Django + Telegram bot foundation. Use the Makefile and Docker setup for consistent development environments.

### Prerequisites
- [Docker](https://www.docker.com/get-started) & [Docker Compose](https://docs.docker.com/compose/install/) **or**
- Python 3.11+, PostgreSQL 16, and your preferred virtual environment manager

### Quick Start with Docker
```bash
# Clone the repository
 git clone <project-url>
 cd ftc-lendx

# Copy and configure environment variables
 cp .env.example .env
 # Update secrets such as DJANGO_SECRET_KEY and TELEGRAM_BOT_TOKEN

# Build and run services
 make up
```
Services default to:
- Django backend: http://localhost:8000
- PostgreSQL: localhost:5433 (adjust as needed in `compose/docker-compose.dev.yml`)

### Local Python Environment
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements/dev.txt

# Configure database credentials and environment variables, then run:
python manage.py migrate
python manage.py runserver
```

### Helpful Make Targets
```bash
make build           # Rebuild the web image
make logs            # Tail application logs
make migrate         # Apply database migrations
make manage CMD=test # Run Django tests
```

---

## 📝 Documentation & Deliverables

Keep project documentation in the `docs/` directory. Over the term, we will produce:

- **Project & Technical Specification** (market research, requirements, user stories, UI mockups, architecture diagrams, technology choices)
- **Lessons Learnt Report** (individual reflection)
- **Proof of Concept** (this repository + deployed demo)
- **Presentation & Demo** showcasing the solution

Upcoming course deadlines:
- **10 Oct:** Specification check-in
- **17 Oct:** Final specification submission
- **24 Oct:** POC check-in
- **31 Oct:** POC + presentation demo
- **3 Nov:** Final submission

---

## 🔭 Next Steps

- Set up research sprints to understand user needs, regulatory constraints, and technical feasibility (open banking, XRPL EVM).
- Begin prototyping the credit scoring engine, Telegram bot flow, and smart contract architecture.

This README will evolve alongside the project. Update it regularly to reflect the latest architecture, setup steps, and learnings so new contributors can onboard quickly.

---

## 🤝 Contributing

1. **Branching**  
   - For each issue, create a new branch using GitHub’s default naming convention (e.g., `15-workflow-branching-strategy`).  
   - Branch names should clearly reference the issue number and purpose.

2. **Commits**  
   - Write short, descriptive commit messages using clear language (e.g., “Add Celery task for wallet creation”).  
   - Avoid vague terms like “fix stuff” or “update”.

3. **Pull Requests (PRs)**  
   - Once your feature or fix is ready, open a PR to merge into `main`. 
   - Another team member **must review and approve** your PR before merging.

4. **Collaboration**  
   - If you find gaps or have suggestions, open an issue or start a discussion.  
   - This repo is meant to evolve as our understanding grows.

---

## 📬 Support & Contact

- **Hub Space:** Tuesday–Thursday, 09:00–18:00
- **Technical & Business Support:** Wednesdays, 11:00–13:00 at the Hub
- **Team Channels:** Use our agreed Slack/Discord/Notion groups for daily coordination

Let's build responsibly, document transparently, and keep the end-users—borrowers seeking fair credit access—at the centre of every design decision.
