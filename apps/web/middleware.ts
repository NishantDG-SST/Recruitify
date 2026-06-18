import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

const DEMO_ORG = "11111111-1111-1111-1111-111111111111";
const DEMO_USER = "22222222-2222-2222-2222-222222222222";

const PUBLIC_PAGES = ["/login", "/signup"];
const PUBLIC_API = ["/api/users/register", "/api/users/login"];

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const backend = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

  // NextAuth's own endpoints (callbacks, session) must pass through.
  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  // Public API (signup/login) → proxy to backend without requiring a session.
  if (PUBLIC_API.includes(pathname)) {
    return NextResponse.rewrite(new URL(pathname.replace(/^\/api/, "") + search, backend));
  }

  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });

  // API proxy → require a valid session, then forward the real identity to the backend.
  if (pathname.startsWith("/api")) {
    if (!token) {
      return new NextResponse("Unauthorized", { status: 401 });
    }
    const headers = new Headers(request.headers);
    headers.set("x-user-id", (token.id as string) || DEMO_USER);
    headers.set("x-org-id", (token.org_id as string) || DEMO_ORG);

    const destinationUrl = new URL(pathname.replace(/^\/api/, "") + search, backend);
    return NextResponse.rewrite(destinationUrl, { request: { headers } });
  }

  // Public pages (login / signup) are always accessible.
  if (PUBLIC_PAGES.includes(pathname)) {
    return NextResponse.next();
  }

  // All other pages require a session.
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname + search);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything except Next.js internals and static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
