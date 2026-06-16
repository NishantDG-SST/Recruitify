"""Kafka consumer handlers for the resume processing pipeline.

Each handler corresponds to a step in the event chain:
  ResumeUploaded → ResumeParsed → CandidateExtracted →
  EmbeddingGenerated → FeaturesGenerated →
  BiasAnalysisCompleted + InterviewGenerated
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.bias.analyzer import BiasAnalyzer, CandidateProfile
from services.documents.parser import DocumentParser
from services.documents.storage import DocumentStorage
from services.features.extraction import ExtractionService
from services.features.store import FeatureRecord, FeatureStore
from services.interviews.generator import InterviewGenerator
from services.models.embedding_batcher import EmbeddingBatcher
from services.models.embedding_repository import EmbeddingRecord, EmbeddingRepository
from services.models.embedding_service import EmbeddingService
from services.workers.event_factory import build_event
from services.workers.events import EventEnvelope
from services.workers.kafka_topics import (
    BIAS_ANALYSIS_COMPLETED,
    CANDIDATE_EXTRACTED,
    EMBEDDING_GENERATED,
    FEATURES_GENERATED,
    INTERVIEW_GENERATED,
    RESUME_PARSED,
)
from services.workers.producer import EventProducer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConsumerContext:
    """Shared dependencies injected into every consumer handler."""

    storage: DocumentStorage
    parser: DocumentParser
    producer: EventProducer
    extraction: ExtractionService
    embedder: EmbeddingService
    batcher: EmbeddingBatcher
    feature_store: FeatureStore
    embedding_repo: EmbeddingRepository
    bias: BiasAnalyzer
    interviews: InterviewGenerator
    database: Optional[Any] = None


# ------------------------------------------------------------------
# 1. Resume uploaded → parse document → emit ResumeParsed
# ------------------------------------------------------------------

def consume_resume_uploaded(context: ConsumerContext, event: EventEnvelope) -> None:
    document_id = event.payload.get("document_id")
    if not document_id:
        return None
    content = context.storage.fetch(document_id)
    if not content:
        return None
    parsed = context.parser.parse_pdf(content)
    next_event = build_event(
        event_type="ResumeParsed",
        org_id=event.meta.org_id,
        payload={
            "candidate_id": event.payload.get("candidate_id"),
            "candidate_snapshot_id": event.payload.get("candidate_snapshot_id"),
            "document_id": document_id,
            "job_id": event.payload.get("job_id"),
            "parse_version": "v0",
            "text": parsed.text,
        },
        correlation_id=event.meta.correlation_id,
    )
    context.producer.publish(RESUME_PARSED, next_event)


# ------------------------------------------------------------------
# 2. Resume parsed → extract features via LLM → persist → emit CandidateExtracted
# ------------------------------------------------------------------

def consume_resume_parsed(context: ConsumerContext, event: EventEnvelope) -> None:
    candidate_id = event.payload.get("candidate_id")
    snapshot_id = event.payload.get("candidate_snapshot_id", "")
    if not candidate_id:
        return None

    # Guard: skip stale events whose snapshot was deleted
    if context.database and context.database.is_configured and snapshot_id:
        row = context.database.fetchone(
            "SELECT 1 FROM candidate_snapshots WHERE id = %s", [snapshot_id]
        )
        if not row:
            logger.warning("Skipping stale event – snapshot %s not found", snapshot_id)
            return None

    text = event.payload.get("text", "")
    extracted = context.extraction.extract(text)

    # Persist extracted features to the feature store
    feature_records = _extraction_to_feature_records(snapshot_id, extracted)
    context.feature_store.write(feature_records, model_version="v0")
    logger.info(
        "Persisted %d features for snapshot %s (method=%s)",
        len(feature_records), snapshot_id, extracted.extraction_method,
    )

    # Build a serialisable features dict for downstream consumers
    features_dict = {
        "name": extracted.name,
        "email": extracted.email,
        "phone": extracted.phone,
        "current_role": extracted.current_role,
        "skills": extracted.skills,
        "soft_skills": extracted.soft_skills,
        "roles": extracted.roles,
        "domains": extracted.domains,
        "years_experience": extracted.years_experience,
        "education_level": extracted.education_level,
        "certifications": extracted.certifications,
        "career_trajectory": extracted.career_trajectory,
        "extraction_method": extracted.extraction_method,
    }

    if context.database and context.database.is_configured:
        # Update the UI data snapshot so the frontend can display it
        context.database.execute(
            "UPDATE candidate_snapshots SET profile_json = profile_json || %s::jsonb WHERE id = %s",
            [json.dumps(features_dict), snapshot_id]
        )
        context.database.execute(
            "UPDATE candidates SET status = 'extracted' WHERE id = %s",
            [candidate_id]
        )

    next_event = build_event(
        event_type="CandidateExtracted",
        org_id=event.meta.org_id,
        payload={
            "candidate_id": candidate_id,
            "candidate_snapshot_id": snapshot_id,
            "job_id": event.payload.get("job_id"),
            "extraction_version": "v0",
            "features": features_dict,
            "resume_text": text[:8000],  # truncate to keep event size sane
        },
        correlation_id=event.meta.correlation_id,
    )
    context.producer.publish(CANDIDATE_EXTRACTED, next_event)


# ------------------------------------------------------------------
# 3. Candidate extracted → generate embeddings → write vector store → emit
# ------------------------------------------------------------------

def consume_candidate_extracted(context: ConsumerContext, event: EventEnvelope) -> None:
    snapshot_id = event.payload.get("candidate_snapshot_id")
    if not snapshot_id:
        return None

    # Build embedding input from full text + skills for richer representation
    resume_text = event.payload.get("resume_text", "")
    features = event.payload.get("features", {})
    skills_text = ", ".join(features.get("skills", []))
    roles_text = ", ".join(features.get("roles", []))

    # Combine structured + unstructured for embedding
    embed_input = f"Skills: {skills_text}\nRoles: {roles_text}\n\n{resume_text}".strip()
    if not embed_input:
        embed_input = "empty resume"

    embedding_model_id = "skipped"
    try:
        embedding = context.batcher.embed_batch([embed_input])
        record = EmbeddingRecord(
            candidate_snapshot_id=snapshot_id,
            embedding_model_id=embedding.model_id,
            vector=embedding.vectors[0],
        )
        context.embedding_repo.write(record)
        embedding_model_id = embedding.model_id
        logger.info("Wrote embedding for snapshot %s (model=%s)", snapshot_id, embedding.model_id)
    except Exception as e:
        logger.warning("Embedding failed for snapshot %s, skipping: %s", snapshot_id, e)

    next_event = build_event(
        event_type="EmbeddingGenerated",
        org_id=event.meta.org_id,
        payload={
            "candidate_snapshot_id": snapshot_id,
            "embedding_model_id": embedding_model_id,
            "embedding_id": f"emb_{snapshot_id[:8]}",
            # Carry forward for downstream consumers
            "features": features,
            "resume_text": event.payload.get("resume_text", ""),
        },
        correlation_id=event.meta.correlation_id,
    )
    context.producer.publish(EMBEDDING_GENERATED, next_event)


# ------------------------------------------------------------------
# 4. Embedding generated → update feature store → emit FeaturesGenerated
# ------------------------------------------------------------------

def consume_embedding_generated(context: ConsumerContext, event: EventEnvelope) -> None:
    snapshot_id = event.payload.get("candidate_snapshot_id")
    if not snapshot_id:
        return None

    # Mark embedding as ready in the feature store
    context.feature_store.write(
        [
            FeatureRecord(
                entity_id=snapshot_id,
                feature_name="embedding_ready",
                value=1.0,
                evidence={
                    "embedding_id": event.payload.get("embedding_id"),
                    "embedding_model_id": event.payload.get("embedding_model_id"),
                },
            )
        ]
    )

    next_event = build_event(
        event_type="FeaturesGenerated",
        org_id=event.meta.org_id,
        payload={
            "candidate_snapshot_id": snapshot_id,
            "job_version_id": event.payload.get("job_version_id", ""),
            "feature_set_id": f"fset_{snapshot_id[:8]}",
            "feature_version": "v0",
            # Carry forward for bias + interview generation
            "features": event.payload.get("features", {}),
            "resume_text": event.payload.get("resume_text", ""),
        },
        correlation_id=event.meta.correlation_id,
    )
    context.producer.publish(FEATURES_GENERATED, next_event)


# ------------------------------------------------------------------
# 5. Features generated → bias analysis → emit
# ------------------------------------------------------------------

def consume_features_generated(context: ConsumerContext, event: EventEnvelope) -> None:
    snapshot_id = event.payload.get("candidate_snapshot_id", "")
    features = event.payload.get("features", {})

    # --- Bias analysis ---
    # Build a candidate profile for the bias analyzer
    profile = CandidateProfile(
        candidate_snapshot_id=snapshot_id,
        final_score=0.0,  # score not yet computed at this stage
        education_level=features.get("education_level", "unknown"),
        years_experience=features.get("years_experience", 0),
        career_trajectory=features.get("career_trajectory", "unknown"),
        domains=features.get("domains", []),
    )
    # For now we run single-candidate analysis;
    # batch-level analysis happens in the ranking pipeline
    bias_result = context.bias.analyze(
        scores=[0.0],
        profiles=[profile],
    )

    bias_event = build_event(
        event_type="BiasAnalysisCompleted",
        org_id=event.meta.org_id,
        payload={
            "ranking_run_id": event.payload.get("ranking_run_id", ""),
            "analysis_id": f"bias_{snapshot_id[:8]}",
            "metrics": bias_result.metrics,
            "warnings": bias_result.warnings,
            "flags": [
                {
                    "flag_type": f.flag_type,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in bias_result.flags
            ],
            "hidden_gems": bias_result.hidden_gems,
        },
        correlation_id=event.meta.correlation_id,
    )
    context.producer.publish(BIAS_ANALYSIS_COMPLETED, bias_event)



# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extraction_to_feature_records(
    snapshot_id: str, extracted: Any
) -> list[FeatureRecord]:
    """Convert an ExtractionResult into a list of FeatureRecords."""
    records: list[FeatureRecord] = []

    # One record per technical skill
    for skill in extracted.skills:
        records.append(FeatureRecord(
            entity_id=snapshot_id,
            feature_name=f"skill:{skill}",
            value=1.0,
            evidence={"source": extracted.extraction_method, "skill": skill},
        ))

    # One record per soft skill
    for skill in extracted.soft_skills:
        records.append(FeatureRecord(
            entity_id=snapshot_id,
            feature_name=f"soft_skill:{skill}",
            value=1.0,
            evidence={"source": extracted.extraction_method, "skill": skill},
        ))

    # Experience level
    records.append(FeatureRecord(
        entity_id=snapshot_id,
        feature_name="years_experience",
        value=float(extracted.years_experience),
        evidence={"source": extracted.extraction_method},
    ))

    # Education level as an ordinal
    edu_ordinal = {"unknown": 0, "high_school": 1, "bachelors": 2, "masters": 3, "phd": 4}
    records.append(FeatureRecord(
        entity_id=snapshot_id,
        feature_name="education_level",
        value=float(edu_ordinal.get(extracted.education_level, 0)),
        evidence={"source": extracted.extraction_method, "level": extracted.education_level},
    ))

    return records


# ------------------------------------------------------------------
# Handler registry
# ------------------------------------------------------------------

EVENT_HANDLERS: Dict[str, str] = {
    "ResumeUploaded": "consume_resume_uploaded",
    "ResumeParsed": "consume_resume_parsed",
    "CandidateExtracted": "consume_candidate_extracted",
    "EmbeddingGenerated": "consume_embedding_generated",
    "FeaturesGenerated": "consume_features_generated",
}
