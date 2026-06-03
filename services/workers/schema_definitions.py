from services.workers.schema_registry import SchemaDefinition


SCHEMA_DEFINITIONS = [
    SchemaDefinition(
        event_type="JobCreated",
        required_fields=["job_id", "job_version_id", "created_by"],
    ),
    SchemaDefinition(
        event_type="ResumeUploaded",
        required_fields=["candidate_id", "document_id", "job_id", "batch_id"],
    ),
    SchemaDefinition(
        event_type="ResumeParsed",
        required_fields=["candidate_id", "document_id", "job_id", "parse_version"],
    ),
    SchemaDefinition(
        event_type="CandidateExtracted",
        required_fields=["candidate_id", "candidate_snapshot_id", "job_id", "extraction_version"],
    ),
    SchemaDefinition(
        event_type="EmbeddingGenerated",
        required_fields=["candidate_snapshot_id", "embedding_model_id", "embedding_id"],
    ),
    SchemaDefinition(
        event_type="FeaturesGenerated",
        required_fields=["candidate_snapshot_id", "job_version_id", "feature_set_id", "feature_version"],
    ),
    SchemaDefinition(
        event_type="RankingRequested",
        required_fields=["job_version_id", "ranking_run_id", "requested_by"],
    ),
    SchemaDefinition(
        event_type="RankingCompleted",
        required_fields=["ranking_run_id", "job_version_id", "candidate_count"],
    ),
    SchemaDefinition(
        event_type="InterviewGenerated",
        required_fields=["ranking_run_id", "candidate_snapshot_id", "interview_id"],
    ),
    SchemaDefinition(
        event_type="BiasAnalysisCompleted",
        required_fields=["ranking_run_id", "analysis_id"],
    ),
]
