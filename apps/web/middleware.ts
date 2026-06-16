import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  
  // Intercept all /api calls, excluding /api/auth
  if (path.startsWith("/api") && !path.startsWith("/api/auth")) {
    const headers = new Headers(request.headers);
    // Always use global demo user/org
    headers.set("x-user-id", "22222222-2222-2222-2222-222222222222");
    headers.set("x-org-id", "11111111-1111-1111-1111-111111111111");

    // Proxy the request directly to the Python backend
    // Remove the "/api" prefix so it hits the backend root
    const pythonPath = request.nextUrl.pathname.replace(/^\/api/, "");
    const destinationUrl = new URL(
      pythonPath + request.nextUrl.search,
      process.env.INTERNAL_API_URL || "http://127.0.0.1:8000"
    );

    return NextResponse.rewrite(destinationUrl, {
      request: {
        headers,
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
