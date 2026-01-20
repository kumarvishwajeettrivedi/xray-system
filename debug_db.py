import asyncio
from xray_api.database import get_db, init_db, async_session_maker
from xray_api.models import PipelineRunModel
from sqlalchemy import select

async def main():
    try:
        async with async_session_maker() as db:
            print("Querying all runs...")
            result = await db.execute(select(PipelineRunModel))
            runs = result.scalars().all()
            
            print(f"Total runs found: {len(runs)}")
            for run in runs:
                print(f"Run ID: {run.run_id}")
                print(f"  Pipeline: {run.pipeline_name}")
                print(f"  Context: {run.context}")
                print("-" * 20)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
