"""
OneDay.run Platform - Main Application
FastAPI application with WebSocket support for real-time chat
"""
import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from config.settings import settings
from src.agents.orchestrator import OrchestratorAgent, ProjectContext, ProjectPhase
from src.services.github_service import GitHubService
from src.services.deployment_service import deployment_manager
from src.components.library import component_library


def _coerce_log_level(value: Any) -> int:
    if isinstance(value, str) and value:
        return getattr(logging, value.upper(), logging.INFO)
    return logging.INFO


logging.basicConfig(
    level=_coerce_log_level(os.environ.get("LOG_LEVEL") or getattr(settings, "LOG_LEVEL", None)),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("onedayrun")


# Models
class ProjectCreate(BaseModel):
    client_name: str
    tier: str = Field(..., pattern="^(1h|8h|24h|36h|48h|72h)$")
    initial_message: str
    tech_stack: Optional[str] = None
    project_type: Optional[str] = None


class ChatMessage(BaseModel):
    message: str


class ProjectResponse(BaseModel):
    project_id: str
    status: str
    phase: str
    github_repo: Optional[str] = None
    deployment_url: Optional[str] = None


# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.projects: Dict[str, OrchestratorAgent] = {}
    
    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        self.active_connections[project_id] = websocket
        logger.info("ws_connected project_id=%s", project_id)
    
    def disconnect(self, project_id: str):
        if project_id in self.active_connections:
            del self.active_connections[project_id]
        logger.info("ws_disconnected project_id=%s", project_id)
    
    async def send_message(self, project_id: str, message: dict):
        if project_id in self.active_connections:
            await self.active_connections[project_id].send_json(message)
    
    async def broadcast_progress(self, project_id: str, progress: dict):
        await self.send_message(project_id, {
            "type": "progress",
            "data": progress
        })


manager = ConnectionManager()


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("startup app=%s version=%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("startup components_loaded=%s", len(component_library.components))
    logger.info("startup deployment_platforms=%s", deployment_manager.get_available_platforms())
    yield
    # Shutdown
    logger.info("shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Platforma LLM do automatycznej realizacji zamówień prototypowania w czasie rzeczywistym",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS


def _parse_csv(value: Any) -> List[str]:
    if value is None:
        return ["*"]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if not isinstance(value, str):
        # e.g. tests may patch settings with Mock() objects
        return ["*"]

    v = value.strip()
    if not v or v == "*":
        return ["*"]
    return [part.strip() for part in v.split(",") if part.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_csv(settings.CORS_ALLOW_ORIGINS),
    allow_credentials=bool(settings.CORS_ALLOW_CREDENTIALS),
    allow_methods=_parse_csv(settings.CORS_ALLOW_METHODS),
    allow_headers=_parse_csv(settings.CORS_ALLOW_HEADERS),
)


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.exception(
            "http_error method=%s path=%s duration_ms=%s",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "http_request method=%s path=%s status=%s duration_ms=%s",
        request.method,
        request.url.path,
        getattr(response, "status_code", None),
        duration_ms,
    )
    return response


# Dependencies
def get_github_service() -> GitHubService:
    return GitHubService()


# Routes
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "features": {
            "real_time_chat": True,
            "github_integration": bool(settings.GITHUB_TOKEN),
            "deployment_platforms": deployment_manager.get_available_platforms(),
            "component_library": len(component_library.components)
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


# Project Management
@app.post("/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    github: GitHubService = Depends(get_github_service)
):
    """Tworzy nowy projekt i rozpoczyna sesję"""
    project_id = str(uuid.uuid4())[:8]

    logger.info(
        "project_create project_id=%s client_name=%s tier=%s",
        project_id,
        project.client_name,
        project.tier,
    )
    
    # Initialize orchestrator
    services = {
        "github": github,
        "components": component_library,
        "deployers": {
            "railway": deployment_manager.deployers.get("railway"),
            "vercel": deployment_manager.deployers.get("vercel"),
            "render": deployment_manager.deployers.get("render"),
        }
    }
    
    agent = OrchestratorAgent(services)
    context = await agent.start_project(
        project_id=project_id,
        client_name=project.client_name,
        tier=project.tier,
        initial_message=project.initial_message
    )
    
    # Set optional fields
    if project.tech_stack:
        context.tech_stack = project.tech_stack
    if project.project_type:
        context.project_type = project.project_type
    
    # Store agent
    manager.projects[project_id] = agent
    
    return ProjectResponse(
        project_id=project_id,
        status="created",
        phase=context.current_phase.value
    )


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Pobiera status projektu"""
    agent = manager.projects.get(project_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return agent.get_progress()


@app.post("/projects/{project_id}/github")
async def setup_github(
    project_id: str,
    repo_name: str,
    github: GitHubService = Depends(get_github_service)
):
    """Tworzy repozytorium GitHub dla projektu"""
    agent = manager.projects.get(project_id)
    if not agent or not agent.context:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create repo
    result = await github.setup_project_from_template(
        project_name=repo_name,
        tech_stack=agent.context.tech_stack or "python_fastapi",
        description=f"Project generated by OneDay.run - {agent.context.tier} package"
    )
    
    if result["success"]:
        agent.context.github_repo = result["repo_name"]
        return result
    
    raise HTTPException(status_code=400, detail=result.get("error", "Failed to create repo"))


@app.post("/projects/{project_id}/deploy")
async def deploy_project(
    project_id: str,
    platform: str = "railway"
):
    """Wdraża projekt na wybranej platformie"""
    agent = manager.projects.get(project_id)
    if not agent or not agent.context:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not agent.context.github_repo:
        raise HTTPException(status_code=400, detail="No GitHub repo configured")
    
    result = await deployment_manager.deploy(
        platform=platform,
        repo=agent.context.github_repo,
        config={"env": {}}
    )
    
    if result.success:
        agent.context.deployment_url = result.url
        agent.context.deployment_platform = platform
    
    return result.to_dict()


# Components API
@app.get("/components")
async def list_components(category: Optional[str] = None):
    """Lista dostępnych komponentów"""
    if category:
        return {"components": component_library.list_by_category(category)}
    return {"categories": component_library.list_categories()}


@app.get("/components/search")
async def search_components(
    q: str,
    category: Optional[str] = None,
    tech_stack: Optional[str] = None
):
    """Szuka komponentów"""
    return await component_library.search(
        query=q,
        category=category,
        tech_stack=tech_stack
    )


# Pricing
@app.get("/pricing")
async def get_pricing():
    """Zwraca cennik"""
    return {
        "tiers": settings.PRICING_TIERS,
        "currency": "PLN",
        "includes": {
            "all": ["GitHub repo", "Documentation", "3 months warranty"],
            "8h+": ["Deployment included", "Basic testing"],
            "24h+": ["Extended testing", "Performance optimization"],
            "48h+": ["Security audit", "Multi-environment deployment"]
        }
    }


# WebSocket Chat
@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """
    WebSocket endpoint dla real-time chatu z AI
    
    Protokół:
    - Client wysyła: {"type": "message", "content": "..."}
    - Server odpowiada: {"type": "response", "content": "...", "streaming": true/false}
    - Server wysyła progress: {"type": "progress", "data": {...}}
    - Server wysyła tool calls: {"type": "tool", "name": "...", "status": "..."}
    """
    await manager.connect(websocket, project_id)
    
    agent = manager.projects.get(project_id)
    if not agent:
        logger.warning("ws_project_not_found project_id=%s", project_id)
        await websocket.send_json({
            "type": "error",
            "content": "Project not found. Create a project first via POST /projects"
        })
        await websocket.close()
        return
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "system",
            "content": f"🚀 Witaj w OneDay.run! Projekt {project_id} gotowy. Opisz co chcesz zbudować.",
            "project": agent.get_progress()
        })
        
        while True:
            # Receive message
            data = await websocket.receive_json()
            logger.info("ws_message_received project_id=%s type=%s", project_id, data.get("type"))
            
            if data.get("type") == "message":
                user_message = data.get("content", "")

                logger.info(
                    "ws_user_message project_id=%s chars=%s",
                    project_id,
                    len(user_message or ""),
                )
                
                # Send typing indicator
                await websocket.send_json({
                    "type": "typing",
                    "content": True
                })
                
                # Stream response
                await websocket.send_json({
                    "type": "response_start"
                })
                
                full_response = ""
                async for chunk in agent.chat(user_message, stream=True):
                    full_response += chunk
                    await websocket.send_json({
                        "type": "response_chunk",
                        "content": chunk
                    })
                
                await websocket.send_json({
                    "type": "response_end",
                    "full_content": full_response
                })
                
                # Send updated progress
                await websocket.send_json({
                    "type": "progress",
                    "data": agent.get_progress()
                })
            
            elif data.get("type") == "command":
                # Handle special commands
                command = data.get("command")
                
                if command == "status":
                    await websocket.send_json({
                        "type": "status",
                        "data": agent.get_progress()
                    })
                
                elif command == "components":
                    query = data.get("query", "")
                    results = await component_library.search(query)
                    await websocket.send_json({
                        "type": "components",
                        "data": results
                    })
                
                elif command == "deploy":
                    platform = data.get("platform", "railway")
                    if agent.context and agent.context.github_repo:
                        result = await deployment_manager.deploy(
                            platform=platform,
                            repo=agent.context.github_repo
                        )
                        await websocket.send_json({
                            "type": "deployment",
                            "data": result.to_dict()
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "content": "No GitHub repo configured"
                        })
    
    except WebSocketDisconnect:
        manager.disconnect(project_id)
    except Exception as e:
        logger.exception("ws_error project_id=%s", project_id)
        await websocket.send_json({
            "type": "error",
            "content": str(e)
        })
        manager.disconnect(project_id)


# Simple chat UI for testing
@app.get("/chat", response_class=HTMLResponse)
@app.get("/chat/", response_class=HTMLResponse)
async def chat_create_ui():
    return r"""
<!DOCTYPE html>
<html>
<head>
    <title>OneDay.run - Create Project</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; }
        .container { max-width: 900px; margin: 0 auto; height: 100vh; display: flex; flex-direction: column; }
        .header { background: #16213e; padding: 20px; border-bottom: 1px solid #0f3460; }
        .header h1 { color: #e94560; font-size: 1.5rem; }
        .header .status { font-size: 0.9rem; margin-top: 5px; }
        .content { flex: 1; padding: 20px; }
        .card { background: #16213e; border: 1px solid #0f3460; border-radius: 10px; padding: 20px; }
        label { display: block; font-size: 0.9rem; margin-top: 12px; margin-bottom: 6px; color: #ccc; }
        input, select, textarea { width: 100%; padding: 12px; border: none; border-radius: 10px; background: #0f3460; color: #eee; font-size: 1rem; }
        textarea { min-height: 140px; resize: vertical; }
        .actions { display: flex; gap: 10px; margin-top: 16px; }
        button { padding: 12px 18px; background: #e94560; border: none; border-radius: 10px; color: #fff; font-weight: bold; cursor: pointer; }
        button:hover { background: #ff6b6b; }
        .muted { color: #aaa; font-size: 0.9rem; margin-top: 10px; }
        .error { margin-top: 12px; padding: 12px; border-radius: 10px; background: #1a1a2e; border: 1px solid #e94560; display: none; }
        a { color: #e94560; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 OneDay.run Platform</h1>
            <div class="status" id="status">Create a project to start chatting</div>
        </div>
        <div class="content">
            <div class="card">
                <form id="form">
                    <label for="client_name">Client name</label>
                    <input id="client_name" name="client_name" type="text" value="tom" required />

                    <label for="tier">Tier</label>
                    <select id="tier" name="tier" required>
                        <option value="1h">1h</option>
                        <option value="8h">8h</option>
                        <option value="24h">24h</option>
                        <option value="36h">36h</option>
                        <option value="48h">48h</option>
                        <option value="72h">72h</option>
                    </select>

                    <label for="initial_message">Initial message</label>
                    <textarea id="initial_message" name="initial_message" placeholder="Opisz co chcesz zbudować..." required></textarea>

                    <div class="actions">
                        <button type="submit" id="submit">Create & Open Chat</button>
                        <button type="button" id="openDocs">Open API Docs</button>
                    </div>

                    <div class="muted">
                        This page calls <code>POST /projects</code> and redirects to <code>/chat/&lt;project_id&gt;</code>.
                    </div>
                    <div class="error" id="error"></div>
                </form>
            </div>
        </div>
    </div>

    <script>
        const form = document.getElementById('form');
        const submitBtn = document.getElementById('submit');
        const openDocsBtn = document.getElementById('openDocs');
        const statusDiv = document.getElementById('status');
        const errorDiv = document.getElementById('error');

        function showError(message) {
            errorDiv.style.display = 'block';
            errorDiv.textContent = message;
        }

        openDocsBtn.onclick = () => {
            window.location.href = '/docs';
        };

        form.onsubmit = async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';

            const clientName = document.getElementById('client_name').value.trim();
            const tier = document.getElementById('tier').value;
            const initialMessage = document.getElementById('initial_message').value.trim();

            if (!clientName || !tier || !initialMessage) {
                showError('Please fill all fields.');
                return;
            }

            submitBtn.disabled = true;
            statusDiv.textContent = 'Creating project...';

            try {
                const res = await fetch('/projects', {
                    method: 'POST',
                    headers: { 'content-type': 'application/json' },
                    body: JSON.stringify({
                        client_name: clientName,
                        tier: tier,
                        initial_message: initialMessage
                    })
                });

                if (!res.ok) {
                    const text = await res.text();
                    throw new Error(text || `HTTP ${res.status}`);
                }

                const data = await res.json();
                if (!data.project_id) {
                    throw new Error('Missing project_id in response');
                }

                statusDiv.textContent = 'Project created. Redirecting...';
                window.location.href = `/chat/${data.project_id}`;
            } catch (err) {
                showError(String(err));
                statusDiv.textContent = 'Failed to create project';
            } finally {
                submitBtn.disabled = false;
            }
        };
    </script>
</body>
</html>
"""

@app.get("/chat/{project_id}", response_class=HTMLResponse)
@app.get("/chat/{project_id}/", response_class=HTMLResponse)
async def chat_ui(project_id: str):
    """Simple chat UI for testing"""
    if project_id not in manager.projects:
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>OneDay.run - Project not found</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 900px; margin: 0 auto; height: 100vh; display: flex; flex-direction: column; }}
        .header {{ background: #16213e; padding: 20px; border-bottom: 1px solid #0f3460; }}
        .header h1 {{ color: #e94560; font-size: 1.5rem; }}
        .content {{ flex: 1; padding: 20px; }}
        .card {{ background: #16213e; border: 1px solid #e94560; border-radius: 10px; padding: 20px; }}
        a {{ color: #e94560; }}
        code {{ font-family: 'Fira Code', monospace; font-size: 0.95rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 OneDay.run Platform</h1>
        </div>
        <div class="content">
            <div class="card">
                <h2 style="margin-bottom: 10px;">❌ Project not found</h2>
                <div style="margin-bottom: 12px; color: #ccc;">
                    Project ID: <code>{project_id}</code>
                </div>
                <div style="margin-bottom: 12px; color: #ccc;">
                    Ten serwer trzyma projekty w pamięci. Najpierw utwórz projekt przez Web UI:
                    <a href="/chat">/chat</a>
                    albo przez <a href="/docs">/docs</a> (POST <code>/projects</code>).
                </div>
                <div style="color: #aaa;">
                    Po utworzeniu projektu dostaniesz prawidłowe <code>project_id</code> i wtedy dopiero działa <code>/chat/&lt;project_id&gt;</code>.
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    return fr"""
<!DOCTYPE html>
<html>
<head>
    <title>OneDay.run Chat - {project_id}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 900px; margin: 0 auto; height: 100vh; display: flex; flex-direction: column; }}
        .header {{ background: #16213e; padding: 20px; border-bottom: 1px solid #0f3460; }}
        .header h1 {{ color: #e94560; font-size: 1.5rem; }}
        .header .status {{ color: #0f0; font-size: 0.8rem; margin-top: 5px; }}
        .messages {{ flex: 1; overflow-y: auto; padding: 20px; }}
        .message {{ margin-bottom: 15px; padding: 15px; border-radius: 10px; max-width: 80%; }}
        .message.user {{ background: #0f3460; margin-left: auto; }}
        .message.assistant {{ background: #16213e; border: 1px solid #0f3460; }}
        .message.system {{ background: #1a1a2e; border: 1px solid #e94560; text-align: center; max-width: 100%; }}
        .message.meta {{ background: #16213e; border: 1px dashed #0f3460; max-width: 100%; }}
        .message.deployment {{ background: #16213e; border: 1px solid #22c55e; max-width: 100%; }}
        .message pre {{ background: #0d0d0d; padding: 10px; border-radius: 5px; overflow-x: auto; margin: 10px 0; }}
        .message code {{ font-family: 'Fira Code', monospace; font-size: 0.9rem; }}
        .message .msg-body {{ line-height: 1.5; }}
        .message .msg-body p {{ margin: 0 0 12px 0; }}
        .message .msg-body p:last-child {{ margin-bottom: 0; }}
        .message .msg-body h1, .message .msg-body h2, .message .msg-body h3 {{ margin: 12px 0 10px; color: #fff; }}
        .message .msg-body h1 {{ font-size: 1.1rem; }}
        .message .msg-body h2 {{ font-size: 1.0rem; }}
        .message .msg-body h3 {{ font-size: 0.95rem; }}
        .message .msg-body ul, .message .msg-body ol {{ margin: 0 0 12px 20px; padding: 0; }}
        .message .msg-body li {{ margin: 4px 0; }}
        .message .msg-body blockquote {{ margin: 10px 0; padding-left: 12px; border-left: 3px solid #0f3460; color: #cbd5e1; }}
        .message .msg-body a {{ color: #e94560; text-decoration: underline; }}
        .message .msg-body code {{ background: #0d0d0d; border: 1px solid #0f3460; padding: 2px 6px; border-radius: 6px; }}
        .input-area {{ background: #16213e; padding: 20px; border-top: 1px solid #0f3460; }}
        .input-area form {{ display: flex; gap: 10px; }}
        .input-area input {{ flex: 1; padding: 15px; border: none; border-radius: 10px; background: #0f3460; color: #eee; font-size: 1rem; }}
        .input-area button {{ padding: 15px 30px; background: #e94560; border: none; border-radius: 10px; color: #fff; font-weight: bold; cursor: pointer; }}
        .input-area button:hover {{ background: #ff6b6b; }}
        .input-area button.btn-icon {{ padding: 15px 16px; min-width: 54px; }}
        .progress {{ background: #0f3460; padding: 10px; border-radius: 5px; margin-top: 10px; font-size: 0.8rem; }}
        .typing {{ color: #888; font-style: italic; }}
        .msg-controls {{ display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 6px; }}
        .msg-controls button {{ background: transparent; border: 1px solid #0f3460; color: #eee; padding: 6px 8px; border-radius: 8px; cursor: pointer; }}
        .msg-controls button:hover {{ border-color: #e94560; color: #e94560; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 OneDay.run Platform</h1>
            <div class="status" id="status">Connecting...</div>
        </div>
        <div class="messages" id="messages"></div>
        <div class="input-area">
            <form id="form">
                <button type="button" id="micBtn" class="btn-icon">🎤</button>
                <button type="button" id="ttsToggleBtn" class="btn-icon">🔊</button>
                <input type="text" id="input" placeholder="Opisz co chcesz zbudować..." autocomplete="off" />
                <button type="submit">Wyślij</button>
            </form>
        </div>
    </div>
    <script>
        const projectId = "{project_id}";
        const messagesDiv = document.getElementById('messages');
        const form = document.getElementById('form');
        const input = document.getElementById('input');
        const statusDiv = document.getElementById('status');
        const enableSTT = {str(settings.UI_ENABLE_STT).lower()};
        const enableTTS = {str(settings.UI_ENABLE_TTS).lower()};
        const micBtn = document.getElementById('micBtn');
        const ttsToggleBtn = document.getElementById('ttsToggleBtn');
        
        let ws;
        let currentResponse = null;
        let ttsEnabled = enableTTS;
        let recognition = null;

        function setButtonVisibility() {{
            if (micBtn) micBtn.style.display = enableSTT ? '' : 'none';
            if (ttsToggleBtn) ttsToggleBtn.style.display = enableTTS ? '' : 'none';
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function applyInlineMarkdown(escapedText) {{
            let html = String(escapedText || '');

            const codeSpans = [];
            html = html.replace(/`([^`]+)`/g, (match, code) => {{
                const idx = codeSpans.length;
                codeSpans.push('<code>' + code + '</code>');
                return '@@CODE' + idx + '@@';
            }});

            html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

            html = html.replace(/@@CODE(\d+)@@/g, (match, idx) => {{
                return codeSpans[Number(idx)] || match;
            }});
            return html;
        }}

        function renderInline(text) {{
            const escaped = escapeHtml(String(text || ''));
            return applyInlineMarkdown(escaped).replace(/\n/g, '<br>');
        }}

        function renderMarkdownBlock(text) {{
            const raw = String(text || '').replace(/\r\n/g, '\n');
            const lines = raw.split('\n');

            const out = [];
            let inUl = false;
            let inOl = false;
            let inBlockquote = false;
            let paragraph = [];

            function flushParagraph() {{
                const content = paragraph.join(' ').trim();
                if (!content) {{
                    paragraph = [];
                    return;
                }}
                const escaped = escapeHtml(content);
                out.push('<p>' + applyInlineMarkdown(escaped) + '</p>');
                paragraph = [];
            }}

            function closeLists() {{
                if (inUl) {{
                    out.push('</ul>');
                    inUl = false;
                }}
                if (inOl) {{
                    out.push('</ol>');
                    inOl = false;
                }}
            }}

            function closeBlockquote() {{
                if (!inBlockquote) return;
                flushParagraph();
                out.push('</blockquote>');
                inBlockquote = false;
            }}

            for (const line of lines) {{
                const trimmed = line.trim();

                if (!trimmed) {{
                    flushParagraph();
                    closeLists();
                    continue;
                }}

                const heading = trimmed.match(/^(#{{1,3}})\s+(.*)$/);
                if (heading) {{
                    closeBlockquote();
                    flushParagraph();
                    closeLists();
                    const level = heading[1].length;
                    const content = applyInlineMarkdown(escapeHtml(heading[2] || ''));
                    out.push('<h' + level + '>' + content + '</h' + level + '>');
                    continue;
                }}

                const bq = trimmed.match(/^>\s+(.*)$/);
                if (bq) {{
                    flushParagraph();
                    closeLists();
                    if (!inBlockquote) {{
                        out.push('<blockquote>');
                        inBlockquote = true;
                    }}
                    paragraph.push(bq[1]);
                    continue;
                }}

                if (inBlockquote) {{
                    closeBlockquote();
                }}

                const ul = trimmed.match(/^[-*]\s+(.*)$/);
                if (ul) {{
                    flushParagraph();
                    if (inOl) {{
                        out.push('</ol>');
                        inOl = false;
                    }}
                    if (!inUl) {{
                        out.push('<ul>');
                        inUl = true;
                    }}
                    out.push('<li>' + applyInlineMarkdown(escapeHtml(ul[1] || '')) + '</li>');
                    continue;
                }}

                const ol = trimmed.match(/^\d+\.\s+(.*)$/);
                if (ol) {{
                    flushParagraph();
                    if (inUl) {{
                        out.push('</ul>');
                        inUl = false;
                    }}
                    if (!inOl) {{
                        out.push('<ol>');
                        inOl = true;
                    }}
                    out.push('<li>' + applyInlineMarkdown(escapeHtml(ol[1] || '')) + '</li>');
                    continue;
                }}

                if (inUl || inOl) {{
                    closeLists();
                }}
                paragraph.push(trimmed);
            }}

            closeBlockquote();
            flushParagraph();
            closeLists();
            return out.join('');
        }}

        function renderContent(text) {{
            const raw = String(text || '');
            const parts = [];
            const re = /```([^\r\n`]*)\r?\n([\s\S]*?)```/g;
            let lastIndex = 0;
            let m;
            while ((m = re.exec(raw)) !== null) {{
                const before = raw.slice(lastIndex, m.index);
                if (before) parts.push(renderMarkdownBlock(before));
                const info = String(m[1] || '').trimEnd();
                const body = m[2] || '';
                const code = info ? (info + '\n' + body) : body;
                parts.push('<pre><code>' + escapeHtml(code) + '</code></pre>');
                lastIndex = re.lastIndex;
            }}
            const tail = raw.slice(lastIndex);
            if (tail) parts.push(renderMarkdownBlock(tail));

            const joined = parts.join('');

            if (raw.includes('"tool"') && raw.includes('{') && raw.includes('}')) {{
                const jsonCandidate = raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1);
                try {{
                    const obj = JSON.parse(jsonCandidate);
                    return joined + '<div class="progress" style="margin-top:10px;"><strong>Tool call:</strong><pre><code>' + escapeHtml(JSON.stringify(obj, null, 2)) + '</code></pre></div>';
                }} catch (e) {{
                    return joined;
                }}
            }}

            return joined;
        }}

        function speakText(text) {{
            if (!ttsEnabled) return;
            if (!('speechSynthesis' in window)) return;
            const utter = new SpeechSynthesisUtterance(String(text || ''));
            utter.lang = 'pl-PL';
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(utter);
        }}

        function stopSpeak() {{
            if (!('speechSynthesis' in window)) return;
            window.speechSynthesis.cancel();
        }}

        function toggleTTS() {{
            ttsEnabled = !ttsEnabled;
            if (!ttsEnabled) stopSpeak();
            if (ttsToggleBtn) ttsToggleBtn.textContent = ttsEnabled ? '🔊' : '🔇';
        }}

        function initSTT() {{
            if (!enableSTT) return;
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {{
                if (micBtn) micBtn.style.display = 'none';
                return;
            }}
            recognition = new SpeechRecognition();
            recognition.lang = 'pl-PL';
            recognition.interimResults = true;
            recognition.continuous = false;

            recognition.onresult = (event) => {{
                let transcript = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {{
                    transcript += event.results[i][0].transcript;
                }}
                input.value = transcript.trim();
            }};
            recognition.onend = () => {{
                if (micBtn) micBtn.textContent = '🎤';
            }};
            recognition.onerror = () => {{
                if (micBtn) micBtn.textContent = '🎤';
            }};
        }}

        function toggleSTT() {{
            if (!recognition) return;
            try {{
                if (micBtn && micBtn.textContent === '⏹') {{
                    recognition.stop();
                    micBtn.textContent = '🎤';
                }} else {{
                    if (micBtn) micBtn.textContent = '⏹';
                    recognition.start();
                }}
            }} catch (e) {{
                if (micBtn) micBtn.textContent = '🎤';
            }}
        }}

        setButtonVisibility();
        if (enableTTS && ttsToggleBtn) {{
            ttsToggleBtn.onclick = toggleTTS;
            ttsToggleBtn.textContent = ttsEnabled ? '🔊' : '🔇';
        }}
        if (enableSTT && micBtn) {{
            initSTT();
            micBtn.onclick = toggleSTT;
        }}
        
        function connect() {{
            const scheme = (window.location.protocol === 'https:') ? 'wss://' : 'ws://';
            ws = new WebSocket(scheme + window.location.host + '/ws/' + projectId);
            
            ws.onopen = () => {{
                statusDiv.textContent = '🟢 Connected';
                statusDiv.style.color = '#0f0';
            }};
            
            ws.onclose = () => {{
                statusDiv.textContent = '🔴 Disconnected - Reconnecting...';
                statusDiv.style.color = '#f00';
                setTimeout(connect, 2000);
            }};
            
            ws.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                handleMessage(data);
            }};
        }}
        
        function handleMessage(data) {{
            switch(data.type) {{
                case 'system':
                    addMessage(data.content, 'system');
                    if (data.project) {{
                        addProgress(data.project);
                    }}
                    break;
                case 'response_start':
                    currentResponse = addMessage('', 'assistant');
                    break;
                case 'response_chunk':
                    if (currentResponse) {{
                        currentResponse.raw += String(data.content || '');
                        currentResponse.body.innerHTML = renderInline(currentResponse.raw);
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }}
                    break;
                case 'response_end':
                    if (currentResponse) {{
                        const full = data.full_content || currentResponse.raw;
                        currentResponse.raw = String(full || '');
                        currentResponse.body.innerHTML = renderContent(currentResponse.raw);
                        if (currentResponse.speakBtn) {{
                            currentResponse.speakBtn.onclick = () => speakText(currentResponse.raw);
                        }}
                    }}
                    currentResponse = null;
                    if (ws && ws.readyState === WebSocket.OPEN) {{
                        statusDiv.textContent = '🟢 Connected';
                        statusDiv.style.color = '#0f0';
                    }}
                    break;
                case 'typing':
                    if (data.content) {{
                        statusDiv.textContent = '🟢 Connected (typing...)';
                        statusDiv.style.color = '#0f0';
                    }} else {{
                        statusDiv.textContent = '🟢 Connected';
                        statusDiv.style.color = '#0f0';
                    }}
                    break;
                case 'progress':
                    addProgress(data.data);
                    break;
                case 'status':
                    addProgress(data.data);
                    addMessage(JSON.stringify(data.data, null, 2), 'meta');
                    break;
                case 'components':
                    addMessage(JSON.stringify(data.data, null, 2), 'meta');
                    break;
                case 'deployment':
                    addMessage(JSON.stringify(data.data, null, 2), 'deployment');
                    break;
                case 'error':
                    addMessage('❌ ' + (data.content || ''), 'system');
                    break;
                default:
                    addMessage(JSON.stringify(data, null, 2), 'meta');
                    break;
            }}
        }}

        function addMessage(content, type) {{
            const div = document.createElement('div');
            div.className = 'message ' + String(type || '');

            const controls = document.createElement('div');
            controls.className = 'msg-controls';

            const body = document.createElement('div');
            body.className = 'msg-body';

            const raw = String((content === undefined || content === null) ? '' : content);
            body.innerHTML = renderContent(raw);

            let speakBtn = null;
            if (type === 'assistant' && enableTTS) {{
                speakBtn = document.createElement('button');
                speakBtn.type = 'button';
                speakBtn.textContent = '🔊';
                speakBtn.onclick = () => speakText(raw);
                controls.appendChild(speakBtn);
            }}

            if (controls.childNodes.length) div.appendChild(controls);
            div.appendChild(body);

            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            return {{ root: div, body, raw, speakBtn }};
        }}
        
        function addProgress(progress) {{
            const existing = document.querySelector('.progress-display');
            if (existing) existing.remove();
            
            const div = document.createElement('div');
            div.className = 'progress progress-display';

            const progressPercent = (progress && progress.progress_percent !== undefined && progress.progress_percent !== null) ? progress.progress_percent : 0;
            const phase = (progress && progress.current_phase) ? progress.current_phase : 'discovery';
            const files = (progress && progress.files_generated !== undefined && progress.files_generated !== null) ? progress.files_generated : 0;
            const tokens = Math.round((progress && progress.tokens_used) ? progress.tokens_used : 0);

            const repoPart = (progress && progress.github_repo)
                ? (' | <strong>Repo:</strong> ' + escapeHtml(String(progress.github_repo)))
                : '';

            const livePart = (progress && progress.deployment_url)
                ? (' | <a href="' + escapeHtml(String(progress.deployment_url)) + '" target="_blank" rel="noopener noreferrer" style="color:#e94560">🌐 Live</a>')
                : '';

            div.innerHTML = '<strong>Progress:</strong> ' + progressPercent + '% | '
                + '<strong>Phase:</strong> ' + escapeHtml(String(phase)) + ' | '
                + '<strong>Files:</strong> ' + files + ' | '
                + '<strong>Tokens:</strong> ' + tokens
                + repoPart
                + livePart;
            messagesDiv.appendChild(div);
        }}
        
        // escapeHtml defined above
        
        form.onsubmit = (e) => {{
            e.preventDefault();
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, 'user');
            ws.send(JSON.stringify({{ type: 'message', content: message }}));
            input.value = '';
        }};
        
        connect();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
