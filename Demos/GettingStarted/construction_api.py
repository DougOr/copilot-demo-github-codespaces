"""
Construction Management API Server
A local API endpoint system for Microsoft Copilot integration
Provides construction schedule and inventory management capabilities
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
from datetime import datetime
from pathlib import Path

# Initialize FastAPI app
app = FastAPI(
    title="Construction Management API",
    description="Local API for construction schedule and inventory management",
    version="1.0.0"
)

# Add CORS middleware to allow Copilot to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configuration
CONFIG_FILE = "endpoints_config.json"
SCHEDULE_FILE = "schedule.json"
INVENTORY_FILE = "inventory.json"

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File {file_path} not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in {file_path}")

def format_schedule_response(data: Dict[str, Any], query_type: str = "general") -> str:
    """Format schedule data into natural language for Copilot."""
    project_name = data.get("project_name", "Unknown Project")
    schedule = data.get("schedule", {})
    
    if query_type == "general":
        phases = schedule.get("phases", [])
        progress = schedule.get("overall_progress", {})
        key_dates = schedule.get("key_dates", {})
        
        response = f"""
📋 **{project_name} - Schedule Overview**

**Overall Progress:** {progress.get('overall_percentage', 0)}% Complete
- Completed Phases: {progress.get('completed_phases', 0)}
- In Progress: {progress.get('in_progress_phases', 0)}
- Pending: {progress.get('pending_phases', 0)}

**Timeline:**
- Started: {key_dates.get('project_start', 'N/A')}
- Estimated Completion: {key_dates.get('estimated_completion', 'N/A')}
- Days Remaining: {key_dates.get('days_remaining', 0)}

**Current Status:**
"""
        for phase in phases[:3]:  # Show first 3 phases
            status_emoji = "✅" if phase["status"] == "completed" else "🔄" if phase["status"] == "in_progress" else "⏳"
            response += f"\n{status_emoji} {phase['name']}: {phase['status'].title()} ({phase.get('progress', 0)}%)"
        
        return response.strip()
    
    elif query_type == "deadlines":
        deadlines = schedule.get("upcoming_deadlines", [])
        response = f"🚨 **Upcoming Deadlines for {project_name}:**\n\n"
        
        for deadline in deadlines:
            priority_emoji = "🔴" if deadline["priority"] == "critical" else "🟡" if deadline["priority"] == "high" else "🟢"
            response += f"{priority_emoji} **{deadline['date']}** - {deadline['task']}\n"
            response += f"   Impact: {deadline['impact']}\n"
            response += f"   Responsible: {deadline['responsible_party']}\n\n"
        
        return response.strip()
    
    elif query_type == "current_phase":
        phases = schedule.get("phases", [])
        current_phase = next((p for p in phases if p["status"] == "in_progress"), None)
        
        if not current_phase:
            return f"📍 **Current Phase Status for {project_name}:**\n\nNo phase currently in progress."
        
        response = f"📍 **Current Phase: {current_phase['name']}**\n\n"
        response += f"**Progress:** {current_phase['progress']}%\n"
        response += f"**Team Size:** {current_phase['team_size']} workers\n"
        response += f"**Contractor:** {current_phase['contractor']}\n"
        response += f"**Dates:** {current_phase['start_date']} to {current_phase['end_date']}\n\n"
        response += "**Upcoming Milestones:**\n"
        
        for milestone in current_phase.get("milestones", []):
            if milestone["status"] in ["in_progress", "pending"]:
                emoji = "🔄" if milestone["status"] == "in_progress" else "⏳"
                response += f"{emoji} {milestone['name']} - {milestone['date']}\n"
        
        return response.strip()
    
    return format_schedule_response(data, "general")

def format_inventory_response(data: Dict[str, Any], query_type: str = "general", filters: Optional[Dict] = None) -> str:
    """Format inventory data into natural language for Copilot."""
    inventory = data.get("inventory", {})
    location = data.get("location", "Unknown Location")
    
    if query_type == "general":
        materials = inventory.get("materials", [])
        equipment = inventory.get("equipment", [])
        status_summary = inventory.get("equipment_status_summary", {})
        
        response = f"📦 **Inventory Overview - {location}**\n\n"
        response += f"**Materials:** {len(materials)} categories\n"
        response += f"**Equipment:** {equipment} total items\n\n"
        
        response += "**Equipment Status:**\n"
        response += f"✅ Available: {status_summary.get('available', 0)}\n"
        response += f"🔧 In Use: {status_summary.get('in_use', 0)}\n"
        response += f"⚠️ Maintenance: {status_summary.get('maintenance', 0)}\n\n"
        
        # Show low stock alerts
        low_stock = inventory.get("low_stock_alerts", [])
        if low_stock:
            response += "⚠️ **Low Stock Alerts:**\n"
            for alert in low_stock:
                response += f"- {alert['name']}: {alert['current_quantity']} {alert['item_id']} (Reorder level: {alert['reorder_level']})\n"
                response += f"  Action: {alert['recommended_action']}\n\n"
        
        return response.strip()
    
    elif query_type == "equipment":
        equipment = inventory.get("equipment", [])
        status = filters.get("status") if filters else None
        
        response = f"🔧 **Equipment Status - {location}**\n\n"
        
        if status:
            filtered_eq = [eq for eq in equipment if eq["status"] == status]
            response += f"**{status.title()} Equipment:**\n\n"
            for eq in filtered_eq:
                response += f"- {eq['name']} ({eq['category']})\n"
                response += f"  Location: {eq['location']}\n"
                if eq["current_operator"]:
                    response += f"  Operator: {eq['current_operator']}\n"
                response += f"  Rate: ${eq['hourly_rate']}/hr\n\n"
        else:
            for eq in equipment:
                status_emoji = "✅" if eq["status"] == "available" else "🔧" if eq["status"] == "in_use" else "⚠️"
                response += f"{status_emoji} {eq['name']}\n"
                response += f"   Status: {eq['status'].title()}\n"
                response += f"   Location: {eq['location']}\n"
                if eq["next_maintenance"]:
                    response += f"   Next Maintenance: {eq['next_maintenance']}\n"
                response += "\n"
        
        return response.strip()
    
    elif query_type == "materials":
        materials = inventory.get("materials", [])
        
        response = f"📦 **Materials Inventory - {location}**\n\n"
        
        for mat in materials:
            status_emoji = "⚠️" if mat["quantity"] <= mat["reorder_level"] else "✅"
            response += f"{status_emoji} {mat['name']}\n"
            response += f"   Quantity: {mat['quantity']} {mat['unit']}\n"
            response += f"   Location: {mat['location']}\n"
            response += f"   Cost: ${mat['unit_cost']}/{mat['unit']}\n"
            if mat["quantity"] <= mat["reorder_level"]:
                response += f"   ⚠️ LOW STOCK - Reorder level: {mat['reorder_level']}\n"
            response += "\n"
        
        return response.strip()
    
    elif query_type == "available":
        equipment = inventory.get("equipment", [])
        available_eq = [eq for eq in equipment if eq["status"] == "available"]
        
        response = f"✅ **Available Equipment - {location}**\n\n"
        response += f"Total Available: {len(available_eq)} items\n\n"
        
        for eq in available_eq:
            response += f"- {eq['name']} ({eq['category']})\n"
            response += f"  Location: {eq['location']}\n"
            response += f"  Rate: ${eq['hourly_rate']}/hr\n"
            response += f"  Operator Required: {'Yes' if eq['operator_required'] else 'No'}\n\n"
        
        return response.strip()
    
    return format_inventory_response(data, "general")

# Pydantic models for request/response validation
class ScheduleQuery(BaseModel):
    query_type: str = "general"
    phase_id: Optional[str] = None

class InventoryQuery(BaseModel):
    query_type: str = "general"
    category: Optional[str] = None
    status: Optional[str] = None
    item_name: Optional[str] = None

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    config = load_json_file(CONFIG_FILE)
    return {
        "message": "Construction Management API",
        "version": config.get("version", "1.0"),
        "endpoints": list(config.get("endpoints", {}).keys()),
        "description": "Local API for construction schedule and inventory management",
        "copilot_integration": True,
        "usage": "Use /api/schedule or /api/inventory endpoints"
    }

# Configuration endpoint
@app.get("/api/config")
async def get_config():
    """Get API configuration and available endpoints."""
    config = load_json_file(CONFIG_FILE)
    return config

# Schedule endpoints
@app.get("/api/schedule")
async def get_schedule(
    query_type: str = Query("general", description="Type of schedule query: general, deadlines, current_phase"),
    phase_id: Optional[str] = Query(None, description="Specific phase ID")
):
    """
    Get schedule information.
    
    Query Types:
    - general: Overall schedule overview
    - deadlines: Upcoming deadlines and critical dates
    - current_phase: Details about the current active phase
    """
    try:
        schedule_data = load_json_file(SCHEDULE_FILE)
        
        if query_type == "general":
            return {
                "data": schedule_data,
                "formatted_response": format_schedule_response(schedule_data, "general"),
                "query_type": "general"
            }
        elif query_type == "deadlines":
            return {
                "data": schedule_data,
                "formatted_response": format_schedule_response(schedule_data, "deadlines"),
                "query_type": "deadlines"
            }
        elif query_type == "current_phase":
            return {
                "data": schedule_data,
                "formatted_response": format_schedule_response(schedule_data, "current_phase"),
                "query_type": "current_phase"
            }
        else:
            return {
                "data": schedule_data,
                "formatted_response": format_schedule_response(schedule_data, "general"),
                "query_type": "general"
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule/query")
async def query_schedule(query: ScheduleQuery):
    """
    Query schedule data with specific parameters.
    
    Example JSON body:
    {
        "query_type": "deadlines",
        "phase_id": "P002"
    }
    """
    try:
        schedule_data = load_json_file(SCHEDULE_FILE)
        formatted = format_schedule_response(schedule_data, query.query_type)
        
        return {
            "success": True,
            "data": schedule_data,
            "formatted_response": formatted,
            "query_type": query.query_type,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Inventory endpoints
@app.get("/api/inventory")
async def get_inventory(
    query_type: str = Query("general", description="Type of inventory query: general, equipment, materials, available"),
    status: Optional[str] = Query(None, description="Filter by equipment status: available, in_use, maintenance"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """
    Get inventory information.
    
    Query Types:
    - general: Overall inventory overview
    - equipment: Equipment status and details
    - materials: Materials inventory
    - available: Only available equipment
    """
    try:
        inventory_data = load_json_file(INVENTORY_FILE)
        
        filters = {}
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category
        
        formatted = format_inventory_response(inventory_data, query_type, filters)
        
        return {
            "data": inventory_data,
            "formatted_response": formatted,
            "query_type": query_type,
            "filters": filters
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/inventory/query")
async def query_inventory(query: InventoryQuery):
    """
    Query inventory data with specific parameters.
    
    Example JSON body:
    {
        "query_type": "equipment",
        "status": "available",
        "category": "Heavy Equipment"
    }
    """
    try:
        inventory_data = load_json_file(INVENTORY_FILE)
        
        filters = {}
        if query.status:
            filters["status"] = query.status
        if query.category:
            filters["category"] = query.category
        
        formatted = format_inventory_response(inventory_data, query.query_type, filters)
        
        return {
            "success": True,
            "data": inventory_data,
            "formatted_response": formatted,
            "query_type": query.query_type,
            "filters": filters,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "files": {
            "config": os.path.exists(CONFIG_FILE),
            "schedule": os.path.exists(SCHEDULE_FILE),
            "inventory": os.path.exists(INVENTORY_FILE)
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("""
    🚀 Construction Management API Server
    =====================================
    
    Starting server on http://localhost:8000
    
    Available endpoints:
    - GET  /                    - API information
    - GET  /api/config          - Configuration details
    - GET  /api/schedule        - Schedule information
    - POST /api/schedule/query  - Schedule queries
    - GET  /api/inventory       - Inventory information
    - POST /api/inventory/query - Inventory queries
    - GET  /health              - Health check
    
    Press Ctrl+C to stop the server
    """)
    
    uvicorn.run(app, host="localhost", port=8000)