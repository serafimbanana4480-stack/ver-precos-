from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.db import get_db_context
from database.models import Vehicle
import os

app = FastAPI()

# Create static directory if it doesn't exist
static_path = os.path.join(os.getcwd(), "dashboard") # We serve from dashboard
app.mount("/static", StaticFiles(directory=static_path), name="static")

templates = Jinja2Templates(directory="dashboard")

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    with get_db_context() as session:
        # Get top deals
        top_deals = session.query(Vehicle).filter(
            Vehicle.deal_score >= 80,
            Vehicle.is_active == True
        ).order_by(Vehicle.deal_score.desc()).limit(20).all()
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "deals": top_deals
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
