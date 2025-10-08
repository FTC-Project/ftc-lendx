## Tech Stack & Rationale

### Backend (Django + Celery + Redis + Postgres)
- We use **Django** as our core backend framework for API logic, authentication, and Telegram bot orchestration.  
- **Celery** handles asynchronous and scheduled tasks, such as scoring and blockchain transaction processing.  
- **Redis** serves as the Celery message broker and short-term cache.  
- **PostgreSQL** is our primary relational database for user data, wallet references, and loan records.  
- Together, this stack supports scalable, event-driven, and maintainable backend operations.

### Scoring Service (Python + Celery Workers)
- Credit scoring is implemented as **Python Celery tasks**, allowing us to run distributed scoring jobs in parallel.  
- Each worker computes borrower scores, signs attestations, and optionally posts verified scores on-chain via the `ScoreRegistry` contract. (*Might change in future*)
- This architecture keeps our scoring process modular, testable, and extendable.

### Contracts (Solidity + Hardhat)
- Smart contracts are written in **Solidity** and managed through **Hardhat** for local development, testing, and deployment to the **XRPL EVM sidechain**.  
- After deployment, we **export the ABIs and contract addresses** into the backend (`backend/onchain/`) so Django can interact with them.  
- Hardhat also supports local in-memory testing networks, enabling contract verification and gas estimation before XRPL EVM deployment.

### On-chain Access (web3.py)
- The backend interacts with deployed contracts using **web3.py**.  
- ABIs and contract addresses are stored in `backend/onchain/abi/` and `backend/onchain/addresses.json`.  
- Django and Celery workers use web3.py to perform on-chain reads (balance checks, events) and writes (funding, repayments, score updates).

### Frontend (Django Templates + Ethers.js)
- We use **Django templates** for all read-only pages (dashboards, metrics, loan listings).  
- A single minimal **Ethers.js** client (loaded via CDN) handles wallet-connected actions like deposits and withdrawals into the `LiquidityBackstopPool`.  
- This hybrid approach keeps the frontend lightweight while still enabling decentralized user interactions directly from the browser.  
- If more interactivity is needed later, the system can easily integrate a small **React/Vite** app.

### Infrastructure (Docker + Makefile)
- **Docker Compose** orchestrates services for backend, Redis, Postgres, and (optionally) the scoring microservice.  
- A root **Makefile** defines commands like `make up`, `make deploy-contracts`, and `make sync-abi` for reproducible developer workflows.  
- Python 3.11 is the pinned runtime across all backend and scoring components.


## Repository Structure
```
ftc-lendx/
├── backend/
│ ├── apps/
│ │ ├── botutils/
│ │ │ ├── management/commands/
│ │ │ ├── migrations/
│ │ │ └── price_history/
│ │ ├── telegram_bot/commands/
│ │ └── users/migrations/
│ ├── onchain/
│ │ ├── abi/
│ │ └── addresses.json
│ └── settings/
├── contracts/
│ ├── contracts/
│ ├── scripts/
│ ├── test/
│ ├── hardhat.config.ts
│ └── package.json
├── scoring/
│ └── tasks.py
├── compose/env/
├── infra/
│ ├── docker-compose.yml
│ └── Makefile
├── docs/
│ └── final_tech_stack.md
├── deploy/
├── scripts/
└── tests/
```

### Summary
Our stack combines **Python (Django, Celery, FastAPI)** with **Solidity (Hardhat)** to integrate off-chain computation and on-chain settlement.  
The system is modular, non-custodial, and scalable, balancing P2P transparency with a decentralized liquidity backstop built on the XRPL EVM.

