from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RankingRun:
    run_id: str
    job_version_id: str
    status: str


@dataclass(frozen=True)
class RankingOutput:
    run_id: str
    candidate_snapshot_id: str
    final_score: float
    rank: int
    decision: str


class InMemoryRankingStore:
    def __init__(self) -> None:
        self._runs: Dict[str, RankingRun] = {}
        self._outputs: Dict[str, List[RankingOutput]] = {}

    def create_run(self, run: RankingRun) -> None:
        self._runs[run.run_id] = run

    def add_output(self, output: RankingOutput) -> None:
        self._outputs.setdefault(output.run_id, []).append(output)

    def list_outputs(self, run_id: str) -> List[RankingOutput]:
        return list(self._outputs.get(run_id, []))
