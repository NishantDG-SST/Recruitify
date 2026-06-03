import os

from services.workers.consumer_factory import build_consumer
from services.workers.factory import build_producer
from services.workers.runner import run_worker


def main() -> None:
    brokers = [item.strip() for item in os.getenv("KAFKA_BROKERS", "").split(",") if item.strip()]
    group_id = os.getenv("KAFKA_GROUP_ID", "resume-pipeline")
    storage_root = os.getenv("STORAGE_ROOT", "/tmp/recruitment-platform")

    consumer = build_consumer(brokers, group_id)
    producer = build_producer(brokers)

    run_worker(consumer=consumer, producer=producer, storage_root=storage_root)


if __name__ == "__main__":
    main()
