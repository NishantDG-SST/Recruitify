"""Worker runner that builds the ConsumerContext and dispatches events."""

import os
from pathlib import Path
from typing import Callable, Dict

from services.bias.analyzer import BiasAnalyzer
from services.documents.parser import DocumentParser
from services.documents.storage_local import LocalDocumentStorage, LocalStorageConfig
from services.features.extraction import ExtractionService
from services.features.store import PostgresFeatureStore
from services.interviews.generator import InterviewGenerator
from services.llm.client import LLMClient, LLMConfig
from services.models.embedding_batcher import EmbeddingBatcher
from services.models.embedding_repository import EmbeddingRepository
from services.models.embedding_service import EmbeddingService
from services.taxonomy.normalizer import TaxonomyNormalizer
from services.workers.consumers import (
    ConsumerContext,
    consume_candidate_extracted,
    consume_embedding_generated,
    consume_features_generated,
    consume_resume_parsed,
    consume_resume_uploaded,
)
from apps.api.src.core.database import get_database
from services.workers.consumer import EventConsumer
from services.workers.events import EventEnvelope
from services.workers.producer import EventProducer


HANDLERS: Dict[str, Callable[[ConsumerContext, EventEnvelope], None]] = {
    "ResumeUploaded": consume_resume_uploaded,
    "ResumeParsed": consume_resume_parsed,
    "CandidateExtracted": consume_candidate_extracted,
    "EmbeddingGenerated": consume_embedding_generated,
    "FeaturesGenerated": consume_features_generated,
}


def run_worker(
    consumer: EventConsumer,
    producer: EventProducer,
    storage_root: str,
) -> None:
    database = get_database(os.getenv("DATABASE_DSN"))

    # Build the LLM client from environment
    llm_config = LLMConfig(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        model=os.getenv("LLM_MODEL", "gemini-flash-latest"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "gemini-embedding-2"),
        embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
    )
    llm_client = LLMClient(llm_config)

    normalizer = TaxonomyNormalizer()
    embedder = EmbeddingService(
        model_id=llm_config.embedding_model,
        dim=llm_config.embedding_dimensions,
        llm_client=llm_client,
    )

    context = ConsumerContext(
        storage=LocalDocumentStorage(LocalStorageConfig(root_dir=Path(storage_root))),
        parser=DocumentParser(),
        producer=producer,
        extraction=ExtractionService(normalizer=normalizer, llm_client=llm_client),
        embedder=embedder,
        batcher=EmbeddingBatcher(embedder),
        feature_store=PostgresFeatureStore(database),
        embedding_repo=EmbeddingRepository(database),
        bias=BiasAnalyzer(),
        interviews=InterviewGenerator(llm_client=llm_client),
        database=database,
    )
    consumer.subscribe(
        [
            "resume-uploaded",
            "resume-parsed",
            "candidate-extracted",
            "embedding-generated",
            "features-generated",
        ]
    )

    print(f"Worker started. Subscribed to topics. Waiting for events...")
    import time
    while True:
        events = consumer.poll()
        for event in events:
            print(f"Received event: {event.event_type}")
            handler = HANDLERS.get(event.event_type)
            if handler:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        handler(context, event)
                        print(f"Successfully processed {event.event_type}")
                        break
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "Too Many Requests" in error_str:
                            wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                            print(f"Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                            time.sleep(wait)
                        else:
                            print(f"Error processing {event.event_type}: {e}")
                            break
                # Throttle between events to stay within Groq free tier limits
                time.sleep(1)
            else:
                print(f"No handler for {event.event_type}")
