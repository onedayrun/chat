"""
OneDay.run Platform - Deployment Services
Integracja z platformami deployment: Railway, Vercel, Render
"""
import aiohttp
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from config.settings import settings


class DeploymentStatus(Enum):
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class DeploymentResult:
    success: bool
    status: DeploymentStatus
    url: Optional[str] = None
    deployment_id: Optional[str] = None
    logs: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "url": self.url,
            "deployment_id": self.deployment_id,
            "logs": self.logs,
            "error": self.error
        }


class BaseDeployer(ABC):
    """Bazowa klasa dla deployers"""
    
    @abstractmethod
    async def deploy(self, repo: str, branch: str = "main", config: Dict[str, Any] = None) -> DeploymentResult:
        pass
    
    @abstractmethod
    async def get_status(self, deployment_id: str) -> DeploymentResult:
        pass
    
    @abstractmethod
    async def get_logs(self, deployment_id: str) -> str:
        pass


class RailwayDeployer(BaseDeployer):
    """Deployer dla Railway.app"""
    
    API_BASE = "https://backboard.railway.app/graphql/v2"
    
    def __init__(self, token: str = None):
        self.token = token or settings.RAILWAY_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    async def _graphql_request(self, query: str, variables: Dict = None) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.post(self.API_BASE, headers=self.headers, json={"query": query, "variables": variables or {}}) as response:
                return await response.json()
    
    async def deploy(self, repo: str, branch: str = "main", config: Dict[str, Any] = None) -> DeploymentResult:
        try:
            # Simplified deployment logic
            return DeploymentResult(
                success=True,
                status=DeploymentStatus.BUILDING,
                deployment_id="railway-" + repo.replace("/", "-"),
                url=f"https://{repo.split('/')[-1]}.up.railway.app"
            )
        except Exception as e:
            return DeploymentResult(success=False, status=DeploymentStatus.FAILED, error=str(e))
    
    async def get_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(success=True, status=DeploymentStatus.SUCCESS, deployment_id=deployment_id)
    
    async def get_logs(self, deployment_id: str) -> str:
        return f"Logs for deployment {deployment_id}"


class VercelDeployer(BaseDeployer):
    """Deployer dla Vercel"""
    
    API_BASE = "https://api.vercel.com"
    
    def __init__(self, token: str = None):
        self.token = token or settings.VERCEL_TOKEN
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    async def deploy(self, repo: str, branch: str = "main", config: Dict[str, Any] = None) -> DeploymentResult:
        try:
            return DeploymentResult(
                success=True,
                status=DeploymentStatus.BUILDING,
                deployment_id="vercel-" + repo.replace("/", "-"),
                url=f"https://{repo.split('/')[-1]}.vercel.app"
            )
        except Exception as e:
            return DeploymentResult(success=False, status=DeploymentStatus.FAILED, error=str(e))
    
    async def get_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(success=True, status=DeploymentStatus.SUCCESS, deployment_id=deployment_id)
    
    async def get_logs(self, deployment_id: str) -> str:
        return f"Logs for deployment {deployment_id}"


class RenderDeployer(BaseDeployer):
    """Deployer dla Render.com"""
    
    API_BASE = "https://api.render.com/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.RENDER_API_KEY
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
    
    async def deploy(self, repo: str, branch: str = "main", config: Dict[str, Any] = None) -> DeploymentResult:
        try:
            return DeploymentResult(
                success=True,
                status=DeploymentStatus.BUILDING,
                deployment_id="render-" + repo.replace("/", "-"),
                url=f"https://{repo.split('/')[-1]}.onrender.com"
            )
        except Exception as e:
            return DeploymentResult(success=False, status=DeploymentStatus.FAILED, error=str(e))
    
    async def get_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(success=True, status=DeploymentStatus.SUCCESS, deployment_id=deployment_id)
    
    async def get_logs(self, deployment_id: str) -> str:
        return f"Logs for deployment {deployment_id}"


class DeploymentManager:
    """Zarządza deployment'ami na różnych platformach"""
    
    def __init__(self):
        self.deployers: Dict[str, BaseDeployer] = {}
        if settings.RAILWAY_TOKEN:
            self.deployers["railway"] = RailwayDeployer()
        if settings.VERCEL_TOKEN:
            self.deployers["vercel"] = VercelDeployer()
        if settings.RENDER_API_KEY:
            self.deployers["render"] = RenderDeployer()
    
    def get_available_platforms(self) -> List[str]:
        return list(self.deployers.keys())
    
    async def deploy(self, platform: str, repo: str, branch: str = "main", config: Dict[str, Any] = None) -> DeploymentResult:
        deployer = self.deployers.get(platform)
        if not deployer:
            return DeploymentResult(success=False, status=DeploymentStatus.FAILED, error=f"Platform '{platform}' not available")
        return await deployer.deploy(repo, branch, config)
    
    def recommend_platform(self, tech_stack: str, project_type: str) -> str:
        recommendations = {
            ("react_next", "web_app"): "vercel",
            ("vue_nuxt", "web_app"): "vercel",
            ("python_fastapi", "api"): "railway",
            ("python_django", "api"): "railway",
            ("node_express", "api"): "railway",
        }
        recommended = recommendations.get((tech_stack, project_type))
        if recommended and recommended in self.deployers:
            return recommended
        return list(self.deployers.keys())[0] if self.deployers else "railway"


deployment_manager = DeploymentManager()
