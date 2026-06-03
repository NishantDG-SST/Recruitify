import { NextResponse } from "next/server";

export async function GET(request: Request, { params }: { params: { jobId: string } }) {
  const candidates = [
    { candidate_id: "cand_demo_001", score: 92.5, rank: 1, explanation_text: "Candidate has strong alignment with all technical requirements including AWS and Docker." },
    { candidate_id: "cand_demo_002", score: 85.0, rank: 2, explanation_text: "Candidate possesses most skills but lacks 2 years of the requested experience." },
    { candidate_id: "cand_demo_003", score: 72.0, rank: 3, explanation_text: "Candidate has the required domains but missing Python expertise." }
  ];

  return NextResponse.json({
    run_id: "run_demo_123",
    candidates
  });
}
