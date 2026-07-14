import datetime
import uvicorn
from fastapi import FastAPI, BackgroundTasks, Query
from scheduler import run_full_scheduled_analysis

app = FastAPI(title="NSE Pulse Analysis Trigger")

@app.get("/trigger")
async def trigger_full_analysis(
    background_tasks: BackgroundTasks,
    check_schedule: bool = Query(False, description="If true, only runs at 9:20 and 15:30 IST.")
):
    """
    Trigger a full analysis run via UptimeRobot. 
    Runs asynchronously in the background.
    """
    if check_schedule:
        now = datetime.datetime.now()
        ist_hour, ist_min = now.hour, now.minute
        target_times = [(9, 20), (15, 30)]  # 9:20 IST and 15:30 IST
        is_target_time = any(
            ist_hour == h and abs(ist_min - m) <= 5
            for h, m in target_times
        )
        if not is_target_time:
            return {"status": "skipped", "message": f"Not a scheduled time ({ist_hour}:{ist_min}). Skipping."}

    background_tasks.add_task(run_full_scheduled_analysis)
    return {"status": "success", "message": "Full analysis triggered successfully in the background."}

if __name__ == "__main__":
    # Run on a different port than main.py or Streamlit
    uvicorn.run("trigger_server:app", host="0.0.0.0", port=8080)
