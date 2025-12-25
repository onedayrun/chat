"""
OneDay.run Platform - Main Application
FastAPI application with WebSocket support for real-time chat
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from config.settings import settings
from src.agents.orchestrator import OrchestratorAgent, ProjectContext, ProjectPhase
from src.services.github_service import GitHubService
from src.services.deployment_service import deployment_manager
from src.components.library import component_library


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
    
    def disconnect(self, project_id: str):
        if project_id in self.active_connections:
            del self.active_connections[project_id]
    
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
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📦 Components loaded: {len(component_library.components)}")
    print(f"🌐 Deployment platforms: {deployment_manager.get_available_platforms()}")
    yield
    # Shutdown
    print("👋 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Platforma LLM do automatycznej realizacji zamówień prototypowania w czasie rzeczywistym",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# Project Management
@app.post("/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    github: GitHubService = Depends(get_github_service)
):
    """Tworzy nowy projekt i rozpoczyna sesję"""
    project_id = str(uuid.uuid4())[:8]
    
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
            
            if data.get("type") == "message":
                user_message = data.get("content", "")
                
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
        await websocket.send_json({
            "type": "error",
            "content": str(e)
        })
        manager.disconnect(project_id)


# Simple chat UI for testing
@app.get("/chat/{project_id}", response_class=HTMLResponse)
async def chat_ui(project_id: str):
    """Simple chat UI for testing"""
    return f"""
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
        .message pre {{ background: #0d0d0d; padding: 10px; border-radius: 5px; overflow-x: auto; margin-top: 10px; }}
        .message code {{ font-family: 'Fira Code', monospace; font-size: 0.9rem; }}
        .input-area {{ background: #16213e; padding: 20px; border-top: 1px solid #0f3460; }}
        .input-area form {{ display: flex; gap: 10px; }}
        .input-area input {{ flex: 1; padding: 15px; border: none; border-radius: 10px; background: #0f3460; color: #eee; font-size: 1rem; }}
        .input-area button {{ padding: 15px 30px; background: #e94560; border: none; border-radius: 10px; color: #fff; font-weight: bold; cursor: pointer; }}
        .input-area button:hover {{ background: #ff6b6b; }}
        .progress {{ background: #0f3460; padding: 10px; border-radius: 5px; margin-top: 10px; font-size: 0.8rem; }}
        .typing {{ color: #888; font-style: italic; }}
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
        
        let ws;
        let currentResponse = null;
        
        function connect() {{
            ws = new WebSocket(`ws://${{window.location.host}}/ws/${{projectId}}`);
            
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
                        currentResponse.innerHTML += escapeHtml(data.content);
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }}
                    break;
                case 'response_end':
                    currentResponse = null;
                    break;
                case 'typing':
                    // Show typing indicator
                    break;
                case 'progress':
                    addProgress(data.data);
                    break;
                case 'error':
                    addMessage('❌ ' + data.content, 'system');
                    break;
            }}
        }}
        
        function addMessage(content, type) {{
            const div = document.createElement('div');
            div.className = `message ${{type}}`;
            div.innerHTML = formatContent(content);
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            return div;
        }}
        
        function addProgress(progress) {{
            const existing = document.querySelector('.progress-display');
            if (existing) existing.remove();
            
            const div = document.createElement('div');
            div.className = 'progress progress-display';
            div.innerHTML = `
                <strong>Progress:</strong> ${{progress.progress_percent || 0}}% | 
                <strong>Phase:</strong> ${{progress.current_phase || 'discovery'}} | 
                <strong>Files:</strong> ${{progress.files_generated || 0}} |
                <strong>Tokens:</strong> ${{Math.round(progress.tokens_used || 0)}}
                ${{progress.github_repo ? `| <strong>Repo:</strong> ${{progress.github_repo}}` : ''}}
                ${{progress.deployment_url ? `| <a href="${{progress.deployment_url}}" target="_blank" style="color:#e94560">🌐 Live</a>` : ''}}
            `;
            messagesDiv.appendChild(div);
        }}
        
        function formatContent(content) {{
            // Format code blocks
            return content.replace(/```(\\w+)?\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>');
        }}
        
        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
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
    uvicorn.run(app, host="0.0.0.0", port=8003)
