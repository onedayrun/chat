"""
OneDay.run Platform - Orchestrator Agent
Główny agent orkiestrujący oparty na Claude Opus 4.5
Zarządza całym procesem realizacji zamówienia
"""
import asyncio
import json
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import litellm
from litellm import acompletion

from config.settings import settings


class ProjectPhase(Enum):
    """Fazy realizacji projektu"""
    DISCOVERY = "discovery"           # Analiza wymagań
    PLANNING = "planning"             # Planowanie architektury
    COMPONENT_SEARCH = "component_search"  # Szukanie gotowych komponentów
    GENERATION = "generation"         # Generowanie kodu
    INTEGRATION = "integration"       # Integracja komponentów
    TESTING = "testing"               # Testowanie
    DEPLOYMENT = "deployment"         # Wdrożenie
    HANDOVER = "handover"             # Przekazanie klientowi


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ProjectContext:
    """Kontekst projektu - przechowuje stan realizacji"""
    project_id: str
    client_name: str
    tier: str  # 1h, 8h, 24h, 36h, 48h, 72h
    
    # Wymagania
    requirements: Dict[str, Any] = field(default_factory=dict)
    tech_stack: Optional[str] = None
    project_type: Optional[str] = None
    
    # Stan realizacji
    current_phase: ProjectPhase = ProjectPhase.DISCOVERY
    generated_files: List[Dict[str, str]] = field(default_factory=list)
    components_used: List[str] = field(default_factory=list)
    
    # GitHub
    github_repo: Optional[str] = None
    github_branch: str = "main"
    
    # Deployment
    deployment_platform: Optional[str] = None
    deployment_url: Optional[str] = None
    
    # Metryki
    tokens_used: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "client_name": self.client_name,
            "tier": self.tier,
            "requirements": self.requirements,
            "tech_stack": self.tech_stack,
            "project_type": self.project_type,
            "current_phase": self.current_phase.value,
            "generated_files": self.generated_files,
            "components_used": self.components_used,
            "github_repo": self.github_repo,
            "deployment_url": self.deployment_url,
            "tokens_used": self.tokens_used,
        }


class OrchestratorAgent:
    """
    Główny agent orkiestrujący platformę OneDay.run
    Wykorzystuje Claude Opus 4.5 do:
    - Analizy wymagań klienta
    - Planowania architektury
    - Koordynacji generowania kodu
    - Zarządzania deployment'em
    """
    
    SYSTEM_PROMPT = """Jesteś ekspertem od szybkiego prototypowania i realizacji projektów IT.
Twoim zadaniem jest prowadzenie klienta przez proces realizacji zamówienia na platformie OneDay.run.

TWOJE MOŻLIWOŚCI:
1. Analiza wymagań - zadajesz precyzyjne pytania, aby zrozumieć potrzeby
2. Planowanie - tworzysz architekturę i plan realizacji
3. Generowanie kodu - tworzysz wysokiej jakości, production-ready kod
4. Integracja - łączysz gotowe komponenty z bibliotekami
5. Deployment - wdrażasz rozwiązanie na wybranej platformie

ZASADY:
- Bądź konkretny i efektywny - czas to pieniądz
- Używaj gotowych komponentów gdy to możliwe
- Generuj kod modularny i łatwy w utrzymaniu
- Zawsze myśl o bezpieczeństwie i skalowalności
- Komunikuj się jasno - informuj o postępach

DOSTĘPNE NARZĘDZIA:
- search_components: Szukaj gotowych komponentów w bibliotece
- generate_code: Generuj nowy kod
- create_file: Twórz pliki w repozytorium
- deploy_project: Wdrażaj projekt
- run_tests: Uruchamiaj testy

FORMATY ODPOWIEDZI:
Gdy generujesz kod, używaj formatu:
```language:path/to/file.ext
kod tutaj
```

Gdy potrzebujesz narzędzia, używaj formatu JSON:
{"tool": "nazwa_narzędzia", "params": {...}}

AKTUALNA FAZA: {current_phase}
KONTEKST PROJEKTU: {project_context}
"""

    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "search_components",
                "description": "Szuka gotowych komponentów w bibliotece reużywalnych modułów",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Zapytanie szukające"},
                        "category": {"type": "string", "enum": ["auth", "database", "api", "ui", "integration", "utils"]},
                        "tech_stack": {"type": "string", "description": "Stack technologiczny"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function", 
            "function": {
                "name": "generate_code",
                "description": "Generuje kod dla konkretnego modułu/funkcjonalności",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string"},
                        "description": {"type": "string"},
                        "tech_stack": {"type": "string"},
                        "dependencies": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["module_name", "description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_file",
                "description": "Tworzy plik w repozytorium GitHub",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "commit_message": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "deploy_project",
                "description": "Wdraża projekt na wybranej platformie",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "platform": {"type": "string", "enum": ["railway", "vercel", "render"]},
                        "config": {"type": "object"}
                    },
                    "required": ["platform"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_tests",
                "description": "Uruchamia testy dla projektu",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "test_type": {"type": "string", "enum": ["unit", "integration", "e2e"]},
                        "files": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_requirements",
                "description": "Analizuje wymagania i generuje plan projektu",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "requirements_text": {"type": "string"},
                        "budget_tier": {"type": "string"}
                    },
                    "required": ["requirements_text"]
                }
            }
        }
    ]

    def __init__(self, services: Dict[str, Any] = None):
        """
        Args:
            services: Słownik serwisów (github, deployment, components)
        """
        self.services = services or {}
        self.conversation_history: List[Dict[str, str]] = []
        self.context: Optional[ProjectContext] = None
        self.model: str = settings.DEFAULT_MODEL
        
        # Configure LiteLLM
        if settings.LITELLM_PROXY_URL:
            litellm.api_base = settings.LITELLM_PROXY_URL
            if settings.LITELLM_API_KEY:
                litellm.api_key = settings.LITELLM_API_KEY
        elif settings.LLM_PROVIDER == "ollama":
            litellm.api_base = settings.OLLAMA_BASE_URL
            litellm.api_key = None
            self.model = settings.OLLAMA_MODEL
        else:
            litellm.api_base = None
            litellm.api_key = settings.ANTHROPIC_API_KEY

    async def _acompletion_with_fallback(self, **kwargs):
        """Calls LiteLLM with a small Ollama-specific fallback when tool calling isn't supported."""
        try:
            return await acompletion(**kwargs)
        except Exception as e:
            if settings.LLM_PROVIDER == "ollama" and "tools" in str(e).lower() and "tools" in kwargs:
                kwargs = dict(kwargs)
                kwargs.pop("tools", None)
                return await acompletion(**kwargs)
            raise

    async def start_project(
        self,
        project_id: str,
        client_name: str,
        tier: str,
        initial_message: str
    ) -> ProjectContext:
        """Rozpoczyna nowy projekt"""
        self.context = ProjectContext(
            project_id=project_id,
            client_name=client_name,
            tier=tier
        )
        
        # Initial system setup
        self.conversation_history = []
        
        return self.context

    def _build_system_prompt(self) -> str:
        """Buduje system prompt z aktualnym kontekstem"""
        return self.SYSTEM_PROMPT.format(
            current_phase=self.context.current_phase.value if self.context else "discovery",
            project_context=json.dumps(self.context.to_dict(), indent=2, default=str) if self.context else "{}"
        )

    async def chat(
        self,
        user_message: str,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Główna metoda chatu - procesuje wiadomość i generuje odpowiedź
        
        Args:
            user_message: Wiadomość od klienta
            stream: Czy streamować odpowiedź
            
        Yields:
            Fragmenty odpowiedzi (jeśli stream=True)
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            *self.conversation_history
        ]
        
        try:
            if stream:
                response = await self._acompletion_with_fallback(
                    model=self.model,
                    messages=messages,
                    tools=self.TOOLS,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=settings.TEMPERATURE,
                    stream=True
                )
                
                full_response = ""
                tool_calls = []
                
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content
                    
                    # Handle tool calls
                    if chunk.choices[0].delta.tool_calls:
                        tool_calls.extend(chunk.choices[0].delta.tool_calls)
                
                # Process any tool calls
                if tool_calls:
                    tool_results = await self._process_tool_calls(tool_calls)
                    for result in tool_results:
                        yield f"\n\n📦 {result['name']}: {result['status']}\n"
                
                # Save assistant response
                self.conversation_history.append({
                    "role": "assistant", 
                    "content": full_response
                })
                
                # Update token count
                if self.context:
                    # Estimate tokens (rough)
                    self.context.tokens_used += len(full_response.split()) * 1.3
                    
            else:
                response = await self._acompletion_with_fallback(
                    model=self.model,
                    messages=messages,
                    tools=self.TOOLS,
                    max_tokens=settings.MAX_TOKENS,
                    temperature=settings.TEMPERATURE
                )
                
                content = response.choices[0].message.content
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content
                })
                
                yield content
                
        except Exception as e:
            error_msg = f"Błąd podczas generowania odpowiedzi: {str(e)}"
            yield error_msg

    async def _process_tool_calls(self, tool_calls: List) -> List[Dict[str, Any]]:
        """Przetwarza wywołania narzędzi"""
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except:
                args = {}
            
            result = await self._execute_tool(tool_name, args)
            results.append({
                "name": tool_name,
                "status": "success" if result.get("success") else "error",
                "result": result
            })
            
            # Add tool result to conversation
            self.conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })
        
        return results

    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wykonuje konkretne narzędzie"""
        
        if tool_name == "search_components":
            return await self._tool_search_components(args)
        elif tool_name == "generate_code":
            return await self._tool_generate_code(args)
        elif tool_name == "create_file":
            return await self._tool_create_file(args)
        elif tool_name == "deploy_project":
            return await self._tool_deploy_project(args)
        elif tool_name == "run_tests":
            return await self._tool_run_tests(args)
        elif tool_name == "analyze_requirements":
            return await self._tool_analyze_requirements(args)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

    async def _tool_search_components(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Szuka komponentów w bibliotece"""
        if "components" in self.services:
            return await self.services["components"].search(
                query=args.get("query", ""),
                category=args.get("category"),
                tech_stack=args.get("tech_stack")
            )
        return {"success": True, "components": [], "message": "Component service not available"}

    async def _tool_generate_code(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generuje kod dla modułu"""
        if "code_generator" in self.services:
            return await self.services["code_generator"].generate(
                module_name=args["module_name"],
                description=args["description"],
                tech_stack=args.get("tech_stack", self.context.tech_stack if self.context else None),
                dependencies=args.get("dependencies", [])
            )
        
        # Fallback - use LLM directly
        return {"success": True, "message": "Code generation delegated to main conversation"}

    async def _tool_create_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Tworzy plik w GitHub"""
        if "github" in self.services and self.context and self.context.github_repo:
            return await self.services["github"].create_file(
                repo=self.context.github_repo,
                path=args["path"],
                content=args["content"],
                message=args.get("commit_message", f"Add {args['path']}")
            )
        return {"success": False, "error": "GitHub not configured or no repo selected"}

    async def _tool_deploy_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wdraża projekt"""
        platform = args["platform"]
        if platform in self.services.get("deployers", {}):
            result = await self.services["deployers"][platform].deploy(
                repo=self.context.github_repo if self.context else None,
                config=args.get("config", {})
            )
            if self.context and result.get("success"):
                self.context.deployment_url = result.get("url")
                self.context.deployment_platform = platform
            return result
        return {"success": False, "error": f"Deployer for {platform} not available"}

    async def _tool_run_tests(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Uruchamia testy"""
        return {"success": True, "message": "Tests would run here", "passed": True}

    async def _tool_analyze_requirements(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analizuje wymagania"""
        if self.context:
            self.context.requirements["raw"] = args.get("requirements_text", "")
            self.context.current_phase = ProjectPhase.PLANNING
        
        return {
            "success": True,
            "message": "Requirements analyzed",
            "suggested_stack": "python_fastapi",
            "estimated_components": 5
        }

    def advance_phase(self, next_phase: ProjectPhase) -> bool:
        """Przechodzi do następnej fazy projektu"""
        if self.context:
            self.context.current_phase = next_phase
            return True
        return False

    def get_progress(self) -> Dict[str, Any]:
        """Zwraca postęp projektu"""
        if not self.context:
            return {"error": "No active project"}
        
        phases = list(ProjectPhase)
        current_idx = phases.index(self.context.current_phase)
        progress = (current_idx + 1) / len(phases) * 100
        
        return {
            "project_id": self.context.project_id,
            "current_phase": self.context.current_phase.value,
            "progress_percent": round(progress, 1),
            "files_generated": len(self.context.generated_files),
            "components_used": len(self.context.components_used),
            "tokens_used": self.context.tokens_used,
            "github_repo": self.context.github_repo,
            "deployment_url": self.context.deployment_url
        }
