import { NextResponse } from "next/server";

export async function POST(request: Request, { params }: { params: { jobId: string, runId: string } }) {
  const body = await request.json();
  console.log("Override received:", body);
  return NextResponse.json({ status: "success" });
}
