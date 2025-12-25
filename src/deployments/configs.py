"""
Deployment Configurations
Konfiguracje dla różnych platform deployment
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class DeploymentConfig:
    """Konfiguracja deployment dla platformy"""
    platform: str
    build_command: Optional[str] = None
    start_command: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    health_check_path: str = "/health"
    port: int = 8000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "build_command": self.build_command,
            "start_command": self.start_command,
            "env_vars": self.env_vars,
            "health_check_path": self.health_check_path,
            "port": self.port
        }


# Railway configurations
RAILWAY_PYTHON_CONFIG = DeploymentConfig(
    platform="railway",
    build_command="pip install -r requirements.txt",
    start_command="uvicorn src.main:app --host 0.0.0.0 --port $PORT",
    port=8000,
    health_check_path="/health"
)

RAILWAY_NODE_CONFIG = DeploymentConfig(
    platform="railway",
    build_command="npm install",
    start_command="npm start",
    port=3000,
    health_check_path="/health"
)

# Vercel configurations
VERCEL_NEXTJS_CONFIG = DeploymentConfig(
    platform="vercel",
    build_command="npm run build",
    start_command=None,  # Vercel handles this
    port=3000,
    health_check_path="/"
)

VERCEL_PYTHON_CONFIG = DeploymentConfig(
    platform="vercel",
    build_command=None,
    start_command=None,
    port=8000,
    health_check_path="/health"
)

# Render configurations
RENDER_PYTHON_CONFIG = DeploymentConfig(
    platform="render",
    build_command="pip install -r requirements.txt",
    start_command="uvicorn src.main:app --host 0.0.0.0 --port $PORT",
    port=8000,
    health_check_path="/health"
)

RENDER_NODE_CONFIG = DeploymentConfig(
    platform="render",
    build_command="npm install && npm run build",
    start_command="npm start",
    port=3000,
    health_check_path="/health"
)


# Config mapping
DEPLOYMENT_CONFIGS: Dict[str, Dict[str, DeploymentConfig]] = {
    "railway": {
        "python_fastapi": RAILWAY_PYTHON_CONFIG,
        "python_django": RAILWAY_PYTHON_CONFIG,
        "node_express": RAILWAY_NODE_CONFIG,
        "react_next": RAILWAY_NODE_CONFIG,
    },
    "vercel": {
        "python_fastapi": VERCEL_PYTHON_CONFIG,
        "react_next": VERCEL_NEXTJS_CONFIG,
        "vue_nuxt": VERCEL_NEXTJS_CONFIG,
    },
    "render": {
        "python_fastapi": RENDER_PYTHON_CONFIG,
        "python_django": RENDER_PYTHON_CONFIG,
        "node_express": RENDER_NODE_CONFIG,
    }
}


def get_deployment_config(platform: str, tech_stack: str) -> Optional[DeploymentConfig]:
    """Pobiera konfigurację deployment dla platformy i stacku"""
    platform_configs = DEPLOYMENT_CONFIGS.get(platform, {})
    return platform_configs.get(tech_stack)


def get_platform_env_vars(platform: str) -> Dict[str, str]:
    """Pobiera zmienne środowiskowe specyficzne dla platformy"""
    platform_vars = {
        "railway": {
            "RAILWAY_ENVIRONMENT": "production"
        },
        "vercel": {
            "VERCEL_ENV": "production"
        },
        "render": {
            "RENDER": "true"
        }
    }
    return platform_vars.get(platform, {})


def generate_railway_json(tech_stack: str) -> Dict[str, Any]:
    """Generuje railway.json dla projektu"""
    config = get_deployment_config("railway", tech_stack)
    
    return {
        "$schema": "https://railway.app/railway.schema.json",
        "build": {
            "builder": "NIXPACKS" if "python" in tech_stack else "NIXPACKS"
        },
        "deploy": {
            "numReplicas": 1,
            "sleepApplication": False,
            "restartPolicyType": "ON_FAILURE",
            "restartPolicyMaxRetries": 10,
            "healthcheckPath": config.health_check_path if config else "/health"
        }
    }


def generate_vercel_json(tech_stack: str) -> Dict[str, Any]:
    """Generuje vercel.json dla projektu"""
    if "python" in tech_stack:
        return {
            "version": 2,
            "builds": [
                {"src": "src/main.py", "use": "@vercel/python"}
            ],
            "routes": [
                {"src": "/(.*)", "dest": "src/main.py"}
            ]
        }
    else:
        return {
            "version": 2,
            "framework": "nextjs" if "next" in tech_stack else None
        }


def generate_render_yaml(tech_stack: str, service_name: str) -> str:
    """Generuje render.yaml dla projektu"""
    config = get_deployment_config("render", tech_stack)
    
    service_type = "web"
    env = "python" if "python" in tech_stack else "node"
    
    return f'''services:
  - type: {service_type}
    name: {service_name}
    env: {env}
    buildCommand: {config.build_command if config else "pip install -r requirements.txt"}
    startCommand: {config.start_command if config else "uvicorn src.main:app"}
    healthCheckPath: {config.health_check_path if config else "/health"}
    envVars:
      - key: PYTHON_VERSION
        value: "3.11"
'''
