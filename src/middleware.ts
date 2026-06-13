import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/", "/favicon.ico"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (
    PUBLIC_PATHS.includes(pathname) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  const hasToken = req.cookies.get("advisor_token")?.value;
  if (!hasToken) {
    // localStorage isn't visible server-side; rely on client-side useAuth redirect.
    // We allow through and let useAuth push to "/" if missing.
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
