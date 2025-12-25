# 🚀 OneDay.run Platform

**Platforma LLM do automatycznej realizacji zamówień prototypowania w czasie rzeczywistym**

Wykorzystuje **Claude Opus 4.5** via **LiteLLM** do generowania kompletnych rozwiązań IT w ciągu max 1 godziny konwersacji z klientem.

## 🎯 Kluczowe funkcje

- **Real-time Chat** - WebSocket dla natychmiastowej komunikacji
- **Modułowa architektura** - Reużywalne komponenty z biblioteki
- **Automatyczny deployment** - Railway, Vercel, Render
- **GitHub integration** - Automatyczne tworzenie repozytoriów
- **Streaming responses** - Odpowiedzi generowane na żywo

## 📦 Architektura

```
┌─────────────────────────────────────────────────────────────┐
│                     ONEDAY.RUN PLATFORM                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   Client    │◄──►│  WebSocket   │◄──►│  Orchestrator │  │
│  │   (Chat)    │    │   Handler    │    │    Agent      │  │
│  └─────────────┘    └──────────────┘    └───────┬───────┘  │
│                                                  │          │
│  ┌───────────────────────────────────────────────┼────────┐ │
│  │                    SERVICES                   ▼        │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │ │
│  │  │  GitHub  │  │Component │  │   Deployment Manager │ │ │
│  │  │ Service  │  │ Library  │  │ Railway│Vercel│Render│ │ │
│  │  └──────────┘  └──────────┘  └──────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    LLM LAYER                           │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │                   LiteLLM                         │ │ │
│  │  │  Claude Opus 4.5 │ Claude Sonnet 4.5 │ GPT-4o   │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Stack technologiczny

| Komponent | Technologia |
|-----------|-------------|
| Backend | FastAPI + Python 3.11 |
| LLM | Claude Opus 4.5 via LiteLLM |
| Real-time | WebSocket |
| GitHub | PyGithub |
| Deployment | Railway, Vercel, Render API |
| Database | PostgreSQL + SQLAlchemy |
| Cache | Redis |
| Container | Docker |

## 🚀 Quick Start

### 1. Klonowanie i konfiguracja

```bash
git clone https://github.com/prototypowanie-pl/chat.git
cd chat

# Kopiowanie konfiguracji
cp .env.example .env

# Uzupełnij klucze API w .env:
# - ANTHROPIC_API_KEY (wymagany)
# - GITHUB_TOKEN (wymagany)
# - RAILWAY_TOKEN / VERCEL_TOKEN / RENDER_API_KEY (jeden z nich)
```

### 2. Uruchomienie z Docker

```bash
# Podstawowe uruchomienie
docker-compose up -d

# Z LiteLLM proxy
docker-compose --profile full up -d
```

### 3. Uruchomienie lokalne (development)

```bash
# Instalacja zależności
pip install -r requirements.txt

# Uruchomienie
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Testowanie

Otwórz w przeglądarce:
- **API Docs**: http://localhost:8000/docs
- **Chat UI**: http://localhost:8000/chat/{project_id}

## 📡 API Endpoints

### REST API

| Endpoint | Method | Opis |
|----------|--------|------|
| `/` | GET | Status platformy |
| `/health` | GET | Health check |
| `/projects` | POST | Utwórz nowy projekt |
| `/projects/{id}` | GET | Status projektu |
| `/projects/{id}/github` | POST | Utwórz repo GitHub |
| `/projects/{id}/deploy` | POST | Wdróż projekt |
| `/components` | GET | Lista komponentów |
| `/components/search` | GET | Szukaj komponentów |
| `/pricing` | GET | Cennik |

### WebSocket

```javascript
// Połączenie
const ws = new WebSocket('ws://localhost:8000/ws/{project_id}');

// Wysyłanie wiadomości
ws.send(JSON.stringify({
  type: 'message',
  content: 'Stwórz API do zarządzania zadaniami'
}));

// Odbieranie odpowiedzi (streaming)
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: 'response_chunk', 'progress', 'tool', 'system'
};
```

## 📦 Biblioteka komponentów

Wbudowane reużywalne moduły:

| ID | Nazwa | Kategoria |
|----|-------|-----------|
| `auth-fastapi-jwt` | JWT Authentication | Auth |
| `db-sqlalchemy-base` | SQLAlchemy Setup | Database |
| `api-crud-base` | Generic CRUD | API |
| `integration-stripe` | Stripe Payments | Integration |
| `ui-react-dashboard` | Dashboard Layout | UI |
| `utils-logger` | Structured Logger | Utils |

## 💰 Cennik (PLN)

| Pakiet | Cena | Max tokens | Max plików |
|--------|------|------------|------------|
| 1h | 150 | 50,000 | 5 |
| 8h | 1,200 | 400,000 | 20 |
| 24h | 3,000 | 1,200,000 | 50 |
| 36h | 3,600 | 1,800,000 | 75 |
| 48h | 4,800 | 2,400,000 | 100 |
| 72h | 7,200 | 3,600,000 | 150 |

## 🔧 Konfiguracja

### Zmienne środowiskowe

```bash
# Wymagane
ANTHROPIC_API_KEY=sk-ant-...     # Klucz API Anthropic
GITHUB_TOKEN=ghp_...              # Personal Access Token GitHub

# Deployment (minimum jeden)
RAILWAY_TOKEN=...                 # Token Railway
VERCEL_TOKEN=...                  # Token Vercel
RENDER_API_KEY=...                # API Key Render

# Opcjonalne
OPENAI_API_KEY=sk-...             # Fallback LLM
DATABASE_URL=postgresql+asyncpg://... 
REDIS_URL=redis://...
```

## 📚 Workflow klienta

```
1. Klient tworzy projekt (POST /projects)
   ↓
2. Klient opisuje wymagania w chacie (WebSocket)
   ↓
3. AI analizuje wymagania i proponuje rozwiązanie
   ↓
4. AI szuka gotowych komponentów w bibliotece
   ↓
5. AI generuje brakujący kod
   ↓
6. AI tworzy repozytorium GitHub
   ↓
7. AI wdraża projekt na wybranej platformie
   ↓
8. Klient otrzymuje link do działającego rozwiązania
```

## 🧪 Testowanie

```bash
# Testy jednostkowe
pytest tests/ -v

# Testy z coverage
pytest tests/ --cov=src --cov-report=html
```

## 📄 Licencja

Proprietary - © 2024 prototypowanie.pl / Softreck

## 🤝 Kontakt

- **Web**: https://prototypowanie.pl
- **Email**: kontakt@prototypowanie.pl
- **GitHub**: https://github.com/prototypowanie-pl
