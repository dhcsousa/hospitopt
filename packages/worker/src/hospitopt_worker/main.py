"""Polling worker that runs optimization when inputs change."""

import asyncio
import hashlib
import json
import logging
from collections.abc import Sequence

from hospitopt_core.config.env import Environment
from hospitopt_core.domain.models import Ambulance, Hospital, Patient, PatientStatus
from hospitopt_worker.db import DatabaseWriter, check_connection
from hospitopt_worker.ingestion import APIIngestor, SQLAlchemyIngestor
from hospitopt_worker.ingestion.base import DataIngestor
from hospitopt_worker.optimize import LockedAssignment, optimize_allocation
from hospitopt_worker.routing import RoutingBackend
from hospitopt_worker.settings import WorkerConfig

logger = logging.getLogger(__name__)

env = Environment()
if not env.WORKER_CONFIG_FILE_PATH:  # pragma: no cover
    raise ValueError(
        "WORKER_CONFIG_FILE_PATH environment variable is not set. For running the worker, this must be set."
    )
config = WorkerConfig.from_yaml(env.WORKER_CONFIG_FILE_PATH)


def _hash_inputs(
    hospitals: Sequence[Hospital],
    patients: Sequence[Patient],
    ambulances: Sequence[Ambulance],
) -> str:
    payload = {
        "hospitals": [h.model_dump(mode="json") for h in sorted(hospitals, key=lambda h: str(h.id))],
        "patients": [p.model_dump(mode="json") for p in sorted(patients, key=lambda p: str(p.id))],
        "ambulances": [a.model_dump(mode="json") for a in sorted(ambulances, key=lambda a: str(a.id))],
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def run_worker() -> None:
    """Poll for input changes and run optimization when needed."""
    ingestion_engine = None
    ingestor: DataIngestor
    if config.ingestion.type == "db":
        ingestion_engine, ingestion_sessions = config.ingestion.to_engine_session_factory()
        await check_connection(ingestion_sessions)
        ingestor = SQLAlchemyIngestor(ingestion_sessions)
    elif config.ingestion.type == "api":
        ingestor = APIIngestor(host_url=config.ingestion.host, api_key=config.ingestion.api_key)
    else:
        raise ValueError(f"Unsupported ingestion type: {config.ingestion.type}")

    worker_engine, worker_sessions = config.db_connection.to_engine_session_factory()
    await check_connection(worker_sessions)

    writer = DatabaseWriter(worker_sessions)

    async with RoutingBackend.from_config(config.routing) as routing:
        last_hash: str | None = None
        try:
            while True:
                hospitals = await ingestor.get_hospitals()
                patients = await ingestor.get_patients()
                ambulances = await ingestor.get_ambulances()

                current_hash = _hash_inputs(hospitals, patients, ambulances)
                if current_hash != last_hash:
                    if config.sync_inputs_to_db:
                        await writer.write_inputs(hospitals, patients, ambulances)
                    if not hospitals or not patients or not ambulances:
                        logger.info("Skipping optimization due to missing inputs.")
                    else:
                        eligible_patients: Sequence[Patient]
                        if config.optimization.allow_reassign_in_transit:
                            eligible_patients = [p for p in patients if p.status != PatientStatus.DELIVERED]
                        else:
                            eligible_patients = [p for p in patients if p.status == PatientStatus.WAITING]

                        if not eligible_patients:
                            logger.info("Skipping optimization because there are no eligible patients.")
                            last_hash = current_hash
                            await asyncio.sleep(config.poll_interval_seconds)
                            continue

                        # Build locked assignments when hospital reassignment is
                        # disabled: in-transit patients keep their current hospital.
                        locked: list[LockedAssignment] = []
                        if not config.optimization.allow_hospital_reassignment:
                            in_transit_ids = {p.id for p in eligible_patients if p.status == PatientStatus.IN_TRANSIT}
                            for pid, hid in (await writer.read_locked_hospitals(in_transit_ids)).items():
                                locked.append(LockedAssignment(patient_id=pid, hospital_id=hid))

                        minutes_tables = await routing.build_minutes_tables(
                            list(eligible_patients), list(hospitals), list(ambulances)
                        )
                        result = optimize_allocation(
                            minutes_tables=minutes_tables,
                            hospitals=hospitals,
                            patients=eligible_patients,
                            ambulances=ambulances,
                            speed_factor=config.optimization.speed_factor,
                            locked_assignments=locked,
                        )
                        await writer.write_optimization_result(result)
                        logger.info(
                            "Optimization complete. max_lives_saved=%s unassigned=%s",
                            result.max_lives_saved,
                            len(result.unassigned_patient_ids),
                        )
                    last_hash = current_hash
                else:
                    logger.debug("No input changes detected, skipping optimization.")

                await asyncio.sleep(config.poll_interval_seconds)
        finally:
            if ingestion_engine is not None:
                await ingestion_engine.dispose()
            await worker_engine.dispose()


def run_worker_forever() -> None:
    """Run the polling worker."""
    config.logging.setup_logging(level=env.LOG_LEVEL)
    asyncio.run(run_worker())


if __name__ == "__main__":
    run_worker_forever()
