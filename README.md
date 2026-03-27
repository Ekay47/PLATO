<p align="center">
  <img src="./logo.svg" alt="PLATO" width="224">
</p>

<h1 align="center">PLATO</h1>

<p align="center">
  <strong>Natural Language → Behavioral Diagrams, Automatically.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/node-18%2B-339933?logo=node.js&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/FastAPI-0.128-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18.2-61DAFB?logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/PlantUML-diagram%20engine-blue" alt="PlantUML">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

PLATO takes natural-language requirements and produces validated PlantUML behavioral diagrams through a multi-stage LLM pipeline [LATO](https://github.com/reg-repo/LATO) — with real-time progress streaming and interactive canvas rendering.

<p align="center">
  <code>Requirement</code> → <code>Identification</code> → <code>Decomposition</code> → <code>Integration</code> → <code>PlantUML</code> → <code>Render / Export</code>
</p>

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Testing](#testing)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Features

- **LLM-Powered Generation** — Multi-stage pipeline (identification → decomposition → integration → code generation) driven by GPT-4 / compatible models via LangChain
- **Structured Knowledge Retrieval** — Domain-specific PlantUML knowledge base for context-augmented generation
- **Real-Time Streaming** — Server-Sent Events (SSE) deliver workflow progress, intermediate artifacts, and final output as they are produced
- **Interactive Canvas** — ReactFlow-based diagram visualization with auto-layout (dagre / ELK)
- **NLP Enhancement** — Optional coreference resolution (fastcoref) and dependency parsing (Stanford CoreNLP) for improved requirement understanding
- **PlantUML Validation** — Syntax validation and PNG rendering via local PlantUML JAR before delivery
- **Export** — PlantUML source code and rendered PNG export

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.9+, FastAPI, LangChain, LangGraph, Pydantic v2 |
| **NLP** | Stanford CoreNLP, spaCy, fastcoref, Transformers |
| **Diagram Engine** | PlantUML (local JAR) |
| **Frontend** | React 18, TypeScript, ReactFlow, TailwindCSS, Vite |
| **Layout** | dagre, ELK.js |

## Architecture

```text
PLATO/
├─ backend/
│  ├─ main.py                     Entry point (Uvicorn)
│  ├─ config.example.yaml         Configuration template
│  ├─ src/
│  │  ├─ api/                     HTTP routes & schemas
│  │  ├─ application/             Run orchestration & workflow logic
│  │  ├─ bootstrap/               App factory & lifecycle wiring
│  │  ├─ core/                    Modeling, validation, KB retrieval
│  │  ├─ domain/                  Run models & domain state
│  │  ├─ infrastructure/          Run store & adapters
│  │  └─ lato/                    Prompt assets
│  ├─ nl2diagram/
│  │  ├─ kb/                      PlantUML knowledge base
│  │  ├─ prompts/                 Prompt templates
│  │  ├─ scripts/                 KB maintenance scripts
│  │  └─ coverage/                Coverage & audit outputs
│  └─ tests/
└─ frontend/
   └─ src/
      ├─ components/              UI components
      ├─ hooks/                   React hooks (SSE, diagram state)
      ├─ types/                   TypeScript type definitions
      └─ utils/                   Utilities & helpers
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Ekay47/PLATO.git
cd PLATO

# 2. Backend
cd backend
cp config.example.yaml config.yaml        # then fill in llm.api_key
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8147 --reload

# 3. Frontend (new terminal)
cd frontend
echo "VITE_API_BASE=http://localhost:8147" > .env.development
npm install && npm run dev
```

Open **http://localhost:5173** — enter a requirement and watch the pipeline run.

## Installation

### Prerequisites

| Dependency | Version | Required | Notes |
|-----------|---------|----------|-------|
| Python | 3.9+ | Yes | Backend runtime |
| Node.js | 18+ | Yes | Frontend build |
| Java | 8+ | Yes | PlantUML JAR execution |
| PlantUML JAR | — | Yes | Place in `backend/src/utils/` |
| Stanford CoreNLP | 4.5.10 | Optional | When `nlp.dependency_provider: corenlp` |
| fastcoref | — | Optional | When `nlp.coref_provider: fastcoref` |

### Backend Setup

1. **Configuration**

   ```bash
   cd backend
   cp config.example.yaml config.yaml
   ```

   Edit `config.yaml` and set your `llm.api_key`.

2. **Dependencies**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Runtime Assets**

   Place the following in `backend/src/utils/` if not already present:

   | Asset | Purpose |
   |-------|---------|
   | `plantuml-*.jar` | PlantUML validation & PNG rendering |
   | `stanford-corenlp-4.5.10/` | CoreNLP dependency parsing (optional) |
   | `f-coref/` | Coreference resolution model (optional) |
   | `en_core_web_sm-*.whl` | spaCy English model (optional) |

4. **Start**

   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8147 --reload
   ```

5. **Verify** — open http://127.0.0.1:8147/health

#### CoreNLP Configuration

The backend supports two CoreNLP modes via `config.yaml`:

| Mode | Behavior |
|------|----------|
| `corenlp.mode: managed` | Backend starts/stops CoreNLP automatically |
| `corenlp.mode: external` | You run CoreNLP independently |

External CoreNLP startup:

```bash
cd backend/src/utils/stanford-corenlp-4.5.10
java -Xmx2g -cp "*" edu.stanford.nlp.pipeline.StanfordCoreNLPServer \
  -host 127.0.0.1 -port 9000 -timeout 600000 -threads 2 -maxCharLength 50000 -quiet
```

### Frontend Setup

```bash
cd frontend
echo "VITE_API_BASE=http://localhost:8147" > .env.development
npm install
npm run dev
```

Open **http://localhost:5173**.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check (includes CoreNLP status) |
| `POST` | `/runs` | Create a new diagram generation run |
| `GET` | `/runs/{run_id}` | Retrieve run status and artifacts |
| `GET` | `/runs/{run_id}/events` | SSE stream of run progress and results |
| `POST` | `/generate-model` | One-shot model generation |
| `POST` | `/plantuml/png` | Render PlantUML source to PNG |

## Configuration

Configuration is managed through YAML files:

| File | Purpose |
|------|---------|
| `backend/config.example.yaml` | Safe template — commit this |
| `backend/config.yaml` | Local runtime config — **do not commit** |

**Key configuration sections:**

| Section | Controls |
|---------|----------|
| `server.*` | API host, port, log level |
| `llm.*` | LLM provider URL, model, API key |
| `plantuml.*` | JAR path, render timeout |
| `corenlp.*` | Managed vs. external CoreNLP runtime |
| `nlp.*` | Dependency parser, coreference provider |
| `kb.*` | Knowledge-base root, retrieval parameters |

Override the config file path:

```bash
set PLATO_CONFIG_PATH=C:\path\to\config.yaml
```

## Testing

### Backend

```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```

Test coverage includes:
- Workflow strategy selection and dispatch
- Error payload mapping
- Runs API contracts
- SSE endpoint contract checks

### Frontend

```bash
cd frontend
npm run build    # TypeScript check + production build
npm run lint     # ESLint with zero-warning policy
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

> **Note:** Do not commit secrets or API keys. Keep them in your local `config.yaml` only.

## Acknowledgments

- [PlantUML](https://plantuml.com/) — Diagram rendering engine
- [Stanford CoreNLP](https://stanfordnlp.github.io/CoreNLP/) — Natural language processing
- [LangChain](https://www.langchain.com/) — LLM orchestration framework
- [ReactFlow](https://reactflow.dev/) — Interactive node-based canvas
- [FastAPI](https://fastapi.tiangolo.com/) — High-performance Python web framework

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
